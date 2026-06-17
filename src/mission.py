"""出击规划系统 — 拦截点计算、油量预算、NPC简报数据。

职责：
- 拦截点计算（运动学方程）
- 油量预算
- MissionPlan 生成
- NPC 简报数据准备

AIR-017~022: 出击规划流程
"""
import logging
import math
from typing import Optional

from src.state import (
    GameState, MissionPlan, Position, AirGroup, AirGroupStatus,
)
from src.render.coordinate import world_to_hex, hex_to_world, hex_distance

logger = logging.getLogger("midway.mission")


# ── 飞机速度（kt）──

AIRCRAFT_SPEED = {
    "SBD": 150,
    "TBD": 120,
    "VF": 180,
}

FUEL_RATE = {
    "SBD": 0.6,
    "TBD": 0.6,
    "VF": 0.8,
}


def calculate_intercept(
    enemy_lat: float,
    enemy_lon: float,
    enemy_course: int,
    enemy_speed: int,
    launch_lat: float,
    launch_lon: float,
    aircraft_speed: int,
) -> Optional[dict]:
    """计算拦截点。

    AIR-017: 运动学方程求解。

    Returns:
        dict with intercept_point, heading, distance_nm, flight_time_min
        or None if no solution (aircraft too slow)
    """
    # 转为平面坐标（nm）
    # 以 launch 为原点
    dlat = enemy_lat - launch_lat
    dlon = enemy_lon - launch_lon
    nm_north = dlat * 60
    nm_east = dlon * 60 * math.cos(math.radians(28.2))

    # 敌舰速度矢量
    course_rad = math.radians(enemy_course)
    vx = enemy_speed * math.sin(course_rad)
    vy = enemy_speed * math.cos(course_rad)

    # 解方程: |D + V*t| = S*t
    # |D|² + 2(D·V)t + |V|²t² = S²t²
    # (S² - |V|²)t² - 2(D·V)t - |D|² = 0
    d_sq = nm_east**2 + nm_north**2
    d_dot_v = nm_east * vx + nm_north * vy
    v_sq = vx**2 + vy**2
    s_sq = aircraft_speed**2

    a = s_sq - v_sq
    b = -2 * d_dot_v
    c = -d_sq

    if a == 0:
        # 飞机速度 = 敌舰速度，线性方程
        if b == 0:
            return None
        t = -c / b
        if t <= 0:
            return None
    else:
        discriminant = b**2 - 4*a*c
        if discriminant < 0:
            return None
        t = (-b + math.sqrt(discriminant)) / (2*a)
        if t <= 0:
            t = (-b - math.sqrt(discriminant)) / (2*a)
            if t <= 0:
                return None

    # 拦截点
    intercept_x = nm_east + vx * t
    intercept_y = nm_north + vy * t

    # 转回 lat/lon
    intercept_lat = launch_lat + intercept_y / 60
    intercept_lon = launch_lon + intercept_x / (60 * math.cos(math.radians(28.2)))

    # 飞机航向
    heading = math.degrees(math.atan2(intercept_x, intercept_y)) % 360

    # 距离和时间
    distance_nm = aircraft_speed * t
    flight_time_min = t * 60

    return {
        "intercept_point": Position(lat=intercept_lat, lon=intercept_lon),
        "heading": int(heading),
        "distance_nm": round(distance_nm, 1),
        "flight_time_min": round(flight_time_min, 1),
    }


def calculate_fuel_budget(
    distance_nm: float,
    aircraft_type: str = "SBD",
    search_time_min: float = 0,
) -> dict:
    """计算油量预算。

    AIR-018: 往返油量 + 搜索余量

    Returns:
        dict with fuel_margin_pct, feasible, warning
    """
    fuel_rate = FUEL_RATE.get(aircraft_type, 0.6)
    search_rate = 0.125 if aircraft_type in ("SBD", "TBD") else 0.15

    fuel_outbound = fuel_rate * distance_nm
    fuel_return = fuel_rate * distance_nm
    fuel_search = search_rate * search_time_min
    fuel_reserve = 10.0

    fuel_total = fuel_outbound + fuel_return + fuel_search + fuel_reserve
    margin = 100.0 - fuel_total

    if margin < 0:
        return {
            "fuel_margin_pct": round(margin, 1),
            "feasible": False,
            "warning": "油量不足，无法返航",
        }
    elif margin < 10:
        return {
            "fuel_margin_pct": round(margin, 1),
            "feasible": True,
            "warning": "油量紧张，建议减少搜索时间",
        }
    elif margin < 20:
        return {
            "fuel_margin_pct": round(margin, 1),
            "feasible": True,
            "warning": "注意油量",
        }
    else:
        return {
            "fuel_margin_pct": round(margin, 1),
            "feasible": True,
            "warning": None,
        }


