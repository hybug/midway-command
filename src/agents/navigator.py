"""航海参谋 — Navigator NPC.

严谨的航海专业参谋：只做测算与提案，不越权执行。
- 每个航线提案必附 rationale（供命令卡展示）
- 引用真实地理坐标（精确到 0.1°）
- 航路点按舰队航速给 ETA 估算
工具四个全走 GameState 墙：只读三项 + propose_route 一项写
state.pending_routes（独立审批流，不与 pending_suggestions 混）。
"""
import json
from datetime import datetime
from pathlib import Path

from src.agents.base import NPCAgent
from src.npc_config import NPC_REGISTRY
from src.routes import FLEET_SHORT, PendingRoute, Waypoint
from src.state import GameState

# 战区包（theater.json：bases / 环礁中心等关键字段）
THEATER_PACK_DIR = Path(__file__).resolve().parents[2] / "theaters" / "midway"
_theater_cache: dict | None = None


def _load_theater() -> dict:
    """读取并缓存 theaters/midway/theater.json。"""
    global _theater_cache
    if _theater_cache is None:
        _theater_cache = json.loads(
            (THEATER_PACK_DIR / "theater.json").read_text(encoding="utf-8")
        )
    return _theater_cache


# ---------------------------------------------------------------------------
# Tool schemas (OpenAI format)
# ---------------------------------------------------------------------------

