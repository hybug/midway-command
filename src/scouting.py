"""Scouting detection engine with full lifecycle.

Phases:
1. PREPARING  (0-15min)  — 甲板准备，不消耗燃油
2. OUTBOUND   (15-60min) — 飞往搜索区域，消耗燃油
3. SEARCHING  (60-120min)— 搜索中，消耗燃油
4. RETURNING  (120-165min)— 返航中，消耗燃油
5. LANDED/LOST — 着舰/损失

Fuel model (SBD Dauntless):
- Cruise: 0.8% fuel per nm
- Search: 0.4% fuel per minute (circling)
- Total range: ~250nm at full fuel
"""
import logging
import math
import random
from datetime import timedelta

from src.state import (
    GameState, EnemyKnown, Position, PendingReport,
    ScoutMission, ScoutPhase, AircraftLoss, AircraftStatus, SearchPattern,
)
from src.intel.contracts import CheckType
from src.intel.rng import RNGService
from src.npc_config import UNIT_REGISTRY

logger = logging.getLogger("midway.scouting")

# ── SBD Dauntless parameters (normalized to fuel_pct, 200gal tank) ──
PREP_TIME_MIN = 15          # 起飞准备时间
OUTBOUND_TIME_MIN = 45      # 飞往搜索区域时间
SEARCH_TIME_MIN = 60        # 搜索持续时间
RETURN_TIME_MIN = 45        # 返航时间（与去程相同）
FUEL_BURN_PER_NM = 0.6      # 巡航油耗: 1.2 gal/nm ÷ 200 gal = 0.6%/nm
FUEL_BURN_PER_SEARCH_MIN = 0.125  # 搜索油耗: 25 gal/hr ÷ 200 gal = 0.125%/min
FUEL_RETURN_MINIMUM = 15.0  # 返航最低燃油百分比
FUEL_CRITICAL = 5.0         # 燃油危险线
FUEL_LOW = 10.0             # 燃油低线

# ── Loss probabilities ──
WEATHER_LOSS_PROB = 0.05    # 天气损失概率
MIDWAY_LANDING_FAIL_PROB = 0.10  # 中途岛着舰失败概率
ENEMY_CAP_LOSS_PROB = 0.15  # 敌方CAP击落概率（仅在敌军附近）


# ═══════════════════════════════════════════════════════
# Coordinate utilities (same as before)
# ═══════════════════════════════════════════════════════

