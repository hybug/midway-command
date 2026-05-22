"""Game state models (Pydantic v2).

GameState is the sole source of truth. All game data lives here.
NPCs can only access state through query_* functions — they never see
_hidden_actual_enemy directly.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, PrivateAttr

from src.entities import TaskForce as EntityTaskForce


class AirGroupType(str, Enum):
    FIGHTER = "fighter"
    DIVE_BOMBER = "dive"
    TORPEDO = "torpedo"


class AirGroupStatus(str, Enum):
    READY = "ready"
    LOADING = "loading"
    LAUNCHED = "launched"
    IN_FLIGHT = "in_flight"
    RETURNING = "returning"
    LANDING = "landing"


class AirGroup(BaseModel):
    type: AirGroupType
    count: int = Field(ge=0)
    status: AirGroupStatus = AirGroupStatus.READY
    fuel_pct: int = Field(default=100, ge=0, le=100)
    ammo_pct: int = Field(default=100, ge=0, le=100)
    squadron_name: Optional[str] = None
    target: Optional[str] = None


class Position(BaseModel):
    lat: float
    lon: float
    bearing: Optional[int] = Field(default=None, ge=0, le=359)
    distance_nm: Optional[int] = None
    reference: Optional[str] = None


class Carrier(BaseModel):
    name: str
    position: Position
    course: int = Field(default=240, ge=0, le=359)
    speed: int = Field(default=25, ge=0, le=35)
    air_groups: list[AirGroup] = Field(default_factory=list)
    cap_strength: int = Field(default=0, ge=0)
    damage_level: int = Field(default=0, ge=0, le=3)


class TaskForce(BaseModel):
    name: str
    carriers: list[Carrier] = Field(default_factory=list)
    course: int = Field(ge=0, le=359)
    speed: int = Field(default=25, ge=0, le=35)


class EnemyKnown(BaseModel):
    position: Position
    description: str
    confidence: str = Field(default="low")
    source: str
    reported_at: datetime


class GameClock(BaseModel):
    game_time: datetime
    tick_minutes: int = 15


class PendingSuggestion(BaseModel):
    npc: str
    action_type: str
    details: dict
    proposed_at: datetime = Field(default_factory=datetime.utcnow)


class ScoutMission(BaseModel):
    """一次侦察任务"""
    id: str
    direction: str  # northwest / north / east / etc.
    heading: int  # 侦察机航向 (0-359)
    launched_at: datetime
    eta_minutes: int = 60
    status: str = "in_flight"  # in_flight / completed
    search_bearing_min: int = 0
    search_bearing_max: int = 0
    search_distance_nm: int = 200
    aircraft_count: int = 4


class PendingReport(BaseModel):
    """延迟到达的侦察报告。检测成功后存入，到达时间后才转为 EnemyKnown。"""
    scout_id: str
    detected_at: datetime
    arrive_at: datetime  # 到达时间 = detected_at + delay_minutes
    # 真实数据（内部用）
    real_bearing: float
    real_distance_nm: float
    real_carrier_count: int
    # 失真后的数据（给玩家看）
    reported_bearing: int
    reported_distance_nm: int
    reported_carrier_count: int
    confidence: str = "medium"


class TurnType(str, Enum):
    NORMAL = "normal"      # 3 AP
    CRITICAL = "critical"  # 5 AP
    EMERGENCY = "emergency"  # 2 AP


class GameState(BaseModel):
    clock: GameClock
    task_forces: list[TaskForce] = Field(default_factory=list)
    known_enemy: list[EnemyKnown] = Field(default_factory=list)
    incoming_messages: list[str] = Field(default_factory=list)
    pending_suggestions: list[PendingSuggestion] = Field(default_factory=list)
    active_scouts: list[ScoutMission] = Field(default_factory=list)
    pending_reports: list[PendingReport] = Field(default_factory=list)
    # Action Points
    turn_type: TurnType = TurnType.NORMAL
    action_points: int = Field(default=3, ge=0)
    max_action_points: int = Field(default=3, ge=0)
    _hidden_actual_enemy: Optional[list[dict]] = PrivateAttr(default=None)
    _enemy_fleet: Optional[EntityTaskForce] = PrivateAttr(default=None)
