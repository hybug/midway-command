"""Route models（CHART_SYSTEM.md §5.1 航线系统）。

三类航线同一数据结构不同样式：planned（玩家手绘铅笔线）/
mission（任务航线：侦察/打击）/ track（历史航迹）。
状态机：draft → active → done | cancelled。
航路点为真实经纬度（src/render/chart.py 的 hex 航线不在本层）。
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RouteKind(str, Enum):
    """航线类型（§5.1：三类航线，同一数据结构不同样式）"""
    PLANNED = "planned"   # 手绘铅笔线
    MISSION = "mission"   # 任务航线（侦察/打击）
    TRACK = "track"       # 历史航迹


class RouteStatus(str, Enum):
    """航线状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    DONE = "done"
    CANCELLED = "cancelled"


class Waypoint(BaseModel):
    """航路点（真实经纬度）"""
    lat: float
    lon: float
    eta: Optional[datetime] = None


class Route(BaseModel):
    """海图航线"""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    kind: RouteKind
    owner: str
    waypoints: list[Waypoint] = Field(default_factory=list)
    status: RouteStatus = RouteStatus.DRAFT
    progress: int = Field(default=0, ge=0)  # 下一航路点下标（N.4 航行进度）
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── 舰队短名约定（owner 统一用短名，绑定舰队时经映射还原全名）──
# O.4 收官（战区解耦）：各战区包舰队命名不同（midway "Task Force 16" vs
# 珊瑚海 "Task Force 17 (TG 17.5)"/"MO 机动部队"），映射按 theater_id 取表——
# 珊瑚海名册（TF17/TF11/TF44 + MO）提案不再报「未知舰队」。

_FLEET_SHORT_BY_THEATER: dict[str, dict[str, str]] = {
    "midway": {
        "Task Force 16": "TF16",
        "Task Force 17": "TF17",
    },
    "coral-sea": {
        "Task Force 17": "TF17",
        "Task Force 11": "TF11",
        "Task Force 44": "TF44",
        "MO 机动部队": "MO",
    },
}


def fleet_short_name(full_name: str, theater_id: str = "midway") -> str:
    """舰队全名 → 短名（战区驱动）。

    精确匹配优先，其次前缀匹配（珊瑚海剧本名带战役番号后缀，
    "Task Force 17 (TG 17.5)" 前缀即 "Task Force 17"）；未匹配回退
    全名前 12 字符（调用方再按 known_fleet_short_names 白名单校验）。
    """
    mapping = _FLEET_SHORT_BY_THEATER.get(theater_id, {})
    if full_name in mapping:
        return mapping[full_name]
    for key in sorted(mapping, key=len, reverse=True):
        if full_name.startswith(key):
            return mapping[key]
    return full_name[:12]


def known_fleet_short_names(theater_id: str) -> list[str]:
    """战区内合法舰队短名（propose_route 校验白名单）。"""
    return list(_FLEET_SHORT_BY_THEATER.get(theater_id, {}).values())


# 短名 → 全名反查（Route.owner 无战区语义，取全战区并集；entities 舰队
# 绑定走精确/前缀双匹配 _fleet_matches，跨包同名前缀安全）。
_FLEET_SHORT_TO_FULL: dict[str, str] = {
    short: full
    for mapping in _FLEET_SHORT_BY_THEATER.values()
    for full, short in mapping.items()
}


def full_fleet_name(short_name: str) -> Optional[str]:
    """舰队短名 → 全名（如 "TF16" → "Task Force 16"）；未知返回 None。"""
    return _FLEET_SHORT_TO_FULL.get(short_name)


# ── PendingRoute（航海参谋提案，N.3 审批流）──

class PendingRouteStatus(str, Enum):
    """提案状态：proposed → approved | rejected（revised 为修改后再提）"""
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISED = "revised"


class PendingRoute(BaseModel):
    """参谋航线提案（独立于 pending_suggestions 的审批流）。

    owner 用舰队短名（fleet_short_name 战区归一化值）；rationale 供命令卡展示。
    route_id 是修订链共享 id：同链多次修订（comment 回路）共用，
    批准后即 Route.id；feedback_history 记录指挥官逐轮修改意见。
    批准时经 pending_to_route 转 Route 落 state.routes。
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    route_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    owner: str
    rationale: str
    waypoints: list[Waypoint] = Field(default_factory=list)
    status: PendingRouteStatus = PendingRouteStatus.PROPOSED
    feedback_history: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


def pending_to_route(pending: PendingRoute) -> Route:
    """审批通过：PendingRoute → Route（kind=planned, status=active）。

    Route.id 沿用 pending.route_id（修订链共享），批准后 comment
    回路仍可按此 id 定位该航线。
    """
    return Route(
        id=pending.route_id,
        kind=RouteKind.PLANNED,
        owner=pending.owner,
        waypoints=pending.waypoints,
        status=RouteStatus.ACTIVE,
    )