def plan_mission(
    state: GameState,
    enemy_report: dict,
    aircraft_type: str = "SBD",
    aircraft_speed: int = 150,
) -> MissionPlan:
    """创建出击规划。

    AIR-019: 参谋提出方案

    Args:
        state: 游戏状态
        enemy_report: 敌情报告 {position, course, speed, description, confidence}
        aircraft_type: 飞机型号
        aircraft_speed: 飞机速度
    """
    # 获取舰队位置
    tf = state.task_forces[0]
    launch_pos = tf.carriers[0].position

    # 敌情数据
    enemy_pos = enemy_report.get("position", {})
    enemy_lat = enemy_pos.get("lat", 0)
    enemy_lon = enemy_pos.get("lon", 0)
    enemy_course = enemy_report.get("course", 0)
    enemy_speed = enemy_report.get("speed", 20)

    # 计算拦截点
    intercept = calculate_intercept(
        enemy_lat, enemy_lon, enemy_course, enemy_speed,
        launch_pos.lat, launch_pos.lon, aircraft_speed,
    )

    if not intercept:
        # 无解
        return MissionPlan(
            id=f"plan-{state.clock.game_time.timestamp()}",
            target_position=Position(lat=enemy_lat, lon=enemy_lon),
            target_course=enemy_course,
            target_speed=enemy_speed,
            intercept_point=Position(lat=enemy_lat, lon=enemy_lon),
            intercept_heading=0,
            intercept_distance_nm=0,
            flight_time_min=0,
            fuel_margin_pct=-100,
            warnings=["飞机速度不足，无法拦截"],
            feasible=False,
            npc_briefing_data={"error": "无法拦截"},
        )

    # 计算油量
    fuel = calculate_fuel_budget(intercept["distance_nm"], aircraft_type)

    # 生成警告
    warnings = []
    if fuel["warning"]:
        warnings.append(fuel["warning"])

    # 夜间着舰检查
    arrival_hour = state.clock.game_time.hour + int(intercept["flight_time_min"] / 60) + 1
    if arrival_hour >= 19:
        warnings.append("返航时天色已暗，着舰风险增加")

    # NPC 简报数据
    npc_briefing_data = {
        "target": {
            "bearing": int(math.degrees(math.atan2(
                enemy_lon - launch_pos.lon,
                enemy_lat - launch_pos.lat
            )) % 360),
            "distance_nm": intercept["distance_nm"],
            "course": enemy_course,
            "speed_kn": enemy_speed,
            "description": enemy_report.get("description", "未知目标"),
            "confidence": enemy_report.get("confidence", "medium"),
        },
        "intercept": {
            "heading": intercept["heading"],
            "distance_nm": intercept["distance_nm"],
            "flight_time_min": intercept["flight_time_min"],
        },
        "fuel": {
            "margin_pct": fuel["fuel_margin_pct"],
            "status": "impossible" if not fuel["feasible"] else (
                "critical" if fuel["fuel_margin_pct"] < 10 else
                "tight" if fuel["fuel_margin_pct"] < 20 else
                "adequate"
            ),
            "warning": fuel["warning"],
        },
        "warnings": [{"type": "fuel", "text": w} for w in warnings],
        "feasible": fuel["feasible"],
    }

    plan = MissionPlan(
        id=f"plan-{state.clock.game_time.timestamp()}",
        target_position=Position(lat=enemy_lat, lon=enemy_lon),
        target_course=enemy_course,
        target_speed=enemy_speed,
        intercept_point=intercept["intercept_point"],
        intercept_heading=intercept["heading"],
        intercept_distance_nm=intercept["distance_nm"],
        flight_time_min=intercept["flight_time_min"],
        fuel_margin_pct=fuel["fuel_margin_pct"],
        warnings=warnings,
        feasible=fuel["feasible"],
        npc_briefing_data=npc_briefing_data,
    )

    state.mission_plans.append(plan)
    logger.info(f"[MISSION] Plan created: {plan.id} (feasible={plan.feasible})")
    return plan


def confirm_mission(state: GameState, plan_id: str) -> Optional[AirGroup]:
    """确认出击方案。

    AIR-022: 创建编组，进入 LAUNCHING
    """
    plan = _find_plan(state, plan_id)
    if not plan or not plan.feasible:
        return None

    # 创建编组
    from src.aircraft import create_air_group
    tf = state.task_forces[0]
    carrier = tf.carriers[0]

    # 选择 READY 的飞机
    ready_aircraft = [a.id for a in carrier.aircraft if a.status.value == "ready"][:10]
    if not ready_aircraft:
        return None

    ag = create_air_group(
        state, carrier.name, ready_aircraft,
        mission_type="strike", group_id=f"strike-{plan_id}",
    )
    ag.status = AirGroupStatus.LAUNCHING
    ag.plan_id = plan_id
    ag.intercept_heading = plan.intercept_heading

    logger.info(f"[MISSION] Confirmed: {plan_id} → AirGroup {ag.id}")
    return ag


def reject_mission(state: GameState, plan_id: str) -> None:
    """拒绝出击方案。

    AIR-021: 不起飞，等待新命令
    """
    plan = _find_plan(state, plan_id)
    if plan:
        plan.feasible = False
        logger.info(f"[MISSION] Rejected: {plan_id}")


def get_mission_plan(state: GameState, plan_id: str) -> Optional[dict]:
    """获取规划数据供 NPC 生成简报。"""
    plan = _find_plan(state, plan_id)
    if not plan:
        return None
    return plan.npc_briefing_data


def _find_plan(state: GameState, plan_id: str) -> Optional[MissionPlan]:
    """查找规划。"""
    for plan in state.mission_plans:
        if plan.id == plan_id:
            return plan
    return None
