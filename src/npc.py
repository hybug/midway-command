"""NPC 系统 — 信息过滤、LLM 数据准备。

职责：
- 根据 NPC 信息权限过滤 GameState
- 准备 LLM 数据包
- NPC 参数查询

§8: NPC 系统
"""
import logging
from typing import Optional

from src.state import GameState
from src.npc_config import NPC_REGISTRY, NPCConfig

logger = logging.getLogger("midway.npc")


# ── 信息权限定义（§8.2.2）──

INFO_SCOPE_MAP = {
    "fleet_global": ["task_forces", "clock", "action_points", "turn_type"],
    "own_carrier": ["task_forces"],  # 需要 carrier_filter 进一步过滤
    "air_groups": ["task_forces"],  # 只看 air_groups 字段
    "known_enemy": ["known_enemy"],
    "incoming_msgs": ["incoming_messages"],
    "pending_reports": ["pending_reports"],
    "active_scouts": ["active_scouts"],
}


def filter_state_for_npc(state: GameState, npc_name: str) -> dict:
    """根据 NPC 信息权限过滤 GameState（§8.5.1）

    Args:
        state: 游戏状态
        npc_name: NPC 名称

    Returns:
        过滤后的 dict
    """
    npc_config = NPC_REGISTRY.get(npc_name)
    if not npc_config:
        return {}

    filtered = {}

    for scope_key in npc_config.info_scope:
        if scope_key == "fleet_global":
            filtered["task_forces"] = _filter_task_forces(state, npc_config)
            filtered["clock"] = {
                "game_time": state.clock.game_time.isoformat(),
                "tick_minutes": state.clock.tick_minutes,
            }
            filtered["action_points"] = state.action_points
            filtered["turn_type"] = state.turn_type.value

        elif scope_key == "own_carrier":
            filtered["task_forces"] = _filter_task_forces(state, npc_config)

        elif scope_key == "air_groups":
            if "task_forces" not in filtered:
                filtered["task_forces"] = _filter_task_forces(state, npc_config)

        elif scope_key == "known_enemy":
            filtered["known_enemy"] = [
                {
                    "description": e.description,
                    "confidence": e.confidence,
                    "source": e.source,
                    "reported_at": e.reported_at.isoformat(),
                }
                for e in state.known_enemy
            ]

        elif scope_key == "incoming_msgs":
            filtered["incoming_messages"] = list(state.incoming_messages)

        elif scope_key == "pending_reports":
            filtered["pending_reports"] = [
                {
                    "scout_id": r.scout_id,
                    "arrive_at": r.arrive_at.isoformat(),
                    "reported_bearing": r.reported_bearing,
                    "reported_distance_nm": r.reported_distance_nm,
                    "confidence": r.confidence,
                }
                for r in state.pending_reports
            ]

        elif scope_key == "active_scouts":
            filtered["active_scouts"] = [
                {
                    "id": s.id,
                    "direction": s.direction,
                    "phase": s.phase.value,
                    "fuel_pct": s.fuel_pct,
                }
                for s in state.active_scouts
            ]

    # actual_enemy 永远不传给 NPC（§8.4 NPC-007）
    # 不需要特别处理，因为 actual_enemy 不在任何 scope_key 中

    return filtered


def get_npc_params(npc_name: str) -> Optional[dict]:
    """获取 NPC 参数（§8.6）"""
    npc_config = NPC_REGISTRY.get(npc_name)
    if not npc_config:
        return None

    return {
        "name": npc_config.name,
        "role": npc_config.role,
        "autonomy": npc_config.autonomy,
        "risk_tolerance": npc_config.risk_tolerance,
        "initiative": npc_config.initiative,
        "competence": npc_config.competence,
    }


def prepare_llm_data(
    state: GameState,
    npc_name: str,
    context: str = "",
    recent_events: list[str] = None,
) -> dict:
    """准备 LLM 数据包（§8.5.2）

    Args:
        state: 游戏状态
        npc_name: NPC 名称
        context: 当前触发事件
        recent_events: 最近发生的事件

    Returns:
        LLM 数据包
    """
    npc_config = NPC_REGISTRY.get(npc_name)
    if not npc_config:
        return {}

    filtered_state = filter_state_for_npc(state, npc_name)

    return {
        "role": npc_config.name,
        "personality": {
            "autonomy": npc_config.autonomy,
            "risk_tolerance": npc_config.risk_tolerance,
            "initiative": npc_config.initiative,
            "competence": npc_config.competence,
        },
        "info_scope": npc_config.info_scope,
        "filtered_state": filtered_state,
        "context": context,
        "recent_events": recent_events or [],
    }


def get_npc_list() -> list[dict]:
    """获取所有 NPC 列表（§8.6）"""
    return [
        {
            "name": cfg.name,
            "role": cfg.role,
            "autonomy": cfg.autonomy,
            "risk_tolerance": cfg.risk_tolerance,
            "initiative": cfg.initiative,
            "competence": cfg.competence,
        }
        for cfg in NPC_REGISTRY.values()
    ]


# ── 内部辅助函数 ──

def _filter_task_forces(state: GameState, npc_config: NPCConfig) -> list[dict]:
    """过滤 task_forces 数据。"""
    result = []
    for tf in state.task_forces:
        tf_data = {
            "name": tf.name,
            "course": tf.course,
            "speed": tf.speed,
            "carriers": [],
        }

        for carrier in tf.carriers:
            # 舰长只看自己的航母
            if npc_config.carrier_filter and carrier.name != npc_config.carrier_filter:
                continue

            carrier_data = {
                "name": carrier.name,
                "position": {
                    "lat": carrier.position.lat,
                    "lon": carrier.position.lon,
                },
                "course": carrier.course,
                "speed": carrier.speed,
                "damage_level": carrier.damage_level,
            }

            # 添加 air_groups 信息
            if "air_groups" in npc_config.info_scope or "fleet_global" in npc_config.info_scope:
                carrier_data["air_groups"] = [
                    {
                        "type": ag.type.value,
                        "count": ag.count,
                        "status": ag.status.value,
                        "fuel_pct": ag.fuel_pct,
                        "ammo_pct": ag.ammo_pct,
                    }
                    for ag in carrier.air_groups
                ]

            tf_data["carriers"].append(carrier_data)

        result.append(tf_data)

    return result
