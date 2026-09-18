"""Game state models (Pydantic v2).

GameState is the sole source of truth. All game data lives here.
NPCs can only access state through query_* functions — they never see
actual_enemy directly.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, PrivateAttr
from src.entities import TaskForce as EntityTaskForce
from src.intel.models import (
    ApprovedPlot,
    BeliefState,
    CommanderDecision,
    ContactHypothesis,
    Evidence,
    EvidenceConflict,
    IntelAuditEntry,
    IntelBrief,
    IntelWorkItem,
    MessageEnvelope,
    NPCClaim,
    NPCAssessment,
    PlotProposal,
    SourceObservation,
)
from src.intel.rng import CheckRecord
from src.intel.reasoning import ToolCallRecord
from src.cognition.models import (
    JudgmentAuditRecord,
    JudgmentMemory,
    JudgmentResult,
    JudgmentTask,
)
from src.routes import PendingRoute, Route


class GamePhase(str, Enum):
    """游戏生命周期"""
    PLAYING = "playing"
    GAME_OVER = "game_over"


class AirGroupType(str, Enum):
    FIGHTER = "fighter"
    DIVE_BOMBER = "dive"
    TORPEDO = "torpedo"


class AirGroupStatus(str, Enum):
    """编组状态（完整生命周期）"""
    READY = "ready"
    PLANNING = "planning"
    LAUNCHING = "launching"
    AIRBORNE = "airborne"
    ATTACKING = "attacking"
    RETURNING = "returning"
    REFUELING = "refueling"
    REARMING = "rearming"
    LOST = "lost"


class AirGroup(BaseModel):
    id: Optional[str] = None
    type: AirGroupType
    count: int = Field(ge=0)
    status: AirGroupStatus = AirGroupStatus.READY
    fuel_pct: int = Field(default=100, ge=0, le=100)
    ammo_pct: int = Field(default=100, ge=0, le=100)
    squadron_name: Optional[str] = None
    target: Optional[str] = None
    carrier_name: Optional[str] = None
    plan_id: Optional[str] = None
    mission_type: Optional[str] = None
    launched_at: Optional[datetime] = None
    intercept_heading: Optional[int] = None


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
    LOST = "lost"               # 损失


class Aircraft(BaseModel):
    """单架飞机实体"""
    id: str                          # "SBD-VB6-01"
    type: AircraftType
    squadron: str                    # "VB-6"
    carrier: str                     # "Enterprise"
    status: AircraftStatus = AircraftStatus.READY
    fuel_pct: float = 100.0          # 0-100
    ammo_pct: float = 100.0          # 0-100
    hp: int = 3                      # 生命值（SBD/TBD=3, VF=3）
    group_id: Optional[str] = None   # 所属编组ID
    losses: int = 0                  # 已损失架数
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

    def to_tuple(self) -> tuple:
        return (self.lat, self.lon)


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
    """搜索模式（历史参考）"""
    SECTOR = "sector"               # 扇形搜索（日军中途岛用的模式）
    EXPANDING_SQUARE = "expanding_square"  # 扩展方形（位置大致已知时）
    PARALLEL = "parallel"           # 平行搜索（大范围无目标信息）


class ScoutPhase(str, Enum):
    """侦察任务阶段"""
    PREPARING = "preparing"     # 起飞准备
    OUTBOUND = "outbound"       # 飞往搜索区域
    SEARCHING = "searching"     # 搜索中
    RETURNING = "returning"     # 返航中
    LANDED = "landed"           # 着舰
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

    # 航线（hex坐标列表）
    route: list[tuple[int, int]] = Field(default_factory=list)
    route_index: int = 0

    # 阶段追踪
    phase: ScoutPhase = ScoutPhase.PREPARING
    phase_started_at: Optional[datetime] = None

    # 燃油追踪 (SBD Dauntless: 200gal tank, 1.2 gal/nm cruise, 25 gal/hr search)
    fuel_pct: float = 100.0
    fuel_burn_per_nm: float = 0.6      # 1.2 gal/nm ÷ 200 gal = 0.6%/nm
    fuel_burn_per_search_min: float = 0.125  # 25 gal/hr ÷ 200 gal = 0.125%/min

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

    # 检测结果
    detections: list[dict] = Field(default_factory=list)


class AircraftLoss(BaseModel):
    """单架飞机损失记录"""
    scout_id: str
    aircraft_number: int
    reason: str  # fuel_exhausted / ditched / shot_down / diverted_midway / weather
    time: datetime


class MissionPlan(BaseModel):
    """出击规划（拦截点、油量、警告）"""
    id: str
    target_position: Position
    target_course: int = Field(ge=0, le=359)
    target_speed: int = Field(ge=0)
    intercept_point: Position
    intercept_heading: int = Field(ge=0, le=359)
    intercept_distance_nm: float = Field(ge=0)
    flight_time_min: float = Field(ge=0)
    fuel_margin_pct: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    feasible: bool = True
    npc_briefing_data: dict = Field(default_factory=dict)


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
    game_phase: GamePhase = GamePhase.PLAYING
    task_forces: list[TaskForce] = Field(default_factory=list)
    known_enemy: list[EnemyKnown] = Field(default_factory=list)
    actual_enemy: list[dict] = Field(default_factory=list)
    incoming_messages: list[str] = Field(default_factory=list)
    pending_suggestions: list[PendingSuggestion] = Field(default_factory=list)
    active_scouts: list[ScoutMission] = Field(default_factory=list)
    pending_reports: list[PendingReport] = Field(default_factory=list)
    aircraft_losses: list[AircraftLoss] = Field(default_factory=list)
    mission_plans: list[MissionPlan] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)  # 海图航线（CHART_SYSTEM.md §5.1）
    pending_routes: list[PendingRoute] = Field(default_factory=list)  # 航海参谋提案（N.3 审批流）
    # Action Points
    turn_type: TurnType = TurnType.NORMAL
    action_points: int = Field(default=3, ge=0)
    max_action_points: int = Field(default=3, ge=0)
    enemy_fleet: Optional[EntityTaskForce] = Field(default=None)
    # ── S2.1 可复现随机性（RNGService 种子 + 全量检定记录，回放用）──
    rng_seed: int = 20260604
    check_records: list[CheckRecord] = Field(default_factory=list)
    # ── S2.2 情报档案（追加制：电文/证据/判断声明/接触/信念/审计）──
    messages: list[MessageEnvelope] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    claims: list[NPCClaim] = Field(default_factory=list)
    contacts: list[ContactHypothesis] = Field(default_factory=list)
    beliefs: list[BeliefState] = Field(default_factory=list)
    intel_audit: list[IntelAuditEntry] = Field(default_factory=list)
    intel_id_counters: dict[str, int] = Field(default_factory=dict)
    # ── S2.3 纵切对象（规则侧观测 + 参谋工作流）──
    observations: list[SourceObservation] = Field(default_factory=list)  # 规则侧，禁止下发
    intel_work_items: list[IntelWorkItem] = Field(default_factory=list)
    assessments: list[NPCAssessment] = Field(default_factory=list)
    intel_briefs: list[IntelBrief] = Field(default_factory=list)
    # ── S2.4 标图审批（提案/决议/正式标图）──
    plot_proposals: list[PlotProposal] = Field(default_factory=list)
    commander_decisions: list[CommanderDecision] = Field(default_factory=list)
    approved_plots: list[ApprovedPlot] = Field(default_factory=list)
    # ── S2.5 冲突登记 ──
    evidence_conflicts: list[EvidenceConflict] = Field(default_factory=list)
    # ── S2.7 推理工具调用审计（复盘可查参谋是否用过工具）──
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    # ── S3.0 参谋认知（判断任务/结果/记忆/审计；记忆按 actor 隔离，D7/D8）──
    judgment_tasks: list[JudgmentTask] = Field(default_factory=list)
    judgment_results: list[JudgmentResult] = Field(default_factory=list)
    judgment_memories: list[JudgmentMemory] = Field(default_factory=list)
    judgment_audits: list[JudgmentAuditRecord] = Field(default_factory=list)
    # ── S8 UI.4 人物化报告（result_id → 渲染文本；不改写结构化结果）──
    judgment_reports: dict[str, str] = Field(default_factory=dict)