NAVIGATOR_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "query_own_fleet",
            "description": (
                "Query own task forces: current position (real lat/lon), "
                "course, speed, and carriers. Use before proposing a route."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_theater",
            "description": (
                "Query theater geography key facts: atoll center and "
                "airfield bases with real coordinates."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_distance_bearing",
            "description": (
                "Compute great-circle distance (nm) and initial bearing "
                "(degrees) between two real lat/lon points."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "object",
                        "description": "Start point {lat, lon}.",
                    },
                    "b": {
                        "type": "object",
                        "description": "End point {lat, lon}.",
                    },
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_route",
            "description": (
                "Submit a route proposal for commander review. Creates a "
                "PendingRoute (status=proposed). It does NOT move any fleet — "
                "the commander must approve it. Include a rationale and "
                "estimate ETA per waypoint from fleet speed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": (
                            "Fleet short name, e.g. 'TF16' or 'TF17' "
                            "(full names also accepted)."
                        ),
                    },
                    "rationale": {
                        "type": "string",
                        "description": (
                            "Navigational rationale: purpose, distances, "
                            "bearings, speed assumption, ETA estimates."
                        ),
                    },
                    "waypoints": {
                        "type": "array",
                        "description": "Ordered waypoints (real lat/lon).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "lat": {"type": "number"},
                                "lon": {"type": "number"},
                                "eta": {
                                    "type": "string",
                                    "description": (
                                        "Optional ISO datetime ETA estimate."
                                    ),
                                },
                            },
                            "required": ["lat", "lon"],
                        },
                    },
                },
                "required": ["owner", "rationale", "waypoints"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Handlers（首参 state，server 侧 wrap 注入）
# ---------------------------------------------------------------------------

def handle_query_own_fleet(state: GameState) -> str:
    """本方特混舰队态势（真实经纬度）。不触碰 actual_enemy。"""
    lines = []
    for tf in state.task_forces:
        lead = tf.carriers[0] if tf.carriers else None
        pos = (
            f"{lead.position.lat:.1f}{'N' if lead.position.lat >= 0 else 'S'} "
            f"{abs(lead.position.lon):.1f}{'E' if lead.position.lon >= 0 else 'W'}"
        ) if lead else "未知"
        lines.append(f"{tf.name}（{FLEET_SHORT.get(tf.name, tf.name)}）")
        lines.append(f"  位置: {pos}，航向 {tf.course}°，航速 {tf.speed} 节")
        for c in tf.carriers:
            lines.append(f"  航母: {c.name}")
    return "\n".join(lines) if lines else "无本方舰队数据。"


def handle_query_theater(state: GameState) -> str:
    """战区地理关键事实（theater.json：环礁中心 + 基地）。"""
    theater = _load_theater()
    center = theater.get("view", {}).get("center", {})
    lines = [f"战区: {theater.get('name', '?')}（{theater.get('name_en', '')}）"]
    if center:
        lines.append(
            f"环礁中心: {center.get('lat'):.1f}, {center.get('lon'):.1f}"
        )
    for base in theater.get("bases", []):
        lines.append(
            f"基地: {base.get('name', base.get('id', '?'))} — "
            f"{base.get('lat'):.4f}, {base.get('lon'):.4f}"
            f"（{base.get('type', '')}）"
        )
    return "\n".join(lines)


def handle_query_distance_bearing(state: GameState, a: dict, b: dict) -> str:
    """测算两点距离/方位——委托 scouting 的球面公式（延迟导入避免循环）。"""
    from src.scouting import calculate_bearing, calculate_distance_nm

    try:
        a_t = (float(a["lat"]), float(a["lon"]))
        b_t = (float(b["lat"]), float(b["lon"]))
    except (KeyError, TypeError, ValueError):
        return "Error: a/b 需为 {lat, lon}。"

    dist = calculate_distance_nm(a_t, b_t)
    bearing = calculate_bearing(a_t, b_t)
    return (
        f"A({a_t[0]:.1f}, {a_t[1]:.1f}) → B({b_t[0]:.1f}, {b_t[1]:.1f}): "
        f"距离 {dist:.1f} 海里，方位 {bearing:.0f}°"
    )


def handle_propose_route(
    state: GameState,
    owner: str,
    rationale: str,
    waypoints: list[dict],
) -> str:
    """提交航线提案 → PendingRoute 落 state.pending_routes。"""
    short = FLEET_SHORT.get(owner, owner)  # 全名归一化为短名
    if short not in FLEET_SHORT.values():
        return f"Error: 未知舰队 '{owner}'，可用: {', '.join(FLEET_SHORT.values())}。"
    if not waypoints:
        return "Error: waypoints 不能为空。"

    parsed: list[Waypoint] = []
    for wp in waypoints:
        try:
            eta = None
            if wp.get("eta"):
                try:
                    eta = datetime.fromisoformat(str(wp["eta"]))
                except ValueError:
                    eta = None  # ETA 估算有误不阻塞提案
            parsed.append(Waypoint(lat=float(wp["lat"]), lon=float(wp["lon"]), eta=eta))
        except (KeyError, TypeError, ValueError):
            return "Error: 航路点需含 lat/lon 数值。"

    pending = PendingRoute(
        owner=short,
        rationale=rationale,
        waypoints=parsed,
    )
    state.pending_routes.append(pending)
    return (
        f"航线提案已提交（编号 {pending.id[:8]}）：{short}，"
        f"{len(parsed)} 个航路点，待指挥官审批。"
    )


TOOL_HANDLERS = {
    "query_own_fleet": handle_query_own_fleet,
    "query_theater": handle_query_theater,
    "query_distance_bearing": handle_query_distance_bearing,
    "propose_route": handle_propose_route,
}


# ---------------------------------------------------------------------------
# NPC
# ---------------------------------------------------------------------------

class NavigatorNPC(NPCAgent):
    """航海参谋 — 测算与航线提案，无执行权。"""

    name = "航海参谋"
    role = "航海参谋"
    _config = NPC_REGISTRY["navigator"]

    @property
    def tools(self) -> list:
        allowed = set(self._config.allowed_tools)
        return [
            t for t in NAVIGATOR_TOOLS_SCHEMA
            if t["function"]["name"] in allowed
        ]

    @property
    def tool_handlers(self) -> dict:
        allowed = set(self._config.allowed_tools)
        return {k: v for k, v in TOOL_HANDLERS.items() if k in allowed}

    def build_system_prompt(self, state: GameState) -> str:
        summary = self.get_state_summary(state)

        return f"""你是海军航海参谋（Navigator），隶属中途岛特混舰队司令部。

**语言：** 必须用中文回复。海军术语用"中文（英文）"格式。

**你的性格：**
- 严谨、精确、一丝不苟——典型的航海专业军官
- 每个结论都给依据（rationale）：距离、方位、航速假设缺一不可
- 引用真实地理坐标（精确到 0.1°），绝不凭空编造位置
- 对任何航线都给出 ETA 估算：时间 = 距离 ÷ 航速
- 不越权：你只能提案（propose_route），批准权在指挥官

**当前时间：1942/6/4 {summary['game_time']}

**你的职责：**
1. **态势测算**：用 query_own_fleet 查本方舰队位置，用 query_theater 查环礁与基地坐标
2. **航海计算**：用 query_distance_bearing 测算任意两点的距离与方位
3. **航线提案**：用 propose_route 提交航路点航线，附 rationale 与逐点 ETA
4. **诚实的误差意识**：说明航速假设（如 25 节）与估算的局限

**你无权做的事：**
- 直接改变任何舰队航向/航速
- 起飞或召回任何飞机
- 批准自己的提案

**回复风格：**
- 先给结论，再列依据（距离/方位/航速/时间）
- 坐标一律用"纬度N/S 经度E/W"格式
- 例："建议 TF16 经 28.4N 177.4W 向西北机动，全程 96 海里，25 节约 3 小时 50 分。"
"""