def calculate_bearing(pos1: tuple, pos2: tuple) -> float:
    lat1, lon1 = math.radians(pos1[0]), math.radians(pos1[1])
    lat2, lon2 = math.radians(pos2[0]), math.radians(pos2[1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def calculate_distance_nm(pos1: tuple, pos2: tuple) -> float:
    lat1, lon1 = math.radians(pos1[0]), math.radians(pos1[1])
    lat2, lon2 = math.radians(pos2[0]), math.radians(pos2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 3440.065 * c


def in_sector(bearing: float, bearing_min: int, bearing_max: int) -> bool:
    if bearing_min <= bearing_max:
        return bearing_min <= bearing <= bearing_max
    else:
        return bearing >= bearing_min or bearing <= bearing_max


# ═══════════════════════════════════════════════════════
# 航线生成函数（§6.5.1~6.5.3）
# ═══════════════════════════════════════════════════════

def generate_sector_route(
    fleet_pos: tuple,
    center_bearing: int,
    sector_width: int,
    radius_nm: int,
) -> list[tuple[int, int]]:
    """扇形搜索航线生成（§6.5.1）

    Args:
        fleet_pos: 舰队位置 (lat, lon)
        center_bearing: 中心方位
        sector_width: 扇面宽度（°）
        radius_nm: 搜索半径（nm）

    Returns:
        list of (q, r) hex coordinates
    """
    from src.render.coordinate import world_to_hex, hex_to_world

    route = []
    bearing_min = (center_bearing - sector_width // 2) % 360
    bearing_max = (center_bearing + sector_width // 2) % 360

    # 出航段：沿中心方位飞到半径
    steps = max(1, radius_nm // 10)
    for i in range(1, steps + 1):
        dist = i * 10
        pos = _bearing_distance_to_position(fleet_pos, center_bearing, dist)
        hex_pos = world_to_hex(pos.lat, pos.lon)
        if hex_pos not in route:
            route.append(hex_pos)

    # 弧线段：在半径处沿弧线扫荡
    arc_steps = max(1, sector_width // 10)
    for i in range(arc_steps + 1):
        if bearing_min <= bearing_max:
            bearing = bearing_min + i * (sector_width / arc_steps)
        else:
            bearing = (bearing_min + i * ((360 - bearing_min + bearing_max) / arc_steps)) % 360
        pos = _bearing_distance_to_position(fleet_pos, bearing, radius_nm)
        hex_pos = world_to_hex(pos.lat, pos.lon)
        if hex_pos not in route:
            route.append(hex_pos)

    # 返航段：从弧线末端返回舰队
    # （简化：直接添加舰队位置）
    fleet_hex = world_to_hex(fleet_pos[0], fleet_pos[1])
    if fleet_hex not in route:
        route.append(fleet_hex)

    return route


def generate_expanding_square_route(
    fleet_pos: tuple,
    max_radius_nm: int,
) -> list[tuple[int, int]]:
    """扩展方形航线生成（§6.5.2）

    Args:
        fleet_pos: 舰队位置 (lat, lon)
        max_radius_nm: 最大半径（nm）

    Returns:
        list of (q, r) hex coordinates
    """
    from src.render.coordinate import world_to_hex

    route = []
    max_steps = max_radius_nm // 10

    # 方向序列：北→东→南→西
    directions = [
        (0, 1),   # 北
        (1, 0),   # 东
        (0, -1),  # 南
        (-1, 0),  # 西
    ]

    # 从舰队位置开始
    start_hex = world_to_hex(fleet_pos[0], fleet_pos[1])
    q, r = start_hex
    route.append((q, r))

    step_size = 1
    dir_idx = 0

    while step_size <= max_steps:
        for _ in range(2):  # 每个步长执行两次（北1东1南2西2...）
            dq, dr = directions[dir_idx % 4]
            for _ in range(step_size):
                q += dq
                r += dr
                if (q, r) not in route:
                    route.append((q, r))
            dir_idx += 1
        step_size += 1

    return route


def generate_parallel_route(
    fleet_pos: tuple,
    bearing: int,
    width_nm: int,
    spacing_nm: int,
) -> list[tuple[int, int]]:
    """平行搜索航线生成（§6.5.3）

    Args:
        fleet_pos: 舰队位置 (lat, lon)
        bearing: 主方向
        width_nm: 宽度（nm）
        spacing_nm: 间距（nm）

    Returns:
        list of (q, r) hex coordinates
    """
    from src.render.coordinate import world_to_hex

    route = []
    num_lines = max(1, width_nm // spacing_nm)
    line_length = width_nm

    for line in range(num_lines):
        # 偏移方向（垂直于主方向）
        offset_bearing = (bearing + 90) % 360
        offset_dist = (line - num_lines // 2) * spacing_nm
        line_start_pos = _bearing_distance_to_position(fleet_pos, offset_bearing, offset_dist)
        line_start = (line_start_pos.lat, line_start_pos.lon)

        # 沿主方向飞行
        steps = max(1, line_length // 10)
        for i in range(steps + 1):
            dist = i * 10
            if line % 2 == 0:
                # 偶数行：正向
                pos = _bearing_distance_to_position(line_start, bearing, dist)
            else:
                # 奇数行：反向
                pos = _bearing_distance_to_position(line_start, (bearing + 180) % 360, dist)
            hex_pos = world_to_hex(pos.lat, pos.lon)
            if hex_pos not in route:
                route.append(hex_pos)

    return route


# ═══════════════════════════════════════════════════════
# 空间相遇检测（§6.5.4）
# ═══════════════════════════════════════════════════════

def check_detection(
    scout_hex: tuple[int, int],
    state: GameState,
) -> list[dict]:
    """空间相遇检测（§6.5.4）

    Args:
        scout_hex: 侦察机当前 hex
        state: 游戏状态

    Returns:
        list of {enemy_id, enemy_hex, distance_hex}
    """
    from src.render.coordinate import hex_distance, world_to_hex

    detections = []
    hidden = state.actual_enemy or []

    for i, enemy in enumerate(hidden):
        epos = enemy.get("position", {})
        enemy_lat = epos.get("lat", 0)
        enemy_lon = epos.get("lon", 0)
        enemy_hex = world_to_hex(enemy_lat, enemy_lon)

        dist = hex_distance(scout_hex[0], scout_hex[1], enemy_hex[0], enemy_hex[1])
        if dist <= 1:  # 同格或相邻
            detections.append({
                "enemy_id": enemy.get("name", f"enemy_{i}"),
                "enemy_hex": enemy_hex,
                "distance_hex": dist,
                "enemy_data": enemy,
            })

    return detections


# ═══════════════════════════════════════════════════════
# Distortion functions（S2.1：传 rng=RNGService 时走可复现记录抽取；
# 不传时保持全局 random——仅供旧调用方/测试，游戏管线一律传 rng）
# ═══════════════════════════════════════════════════════

def distort_bearing(bearing: float, max_error: int = 5, rng: RNGService | None = None) -> int:
    if rng is not None:
        err = rng.randint(
            CheckType.OBSERVATION_QUALITY_CHECK, "观测失真", -max_error, max_error,
            reason="方位失真抽取", inputs={"bearing": round(bearing, 1)},
        )
    else:
        err = random.randint(-max_error, max_error)
    return int((bearing + err + 360) % 360)


def distort_distance(distance: float, max_error_pct: float = 0.1, rng: RNGService | None = None) -> int:
    if rng is not None:
        # 以 0.01 粒度抽取，范围受 max_error_pct 约束（±10% ⇒ -10..10）
        span = max(1, int(round(max_error_pct * 100)))
        factor = rng.randint(
            CheckType.OBSERVATION_QUALITY_CHECK, "观测失真", -span, span,
            reason="距离失真抽取",
            inputs={"distance_nm": round(distance, 1)},
            effects={"max_error_pct": max_error_pct},
        ) / 100.0
    else:
        factor = random.uniform(-max_error_pct, max_error_pct)
    return int(distance * (1 + factor))


def distort_count(real_count: int, undercount_prob: float = 0.3, rng: RNGService | None = None) -> int:
    if rng is not None:
        under = rng.chance(
            CheckType.OBSERVATION_QUALITY_CHECK, "观测失真", undercount_prob,
            reason="数量少报抽取", inputs={"real_count": real_count},
        )
        decoy = rng.randint(
            CheckType.OBSERVATION_QUALITY_CHECK, "观测失真", 1, 2,
            reason="少报幅度抽取", inputs={"real_count": real_count},
        ) if under else 0
    else:
        under = random.random() < undercount_prob
        decoy = random.randint(1, 2) if under else 0
    return max(1, real_count - decoy) if under else real_count


def compute_report_delay(distance_nm: float, rng: RNGService | None = None) -> int:
    base = 20
    distance_factor = (distance_nm / 200) * 25
    if rng is not None:
        jitter = rng.randint(
            CheckType.COMMUNICATION_CHECK, "报告传输", -5, 10,
            reason="报告延迟抖动", inputs={"distance_nm": round(distance_nm, 1)},
        )
    else:
        jitter = random.randint(-5, 10)
    return int(base + distance_factor + jitter)


# ═══════════════════════════════════════════════════════
# Phase state machine
# ═══════════════════════════════════════════════════════

def _get_fleet_pos(state: GameState) -> tuple:
    """Get fleet position as (lat, lon)."""
    tf = state.task_forces[0]
    return (tf.carriers[0].position.lat, tf.carriers[0].position.lon)


def _burn_fuel(scout: ScoutMission, amount: float, state: GameState):
    """Burn fuel on ScoutMission and linked Aircraft objects."""
    scout.fuel_pct = max(0.0, scout.fuel_pct - amount)
    # Also burn fuel on linked Aircraft
    for tf in state.task_forces:
        for carrier in tf.carriers:
            for aircraft in carrier.aircraft:
                if aircraft.id in scout.aircraft_ids:
                    aircraft.fuel_pct = max(0.0, aircraft.fuel_pct - amount)


def _advance_phase(scout: ScoutMission, new_phase: ScoutPhase, state: GameState):
    """Transition to a new phase."""
    scout.phase = new_phase
    scout.phase_started_at = state.clock.game_time

    # Update position based on phase
    fleet_pos = _get_fleet_pos(state)
    if new_phase == ScoutPhase.OUTBOUND:
        # Start at fleet position
        scout.position = Position(lat=fleet_pos[0], lon=fleet_pos[1])
    elif new_phase == ScoutPhase.SEARCHING:
        # Move to search area center (bearing + distance from fleet)
        mid_bearing = (scout.search_bearing_min + scout.search_bearing_max) / 2
        search_dist = min(scout.search_distance_nm, 180)  # Cap at 180nm
        scout.position = _bearing_distance_to_position(fleet_pos, mid_bearing, search_dist)
    elif new_phase == ScoutPhase.RETURNING:
        # Start return from current search position
        pass  # position stays at search area, will move toward fleet each tick

    logger.info(f"[SCOUT] {scout.id} → {new_phase.value} (fuel: {scout.fuel_pct:.1f}%)")


def _update_aircraft_on_landing(state: GameState, scout: ScoutMission, new_status: AircraftStatus):
    """Update Aircraft status when scout mission ends."""
    for tf in state.task_forces:
        for carrier in tf.carriers:
            for aircraft in carrier.aircraft:
                if aircraft.id in scout.aircraft_ids:
                    aircraft.status = new_status
                    aircraft.assigned_mission = None


def _check_enemy_proximity(state: GameState, scout: ScoutMission) -> bool:
    """Check if scout is near hidden enemy fleet."""
    hidden = state.actual_enemy or []
    fleet_pos = _get_fleet_pos(state)
    for enemy in hidden:
        epos = enemy.get("position", {})
        enemy_pos = (epos.get("lat", 0), epos.get("lon", 0))
        dist = calculate_distance_nm(fleet_pos, enemy_pos)
        # If scout searched in the right sector and enemy is within range
        bearing = calculate_bearing(fleet_pos, enemy_pos)
        if in_sector(bearing, scout.search_bearing_min, scout.search_bearing_max):
            if dist <= scout.search_distance_nm:
                return True
    return False


def _process_returning(scout: ScoutMission, state: GameState) -> list[str]:
    """Process the return phase of a scout mission."""
    notifications = []
    rng = RNGService(state)
    unit = UNIT_REGISTRY["sbd_scout_section"]
    elapsed = (state.clock.game_time - scout.phase_started_at).total_seconds() / 60

    # Burn return fuel
    _burn_fuel(scout, FUEL_BURN_PER_NM * 2, state)  # ~2nm per 15min tick at cruise

    # Move position toward fleet (2nm per tick)
    if scout.position:
        fleet_pos = _get_fleet_pos(state)
        current = (scout.position.lat, scout.position.lon)
        dist_to_fleet = calculate_distance_nm(current, fleet_pos)
        if dist_to_fleet > 2:
            # Move 2nm toward fleet
            bearing_to_fleet = calculate_bearing(current, fleet_pos)
            new_pos = _bearing_distance_to_position(current, bearing_to_fleet, 2.0)
            scout.position.lat = new_pos.lat
            scout.position.lon = new_pos.lon
        else:
            # Close enough — snap to fleet
            scout.position.lat = fleet_pos[0]
            scout.position.lon = fleet_pos[1]

    # Check fuel status
    if scout.fuel_pct <= FUEL_CRITICAL:
        # Aircraft lost
        lost = min(2, scout.aircraft_count - scout.aircraft_lost)
        if lost > 0:
            scout.aircraft_lost += lost
            scout.loss_reasons.append(f"燃油耗尽损失 {lost} 架")
            state.aircraft_losses.extend([
                AircraftLoss(
                    scout_id=scout.id,
                    aircraft_number=scout.aircraft_lost - lost + i + 1,
                    reason="fuel_exhausted",
                    time=state.clock.game_time,
                )
                for i in range(lost)
            ])
            notifications.append(f"⚠️ {scout.id}: {lost} 架飞机因燃油耗尽坠海！（剩余 {scout.aircraft_count - scout.aircraft_lost} 架）")
            logger.warning(f"[SCOUT] {scout.id} LOST {lost} aircraft — fuel exhausted")

        # If all lost
        if scout.aircraft_lost >= scout.aircraft_count:
            _advance_phase(scout, ScoutPhase.LOST, state)
            scout.status = "completed"
            notifications.append(f"❌ {scout.id}: 全部飞机损失！任务终止。")
            return notifications

    elif scout.fuel_pct <= FUEL_LOW:
        # 50% chance of losing an aircraft
        if rng.chance(
            "raw_draw", unit.name, 0.5,
            reason=f"{scout.id} 低燃油损失抽取",
            inputs={"fuel_pct": round(scout.fuel_pct, 1)},
        ):
            lost = 1
            scout.aircraft_lost += lost
            scout.loss_reasons.append(f"低燃油损失 {lost} 架")
            state.aircraft_losses.append(AircraftLoss(
                scout_id=scout.id,
                aircraft_number=scout.aircraft_lost,
                reason="fuel_exhausted",
                time=state.clock.game_time,
            ))
            notifications.append(f"⚠️ {scout.id}: 1 架飞机因燃油不足坠海！（剩余 {scout.aircraft_count - scout.aircraft_lost} 架）")

    # Check if return phase complete
    if elapsed >= RETURN_TIME_MIN:
        # Check weather loss (5% per aircraft remaining)
        remaining = scout.aircraft_count - scout.aircraft_lost
        weather_lost = sum(
            1 for i in range(remaining)
            if rng.chance(
                "raw_draw", unit.name, WEATHER_LOSS_PROB,
                reason=f"{scout.id} 天气损失抽取",
                inputs={"aircraft_index": i + 1},
            )
        )
        if weather_lost > 0:
            scout.aircraft_lost += weather_lost
            scout.loss_reasons.append(f"天气损失 {weather_lost} 架")
            state.aircraft_losses.extend([
                AircraftLoss(
                    scout_id=scout.id,
                    aircraft_number=scout.aircraft_lost - weather_lost + i + 1,
                    reason="weather",
                    time=state.clock.game_time,
                )
                for i in range(weather_lost)
            ])
            notifications.append(f"🌧️ {scout.id}: {weather_lost} 架飞机因恶劣天气损失")

        # Final status
        remaining = scout.aircraft_count - scout.aircraft_lost
        if remaining <= 0:
            _advance_phase(scout, ScoutPhase.LOST, state)
            scout.status = "completed"
            # Mark all aircraft as lost
            _update_aircraft_on_landing(state, scout, AircraftStatus.MAINTENANCE)
            notifications.append(f"❌ {scout.id}: 全部飞机损失！任务终止。")
        else:
            _advance_phase(scout, ScoutPhase.LANDED, state)
            scout.status = "completed"
            _update_aircraft_on_landing(state, scout, AircraftStatus.LANDING)
            notifications.append(
                f"✅ {scout.id}: {remaining}/{scout.aircraft_count} 架飞机安全着舰"
                + (f"（损失 {scout.aircraft_lost} 架）" if scout.aircraft_lost > 0 else "")
            )
            logger.info(f"[SCOUT] {scout.id} LANDED — {remaining}/{scout.aircraft_count} aircraft")

    return notifications


def _process_searching(scout: ScoutMission, state: GameState) -> list[str]:
    """Process the search phase — detect enemies and check fuel.

    Uses the dice system for detection checks instead of fixed probabilities.
    """
    notifications = []
    elapsed_search = (state.clock.game_time - scout.phase_started_at).total_seconds() / 60

    # Burn search fuel
    _burn_fuel(scout, FUEL_BURN_PER_SEARCH_MIN * 15, state)  # 15 min per tick

    # Detection check (at end of search)
    if elapsed_search >= SEARCH_TIME_MIN:
        hidden = state.actual_enemy or []
        fleet_pos = _get_fleet_pos(state)

        # S2.1：检定用实际执行单位能力 + 可复现 RNG（骰子缺口 #1/#3）
        rng = RNGService(state)
        unit = UNIT_REGISTRY["sbd_scout_section"]

        detected = False

        for enemy in hidden:
            epos = enemy.get("position", {})
            enemy_pos = (epos.get("lat", 0), epos.get("lon", 0))
            bearing = calculate_bearing(fleet_pos, enemy_pos)
            distance = calculate_distance_nm(fleet_pos, enemy_pos)

            if not in_sector(bearing, scout.search_bearing_min, scout.search_bearing_max):
                continue
            if distance > scout.search_distance_nm:
                continue

            # Roll dice for detection（检定记录落 state.check_records）
            result, _rec = rng.detection_check(
                unit=unit,
                distance_nm=distance,
                pattern=scout.search_pattern.value,
                reason=f"{scout.id} 侦察检定",
                inputs={
                    "sector": f"{scout.search_bearing_min}-{scout.search_bearing_max}",
                    "enemy": enemy.get("name", "?"),
                },
            )

            logger.info(f"[SCOUT] {scout.id} 侦察检定: {result} (距离{int(distance)}nm)")

            if result.is_success():
                # S2.3：探测成功 → 情报流（观测/观察质量/报告撰写/通信检定，
                # 到达处理在管线 process_intel 步骤——src/intel/flow.py）
                from src.intel.flow import on_scout_detection
                on_scout_detection(state, scout=scout, enemy=enemy,
                                   bearing=bearing, distance=distance,
                                   result=result)
                notifications.append(f"📡 {scout.id} 发现敌舰！报告传输中")
                logger.info(f"[SCOUT] {scout.id} DETECTED at bearing {int(bearing)}°, {int(distance)}nm")
                detected = True
                break

            elif result.level == "partial":
                # Partial identification — see something but unclear
                notifications.append(
                    f"📡 {scout.id}: 看到大型船只，但无法确认类型（方位{int(bearing)}°）"
                )
                logger.info(f"[SCOUT] {scout.id} PARTIAL at bearing {int(bearing)}°")

            elif result.level == "failure":
                # Missed — didn't see anything
                logger.info(f"[SCOUT] {scout.id} MISSED at bearing {int(bearing)}°")

            elif result.level == "critical_failure":
                # Critical failure — aircraft lost or major false report
                lost = min(1, scout.aircraft_count - scout.aircraft_lost)
                if lost > 0:
                    scout.aircraft_lost += lost
                    scout.loss_reasons.append(f"侦察中被击落 {lost} 架")
                    state.aircraft_losses.append(AircraftLoss(
                        scout_id=scout.id,
                        aircraft_number=scout.aircraft_lost,
                        reason="shot_down",
                        time=state.clock.game_time,
                    ))
                    notifications.append(f"❌ {scout.id}: 1 架飞机在侦察中被击落！")
                logger.warning(f"[SCOUT] {scout.id} CRITICAL FAILURE — aircraft lost")

        if not detected:
            state.incoming_messages.append(
                f"[{state.clock.game_time.strftime('%H:%M')}] {scout.id}: 搜索扇面内未发现敌舰"
            )
            notifications.append(f"📡 {scout.id}: 扇面内未发现敌舰")

        # Transition to return
        scout.return_heading = (scout.heading + 180) % 360  # Reverse heading
        scout.return_eta_minutes = RETURN_TIME_MIN
        _advance_phase(scout, ScoutPhase.RETURNING, state)

    return notifications


def _process_outbound(scout: ScoutMission, state: GameState) -> list[str]:
    """Process the outbound flight phase."""
    notifications = []
    elapsed = (state.clock.game_time - scout.phase_started_at).total_seconds() / 60

    # Burn outbound fuel
    _burn_fuel(scout, FUEL_BURN_PER_NM * 2, state)  # ~2nm per 15min tick

    if elapsed >= OUTBOUND_TIME_MIN:
        _advance_phase(scout, ScoutPhase.SEARCHING, state)

    return notifications


def _process_preparing(scout: ScoutMission, state: GameState) -> list[str]:
    """Process the preparation phase."""
    elapsed = (state.clock.game_time - scout.phase_started_at).total_seconds() / 60
    if elapsed >= PREP_TIME_MIN:
        _advance_phase(scout, ScoutPhase.OUTBOUND, state)
    return []


# ═══════════════════════════════════════════════════════
# Main check function (called by EventScheduler)
# ═══════════════════════════════════════════════════════

def check_scout_results(state: GameState) -> list[str]:
    """Check all active scout missions through the phase state machine.

    Each call processes the current phase. On the next tick, the next phase
    will be processed. This ensures time passes between phase transitions.
    """
    notifications = []

    for scout in state.active_scouts:
        if scout.status != "in_flight":
            continue
        if scout.phase in (ScoutPhase.LANDED, ScoutPhase.LOST):
            continue

        if scout.phase == ScoutPhase.PREPARING:
            notifications.extend(_process_preparing(scout, state))
        elif scout.phase == ScoutPhase.OUTBOUND:
            notifications.extend(_process_outbound(scout, state))
        elif scout.phase == ScoutPhase.SEARCHING:
            notifications.extend(_process_searching(scout, state))
        elif scout.phase == ScoutPhase.RETURNING:
            notifications.extend(_process_returning(scout, state))

    return notifications


# ═══════════════════════════════════════════════════════
# Pending reports (unchanged logic)
# ═══════════════════════════════════════════════════════

def _bearing_distance_to_position(origin: tuple, bearing_deg: float, distance_nm: float) -> Position:
    """Convert bearing + distance from origin to a Position (lat/lon)."""
    lat1 = math.radians(origin[0])
    lon1 = math.radians(origin[1])
    bearing = math.radians(bearing_deg)
    R = 3440.065  # Earth radius in nm

    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance_nm / R) +
        math.cos(lat1) * math.sin(distance_nm / R) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(distance_nm / R) * math.cos(lat1),
        math.cos(distance_nm / R) - math.sin(lat1) * math.sin(lat2)
    )
    return Position(lat=math.degrees(lat2), lon=math.degrees(lon2))


def check_pending_reports(state: GameState) -> list[str]:
    """Check if any pending reports have arrived. Convert to EnemyKnown."""
    notifications = []
    arrived = []

    for report in state.pending_reports:
        if state.clock.game_time >= report.arrive_at:
            # Compute actual position from bearing/distance
            tf = state.task_forces[0]
            fleet_pos = (tf.carriers[0].position.lat, tf.carriers[0].position.lon)
            enemy_pos = _bearing_distance_to_position(
                fleet_pos, report.reported_bearing, report.reported_distance_nm
            )

            enemy = EnemyKnown(
                position=enemy_pos,
                description=(
                    f"SBD {report.scout_id}: 敌航母约 {report.reported_carrier_count} 艘"
                    f" - 方位 {report.reported_bearing}°"
                    f" - 距离约 {report.reported_distance_nm} 海里"
                ),
                confidence=report.confidence,
                source=report.scout_id,
                reported_at=report.arrive_at,
            )
            state.known_enemy.append(enemy)
            msg = f"[{report.arrive_at.strftime('%H:%M')}] {enemy.description}"
            state.incoming_messages.append(msg)
            notifications.append(f"📡 {report.scout_id} 报告到达：{enemy.description}")
            arrived.append(report)
            logger.info(f"[REPORT] {report.scout_id} arrived: {enemy.description}")

    for r in arrived:
        state.pending_reports.remove(r)

    return notifications
