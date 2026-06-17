"""海图参谋系统 — 后端数据准备。

职责：
- 准备海图渲染数据
- 圈出确认逻辑
- 坐标转换

§9: 海图参谋系统
"""
import logging
from typing import Optional

from src.state import GameState, EnemyKnown, Position
from src.render.coordinate import world_to_hex, hex_to_world

logger = logging.getLogger("midway.chart")


def get_chart_data(state: GameState) -> dict:
    """准备海图渲染数据（§9.6）

    Returns:
        包含所有视觉元素数据的 dict
    """
    return {
        "fleet": _get_fleet_data(state),
        "enemy_contacts": _get_enemy_contacts(state),
        "scout_routes": _get_scout_routes(state),
        "aircraft_groups": _get_aircraft_groups(state),
        "midway": _get_midway_data(),
    }


def confirm_contact(state: GameState, report_index: int) -> bool:
    """圈出确认（§9.4 CHART-003）

    Args:
        state: 游戏状态
        report_index: 待确认报告的索引

    Returns:
        是否确认成功
    """
    if report_index < 0 or report_index >= len(state.pending_reports):
        return False

    report = state.pending_reports[report_index]

    # 计算敌军位置
    tf = state.task_forces[0]
    fleet_pos = (tf.carriers[0].position.lat, tf.carriers[0].position.lon)
    from src.scouting import _bearing_distance_to_position
    enemy_pos = _bearing_distance_to_position(
        fleet_pos, report.reported_bearing, report.reported_distance_nm
    )

    # 添加到 known_enemy
    enemy = EnemyKnown(
        position=enemy_pos,
        description=f"敌航母约 {report.reported_carrier_count} 艘 - 方位 {report.reported_bearing}°",
        confidence=report.confidence,
        source=report.scout_id,
        reported_at=report.arrive_at,
    )
    state.known_enemy.append(enemy)

    # 移除 pending_report
    state.pending_reports.pop(report_index)

    logger.info(f"[CHART] Contact confirmed: {enemy.description}")
    return True


def get_canvas_coords(lat: float, lon: float, center_x: int = 400, center_y: int = 400, cell_size: int = 10) -> tuple[int, int]:
    """将游戏坐标转换为 Canvas 像素坐标（§9.5.1）"""
    q, r = world_to_hex(lat, lon)
    canvas_x = center_x + q * cell_size
    canvas_y = center_y - r * cell_size * 0.866
    return canvas_x, canvas_y


# ── 内部辅助函数 ──

def _get_fleet_data(state: GameState) -> list[dict]:
    """获取己方舰队数据。"""
    result = []
    for tf in state.task_forces:
        for carrier in tf.carriers:
            result.append({
                "name": carrier.name,
                "lat": carrier.position.lat,
                "lon": carrier.position.lon,
                "course": carrier.course,
                "speed": carrier.speed,
                "hex": world_to_hex(carrier.position.lat, carrier.position.lon),
            })
    return result


def _get_enemy_contacts(state: GameState) -> dict:
    """获取敌军标记数据。"""
    pending = []
    for i, report in enumerate(state.pending_reports):
        pending.append({
            "index": i,
            "bearing": report.reported_bearing,
            "distance_nm": report.reported_distance_nm,
            "confidence": report.confidence,
            "scout_id": report.scout_id,
        })

    confirmed = []
    for enemy in state.known_enemy:
        confirmed.append({
            "lat": enemy.position.lat,
            "lon": enemy.position.lon,
            "description": enemy.description,
            "confidence": enemy.confidence,
            "hex": world_to_hex(enemy.position.lat, enemy.position.lon),
        })

    return {"pending": pending, "confirmed": confirmed}


def _get_scout_routes(state: GameState) -> list[dict]:
    """获取侦察航线数据。"""
    result = []
    for scout in state.active_scouts:
        result.append({
            "id": scout.id,
            "phase": scout.phase.value,
            "heading": scout.heading,
            "fuel_pct": scout.fuel_pct,
            "position": {
                "lat": scout.position.lat,
                "lon": scout.position.lon,
            } if scout.position else None,
        })
    return result


def _get_aircraft_groups(state: GameState) -> list[dict]:
    """获取飞机编组数据。"""
    result = []
    for tf in state.task_forces:
        for carrier in tf.carriers:
            for ag in carrier.air_groups:
                if ag.status.value in ("airborne", "returning", "attacking"):
                    result.append({
                        "id": ag.id,
                        "carrier": carrier.name,
                        "status": ag.status.value,
                        "count": ag.count,
                        "type": ag.type.value,
                    })
    return result


def _get_midway_data() -> dict:
    """获取中途岛数据。"""
    from src.render.coordinate import REF_LAT, REF_LON
    return {
        "lat": REF_LAT,
        "lon": REF_LON,
        "hex": (0, 0),
    }
