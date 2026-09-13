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
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── 舰队短名约定（owner 统一用短名，绑定舰队时经映射还原全名）──

FLEET_SHORT: dict[str, str] = {
    "Task Force 16": "TF16",
    "Task Force 17": "TF17",
}

_FLEET_SHORT_TO_FULL = {v: k for k, v in FLEET_SHORT.items()}


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

    owner 用舰队短名（FLEET_SHORT 值）；rationale 供命令卡展示。
    批准时经 pending_to_route 转 Route 落 state.routes。
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    owner: str
    rationale: str
    waypoints: list[Waypoint] = Field(default_factory=list)
    status: PendingRouteStatus = PendingRouteStatus.PROPOSED
    created_at: datetime = Field(default_factory=datetime.utcnow)


def pending_to_route(pending: PendingRoute) -> Route:
    """审批通过：PendingRoute → Route（kind=planned, status=active）。"""
    return Route(
        kind=RouteKind.PLANNED,
        owner=pending.owner,
        waypoints=pending.waypoints,
        status=RouteStatus.ACTIVE,
    )
