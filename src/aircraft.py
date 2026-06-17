"""航空参谋系统 — 飞机管理、编组生命周期、燃油计算、着舰检定。

职责：
- 飞机状态管理（READY→IN_FLIGHT→RETURNING→LANDING→READY）
- 编组（AirGroup）生命周期
- 燃油消耗计算
- 着舰检定（骰子系统五级结果）
- 战损追踪

飞机始终属于航母（Carrier.aircrafts），飞行中通过 AirGroup 追踪。
"""
import logging
from datetime import datetime
from typing import Optional

from src.state import (
    GameState, AirGroup, AirGroupStatus, AirGroupType,
    Aircraft, AircraftType, AircraftStatus, AircraftLoss,
    Carrier, TaskForce,
)
from src.dice import roll_landing_check, DiceResult
from src.npc_config import NPC_REGISTRY

logger = logging.getLogger("midway.aircraft")


# ── 燃油参数 ──

FUEL_RATE_CRUISE = {
    AircraftType.SBD: 0.6,
    AircraftType.TBD: 0.6,
    AircraftType.VF: 0.8,
}

FUEL_RATE_SEARCH = {
    AircraftType.SBD: 0.125,
    AircraftType.TBD: 0.125,
    AircraftType.VF: 0.15,
}

AIRCRAFT_SPEED = {
    AircraftType.SBD: 150,
    AircraftType.TBD: 120,
    AircraftType.VF:  180,
}

AIRCRAFT_HP = {
    AircraftType.SBD: 3,
    AircraftType.TBD: 2,
    AircraftType.VF:  3,
}

HANGAR_CAPACITY = 300
FUEL_RETURN_THRESHOLD = 15.0
FUEL_CRITICAL = 5.0


# ── 编组管理 ──

def create_air_group(
    state: GameState,
    carrier_name: str,
    aircraft_ids: list[str],
    mission_type: str = "strike",
    group_id: Optional[str] = None,
) -> AirGroup:
    """创建编组，将指定飞机加入。

    AIR-002: 飞机状态必须为 READY。
    """
    # 验证飞机状态
    carrier = _find_carrier(state, carrier_name)
    if not carrier:
        raise ValueError(f"Carrier not found: {carrier_name}")

    for aid in aircraft_ids:
        aircraft = _find_aircraft(carrier, aid)
        if not aircraft:
            raise ValueError(f"Aircraft not found: {aid}")
        if aircraft.status != AircraftStatus.READY:
            raise ValueError(f"Aircraft {aid} not READY (status={aircraft.status})")

    # 创建编组
    if not group_id:
        group_id = f"ag-{carrier_name}-{datetime.utcnow().timestamp()}"

    ag = AirGroup(
        id=group_id,
        type=_determine_group_type(carrier, aircraft_ids),
        count=len(aircraft_ids),
        status=AirGroupStatus.READY,
        carrier_name=carrier_name,
        mission_type=mission_type,
    )

    # 更新飞机状态
    for aid in aircraft_ids:
        aircraft = _find_aircraft(carrier, aid)
        if aircraft:
            aircraft.group_id = group_id

    carrier.air_groups.append(ag)
    logger.info(f"[AIRCRAFT] Created AirGroup {group_id} with {len(aircraft_ids)} aircraft")
    return ag


def launch_air_group(state: GameState, group_id: str) -> list[str]:
    """LAUNCHING → AIRBORNE

    AIR-004: 1 轮后自动变为 AIRBORNE。
    """
    notifications = []
    ag = _find_air_group(state, group_id)
    if not ag or ag.status != AirGroupStatus.LAUNCHING:
        return notifications

    ag.status = AirGroupStatus.AIRBORNE
    ag.launched_at = state.clock.game_time

    # 更新飞机状态
    carrier = _find_carrier(state, ag.carrier_name)
    if carrier:
        for aircraft in carrier.aircraft:
            if aircraft.group_id == group_id:
                aircraft.status = AircraftStatus.IN_FLIGHT

    notifications.append(f"✈️ 编组 {group_id} 已起飞")
    logger.info(f"[AIRCRAFT] AirGroup {group_id} → AIRBORNE")
    return notifications


