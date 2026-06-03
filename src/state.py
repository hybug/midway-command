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


# ── Aircraft Entity System ──

class AircraftType(str, Enum):
    """飞机型号"""
    SBD = "SBD"    # 俯冲轰炸机（侦察+攻击）
    TBD = "TBD"    # 鱼雷机（攻击）
    VF = "VF"      # 战斗机（CAP+护航）


class AircraftStatus(str, Enum):
    """飞机状态"""
    READY = "ready"             # 待命
    LOADING = "loading"         # 装弹/加油
    IN_FLIGHT = "in_flight"     # 飞行中
    RETURNING = "returning"     # 返航
    LANDING = "landing"         # 着舰中
    MAINTENANCE = "maintenance" # 维修中


class Aircraft(BaseModel):
    """单架飞机实体"""
    id: str                          # "SBD-VB6-01"
    type: AircraftType
    squadron: str                    # "VB-6"
    carrier: str                     # "Enterprise"
    status: AircraftStatus = AircraftStatus.READY
    fuel_pct: float = 100.0          # 0-100
    ammo_pct: float = 100.0          # 0-100
    ordnance: str = "none"           # "500lb_bomb" / "torpedo" / "none"
    assigned_mission: Optional[str] = None  # 任务ID
    # 关键飞机标记（历史人物）
    is_key_pilot: bool = False
    pilot_name: Optional[str] = None


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
    air_groups: list[AirGroup] = Field(default_factory=list)  # 向后兼容
    aircraft: list[Aircraft] = Field(default_factory=list)    # 新：具体飞机列表
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


class SearchPattern(str, Enum):
    """搜索模式"""
    SECTOR = "sector"       # 扇形搜索：窄/深/快/高概率
    PARALLEL = "parallel"   # 平行搜索：宽/浅/中/低概率
    GRID = "grid"           # 方格搜索：局部/深/慢/最高概率


class ScoutPhase(str, Enum):
    """侦察任务阶段"""
    PREPARING = "preparing"     # 起飞准备 (15分钟)
    OUTBOUND = "outbound"       # 飞往搜索区域
    SEARCHING = "searching"     # 搜索中
    RETURNING = "returning"     # 返航中
    LANDED = "landed"           # 着舰
    DIVERTED = "diverted"       # 转降中途岛
    DITCHED = "ditched"         # 海面迫降
    LOST = "lost"               # 损失（燃油耗尽/被击落）


class ScoutMission(BaseModel):
    """一次侦察任务（含燃油和返航追踪）"""
    id: str
    direction: str  # northwest / north / east / etc.
    heading: int  # 侦察机航向 (0-359)
    launched_at: datetime
    eta_minutes: int = 60
    status: str = "in_flight"  # in_flight / completed（向后兼容）
    search_bearing_min: int = 0
    search_bearing_max: int = 0
    search_distance_nm: int = 200
    aircraft_count: int = 4
    search_pattern: SearchPattern = SearchPattern.SECTOR

    # 阶段追踪
    phase: ScoutPhase = ScoutPhase.PREPARING
    phase_started_at: Optional[datetime] = None

    # 燃油追踪
    fuel_pct: float = 100.0
    fuel_burn_per_nm: float = 0.8      # 每海里消耗百分比
    fuel_burn_per_search_min: float = 0.4  # 每搜索分钟消耗百分比

    # 返航信息
    return_eta_minutes: int = 0
    return_heading: int = 0

    # 损失追踪
    aircraft_lost: int = 0
    loss_reasons: list[str] = Field(default_factory=list)

    # 飞机引用
    aircraft_ids: list[str] = Field(default_factory=list)

    # 侦察机当前位置（用于地图显示）
    position: Optional[Position] = None


class AircraftLoss(BaseModel):
    """单架飞机损失记录"""
    scout_id: str
    aircraft_number: int
    reason: str  # fuel_exhausted / ditched / shot_down / diverted_midway / weather
    time: datetime


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
    aircraft_losses: list[AircraftLoss] = Field(default_factory=list)
    # Action Points
    turn_type: TurnType = TurnType.NORMAL
    action_points: int = Field(default=3, ge=0)
    max_action_points: int = Field(default=3, ge=0)
    _hidden_actual_enemy: Optional[list[dict]] = PrivateAttr(default=None)
    _enemy_fleet: Optional[EntityTaskForce] = PrivateAttr(default=None)
