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