def update_fuel(state: GameState, minutes: int = 15) -> list[str]:
    """每 tick 消耗燃油。

    AIR-005: 巡航油耗
    AIR-007: 燃油耗尽 → LOST
    AIR-008: 燃油 ≤ 15% → 自动返航
    """
    notifications = []

    for ag in state.task_forces:
        for carrier in ag.carriers:
            for aircraft in carrier.aircraft:
                if aircraft.status != AircraftStatus.IN_FLIGHT:
                    continue
                if not aircraft.group_id:
                    continue

                # 计算燃油消耗
                fuel_rate = FUEL_RATE_CRUISE.get(aircraft.type, 0.6)
                speed = AIRCRAFT_SPEED.get(aircraft.type, 150)
                distance_nm = speed * (minutes / 60)
                fuel_consumed = fuel_rate * distance_nm

                aircraft.fuel_pct = max(0.0, aircraft.fuel_pct - fuel_consumed)

                # 燃油耗尽
                if aircraft.fuel_pct <= 0:
                    aircraft.status = AircraftStatus.LOST
                    state.aircraft_losses.append(AircraftLoss(
                        scout_id=aircraft.group_id or "unknown",
                        aircraft_number=1,
                        reason="fuel_exhausted",
                        time=state.clock.game_time,
                    ))
                    notifications.append(f"⛽ {aircraft.id}: 燃油耗尽，飞机损失！")
                    logger.warning(f"[AIRCRAFT] {aircraft.id} LOST — fuel exhausted")

                # 低燃油自动返航
                elif aircraft.fuel_pct <= FUEL_RETURN_THRESHOLD:
                    ag_group = _find_air_group(state, aircraft.group_id)
                    if ag_group and ag_group.status == AirGroupStatus.AIRBORNE:
                        ag_group.status = AirGroupStatus.RETURNING
                        notifications.append(f"⛽ 编组 {aircraft.group_id}: 燃油不足，自动返航")
                        logger.info(f"[AIRCRAFT] AirGroup {aircraft.group_id} → RETURNING (low fuel)")

    return notifications


def process_landing(state: GameState) -> list[str]:
    """处理着舰检定。

    AIR-010: 着舰检定（骰子系统五级结果）
    AIR-011: 失败重试机制
    """
    notifications = []
    npc_config = NPC_REGISTRY["murray"]

    for ag in state.task_forces:
        for carrier in ag.carriers:
            for aircraft in carrier.aircraft:
                if aircraft.status != AircraftStatus.LANDING:
                    continue

                # 着舰检定
                is_night = state.clock.game_time.hour >= 19
                result = roll_landing_check(
                    npc_config,
                    fuel_pct=aircraft.fuel_pct,
                    is_night=is_night,
                )

                logger.info(f"[AIRCRAFT] {aircraft.id} landing check: {result}")

                if result.level == "critical_success":
                    # 大成功：立即回到 READY
                    aircraft.status = AircraftStatus.READY
                    aircraft.fuel_pct = 100.0
                    notifications.append(f"✅ {aircraft.id}: 完美着舰！")

                elif result.level == "success":
                    # 成功：进入 REFUELING
                    aircraft.status = AircraftStatus.LOADING
                    notifications.append(f"✅ {aircraft.id}: 正常着舰")

                elif result.level == "partial":
                    # 部分成功：甲板占用 1 轮
                    # TODO: 实现甲板占用逻辑
                    aircraft.status = AircraftStatus.LOADING
                    notifications.append(f"⚠️ {aircraft.id}: 粗暴着舰，甲板占用")

                elif result.level == "failure":
                    # 失败：甲板占用 1 轮后重试
                    # TODO: 实现重试逻辑
                    notifications.append(f"❌ {aircraft.id}: 着舰失败，重试中")

                elif result.level == "critical_failure":
                    # 大失败：飞机坠海
                    aircraft.status = AircraftStatus.LOST
                    state.aircraft_losses.append(AircraftLoss(
                        scout_id=aircraft.group_id or "unknown",
                        aircraft_number=1,
                        reason="landing_failed",
                        time=state.clock.game_time,
                    ))
                    notifications.append(f"💥 {aircraft.id}: 着舰大失败，飞机坠海！")

    return notifications


def recall_air_group(state: GameState, group_id: str) -> list[str]:
    """召回编组。

    AIR-009: 玩家召回
    """
    notifications = []
    ag = _find_air_group(state, group_id)
    if not ag:
        return notifications

    if ag.status == AirGroupStatus.AIRBORNE:
        ag.status = AirGroupStatus.RETURNING
        notifications.append(f"🔄 编组 {group_id} 已召回，开始返航")
        logger.info(f"[AIRCRAFT] AirGroup {group_id} → RETURNING (manual recall)")
    elif ag.status == AirGroupStatus.RETURNING:
        notifications.append(f"编组 {group_id} 已在返航中")

    return notifications


def damage_aircraft(aircraft: Aircraft, damage: int) -> bool:
    """对飞机造成伤害。

    AIR-013/014: HP ≤ 0 → LOST
    """
    aircraft.hp = max(0, aircraft.hp - damage)
    if aircraft.hp <= 0:
        aircraft.status = AircraftStatus.LOST
        return True
    return False


# ── 查询接口 ──

def get_aircraft_status(state: GameState, carrier_name: str) -> dict:
    """获取航母飞机状态。"""
    carrier = _find_carrier(state, carrier_name)
    if not carrier:
        return {"error": f"Carrier not found: {carrier_name}"}

    return {
        "carrier": carrier_name,
        "total": len(carrier.aircraft),
        "ready": sum(1 for a in carrier.aircraft if a.status == AircraftStatus.READY),
        "in_flight": sum(1 for a in carrier.aircraft if a.status == AircraftStatus.IN_FLIGHT),
        "returning": sum(1 for a in carrier.aircraft if a.status == AircraftStatus.RETURNING),
        "lost": sum(1 for a in carrier.aircraft if a.status == AircraftStatus.LOST),
        "aircraft": [
            {
                "id": a.id,
                "type": a.type.value,
                "status": a.status.value,
                "fuel_pct": a.fuel_pct,
                "hp": a.hp,
            }
            for a in carrier.aircraft
        ],
    }


def get_air_group_status(state: GameState, group_id: str) -> dict:
    """获取编组状态。"""
    ag = _find_air_group(state, group_id)
    if not ag:
        return {"error": f"AirGroup not found: {group_id}"}

    return {
        "id": ag.id,
        "carrier": ag.carrier_name,
        "status": ag.status.value,
        "count": ag.count,
        "mission_type": ag.mission_type,
        "launched_at": ag.launched_at.isoformat() if ag.launched_at else None,
    }


# ── 内部辅助函数 ──

def _find_carrier(state: GameState, carrier_name: str) -> Optional[Carrier]:
    """查找航母。"""
    for tf in state.task_forces:
        for carrier in tf.carriers:
            if carrier.name == carrier_name:
                return carrier
    return None


def _find_aircraft(carrier: Carrier, aircraft_id: str) -> Optional[Aircraft]:
    """查找飞机。"""
    for aircraft in carrier.aircraft:
        if aircraft.id == aircraft_id:
            return aircraft
    return None


def _find_air_group(state: GameState, group_id: str) -> Optional[AirGroup]:
    """查找编组。"""
    for tf in state.task_forces:
        for carrier in tf.carriers:
            for ag in carrier.air_groups:
                if ag.id == group_id:
                    return ag
    return None


def _determine_group_type(carrier: Carrier, aircraft_ids: list[str]) -> AirGroupType:
    """根据飞机类型确定编组类型。"""
    types = set()
    for aid in aircraft_ids:
        aircraft = _find_aircraft(carrier, aid)
        if aircraft:
            types.add(aircraft.type)

    if AircraftType.VF in types and len(types) == 1:
        return AirGroupType.FIGHTER
    elif AircraftType.TBD in types:
        return AirGroupType.TORPEDO
    else:
        return AirGroupType.DIVE_BOMBER
