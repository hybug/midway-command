"""S2 情报数据模型（Phase S2.2，§6.1–§6.5 / §M2.6.1）。

追加制纪律（D4）：电文、证据、判断声明一经落档不得原地改写——
勘误/替代/否定通过新建记录并引用旧记录实现；状态变化经 status_history
与 state.intel_audit 追加留痕。

防泄漏边界：本模块模型不含规则侧真值字段（actual_enemy / internal_truth_ref），
真值只存在于规则侧（SourceObservation，见 S2.3）。
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.intel.contracts import (
    ActorRole,
    CommCondition,
    ContactStatus,
    EvidenceStatus,
    MessageStatus,
    SourceType,
    WorkPriority,
)


class StatusChange(BaseModel):
    """状态变化留痕（追加式）。"""
    at: datetime
    from_status: str
    to_status: str
    by: str
    reason: str = ""


class MessageEnvelope(BaseModel):
    """电文信封（§6.2）。落档后字段不可覆盖，状态机推进外只追加历史。"""
    id: str = ""
    sender_id: str
    sender_call_sign: str = ""
    recipient_ids: list[str] = Field(default_factory=list)
    priority: WorkPriority = WorkPriority.ROUTINE
    classification: str = "SECRET"
    channel: str = "TBS"
    message_kind: str = "scout_report"   # scout_report/correction/friendly_report/status
    observed_at: Optional[datetime] = None
    filed_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    condition: CommCondition = CommCondition.COMPLETE
    status: MessageStatus = MessageStatus.DRAFT
    supersedes_message_id: Optional[str] = None   # 勘误引用链
    raw_text: str = ""
    generated_by_npc: Optional[str] = None        # 撰写本电文的 NPC actor id
    observation_id: Optional[str] = None          # 规则侧谱系 id（非真值）
    routed_to: list[str] = Field(default_factory=list)
    fields: dict = Field(default_factory=dict)    # 电文要素（失真后的报告值：bearing/distance_nm/count/classification）
    transit_eta: Optional[datetime] = None        # 通信检定预估到达时刻（传输中消费）
    status_history: list[StatusChange] = Field(default_factory=list)


class Evidence(BaseModel):
    """证据账本条目（§6.3）。不可变：登记后只能被替代/勘误/否定（新记录）。"""
    id: str = ""
    message_id: str
    source_id: str
    source_type: SourceType = SourceType.CARRIER_SCOUT
    claim_scope: str = "contact"
    observed_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    source_reliability: float = Field(default=0.6, ge=0.0, le=1.0)
    identity_precision: float = Field(default=0.5, ge=0.0, le=1.0)
    position_precision: float = Field(default=0.5, ge=0.0, le=1.0)
    count_precision: float = Field(default=0.5, ge=0.0, le=1.0)
    corroboration: list[str] = Field(default_factory=list)   # 印证证据 id（追加）
    freshness_at: Optional[datetime] = None
    access_policy: list[ActorRole] = Field(default_factory=list)
    status: EvidenceStatus = EvidenceStatus.ACTIVE
    supersedes_evidence_id: Optional[str] = None
    # 证据内容（失真后的报告值，非规则侧真值）
    summary: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    reported: dict = Field(default_factory=dict)   # {bearing, distance_nm, count, ...}


class ContactHypothesis(BaseModel):
    """接触假设（§6.5，D9）：角色信念中的假设，非敌军实体；竞争假设可并存。"""
    id: str = ""
    actor_id: str
    classification: str = "unknown"
    status: ContactStatus = ContactStatus.BEARING_ONLY
    observed_lat: Optional[float] = None
    observed_lon: Optional[float] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    uncertainty_radius_nm: float = 30.0
    course_estimate: Optional[int] = None
    speed_estimate: Optional[float] = None
    confidence_dimensions: dict[str, float] = Field(default_factory=dict)  # 开放多维（D8）
    evidence_ids: list[str] = Field(default_factory=list)
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    association_candidates: list[str] = Field(default_factory=list)  # 只登记，不静默合并
    supersedes_contact_id: Optional[str] = None
    created_from_assessment_id: Optional[str] = None


class BeliefState(BaseModel):
    """角色信念状态（§6.4，D5）：档案全局、知识按角色隔离。"""
    actor_id: str
    contacts: list[str] = Field(default_factory=list)         # ContactHypothesis id
    known_evidence_ids: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    last_updated_at: Optional[datetime] = None
    version: int = 1


class IntelAuditEntry(BaseModel):
    """情报域审计条目（M2.4.8 信念变化审计 / M2.7.9 工具调用审计的公共载体）。"""
    id: str = ""
    at: datetime
    actor_id: str
    action: str                  # contact_status / association / belief_update / tool_call / approval …
    target_id: str = ""
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)


class NPCClaim(BaseModel):
    """NPC 判断声明（§M2.6.1）：谁何时基于什么证据说了什么（审计链）。"""
    id: str = ""
    assessment_id: str = ""
    actor_id: str
    created_at: Optional[datetime] = None
    claim_type: str = "judgment"  # fact（事实）/ judgment（参谋判断）/ hypothesis（推测）/ recommendation（建议）
    text: str = ""
    based_on_evidence_ids: list[str] = Field(default_factory=list)
    tool_call_ids: list[str] = Field(default_factory=list)
    confidence_dimensions: dict[str, float] = Field(default_factory=dict)
    supersedes_claim_id: Optional[str] = None
    status: str = "active"        # active / rejected（误判被否定，保留原文）


# ── Phase S2.3：纵切对象（观测/工作项/判断/简报）──

class SourceObservation(BaseModel):
    """规则侧观测（§6.1）。

    仅存在于规则侧：internal_truth_ref 指向真实敌情，本模型整体禁止进入
    NPC prompt、NPC 工具返回与玩家 API（防泄漏规范 §3.4）。
    """
    id: str = ""
    source_id: str
    source_type: SourceType = SourceType.CARRIER_SCOUT
    observer_actor_id: str = ""
    observed_at: Optional[datetime] = None
    bearing_true: float = 0.0
    distance_nm_true: float = 0.0
    target_name_true: str = ""
    carrier_count_true: int = 0
    sensor_capability: str = "visual"
    environment: str = "clear"
    quality_band: str = "standard"      # high / standard / low（观察质检定）
    quality_check_id: str = ""
    internal_truth_ref: str = ""        # 规则侧真值引用（禁读）


class IntelWorkItem(BaseModel):
    """情报工作项（§M2.5）。没有 NPC 处理就不会产生判断（D12/D15）。"""
    id: str = ""
    priority: WorkPriority = WorkPriority.ROUTINE
    status: str = "queued"              # WorkItemStatus 值
    trigger_message_id: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    assigned_to: str = "intel_officer"
    created_by: str = "radio_officer"
    created_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    outcome_assessment_id: Optional[str] = None
    merged_into_brief_id: Optional[str] = None


class NPCAssessment(BaseModel):
    """情报参谋判断书（§6.6）。claims 为 NPCClaim id 列表（审计链）。"""
    id: str = ""
    author_actor_id: str
    work_item_id: str = ""
    created_at: Optional[datetime] = None
    based_on_evidence_ids: list[str] = Field(default_factory=list)
    facts_used: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    alternative_hypotheses: list[dict] = Field(default_factory=list)
    confidence_dimensions: dict[str, float] = Field(default_factory=dict)
    change_my_mind: list[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    dice_record_ids: list[str] = Field(default_factory=list)
    tool_call_ids: list[str] = Field(default_factory=list)
    conflict_ids: list[str] = Field(default_factory=list)   # 研判时登记的证据冲突
    narrative: str = ""
    contact_id: Optional[str] = None    # 产生的接触假设


class IntelBrief(BaseModel):
    """情报简报（§6.7）。D6：紧急单报 / 例行批次共用本模型。"""
    id: str = ""
    author_actor_id: str
    created_at: Optional[datetime] = None
    briefed_at: Optional[datetime] = None
    audience: str = "commander"
    priority: WorkPriority = WorkPriority.ROUTINE
    new_evidence_ids: list[str] = Field(default_factory=list)
    changed_judgments: list[str] = Field(default_factory=list)   # assessment ids
    plot_proposal_ids: list[str] = Field(default_factory=list)   # S2.4 接入
    unresolved_questions: list[str] = Field(default_factory=list)
    status: str = "draft"               # ApprovalStatus 值
    narrative: str = ""
    annotations: list[dict] = Field(default_factory=list)        # 参谋长批注（追加式，S2.4）


# ── Phase S2.4：标图审批对象（§6.8/§6.9）──

class PlotGeometry(BaseModel):
    """标图几何（M2.6.3）：观测位/可能区域/方位线/距离/航向航速矢量。"""
    lat: float
    lon: float
    uncertainty_radius_nm: float = 30.0
    bearing_line_deg: Optional[float] = None      # 方位线（自参考点）
    bearing_from_lat: Optional[float] = None
    bearing_from_lon: Optional[float] = None
    bearing_from_label: str = ""
    distance_nm: Optional[float] = None
    course_estimate: Optional[int] = None
    speed_estimate: Optional[float] = None


class PlotProposal(BaseModel):
    """标图提案（§6.8）。version 链共享 plot_id；已批准版本不可覆盖（D14）。"""
    id: str = ""
    plot_id: str = ""                     # 修订链 id
    version: int = 1
    author_actor_id: str
    created_at: Optional[datetime] = None
    based_on_evidence_ids: list[str] = Field(default_factory=list)
    assessment_ids: list[str] = Field(default_factory=list)
    geometry: Optional[PlotGeometry] = None
    method: str = "bearing_distance"      # bearing_distance / bearing_intersection / dead_reckoning
    assumptions: list[str] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
    change_summary: str = ""
    supersedes_version: Optional[int] = None
    status: str = "draft"                 # ApprovalStatus 值
    annotations: list[dict] = Field(default_factory=list)   # 参谋长批注（追加式）
    contact_id: Optional[str] = None


class ApprovedPlot(BaseModel):
    """正式标图（§6.9）：指挥官正式采纳过的作战认识——海图唯一敌情输入（D13）。"""
    plot_id: str
    current_version: int = 1
    approved_by: str = "player"
    approved_at: Optional[datetime] = None
    state: str = "active"                 # active / superseded
    decision_id: str = ""
    history: list[dict] = Field(default_factory=list)   # 逐版本：{version, proposal_id, geometry, change_summary, approved_at, decision_id}


class CommanderDecision(BaseModel):
    """指挥官决议（追加式审计：谁在何时批准/驳回了什么）。"""
    id: str = ""
    at: Optional[datetime] = None
    plot_id: str = ""
    proposal_id: str = ""
    action: str = ""                      # approve/reject/defer/request_revision/partial_approve
    items_approved: list[str] = Field(default_factory=list)
    comment: str = ""


class EvidenceConflict(BaseModel):
    """证据冲突记录（M2.7.7 / S2.5）：只登记呈报，不静默裁决。"""
    id: str = ""
    at: Optional[datetime] = None
    kind: str = "position"          # position / bearing / count / identity
    evidence_ids: list[str] = Field(default_factory=list)
    severity: float = 0.0
    note: str = ""
    status: str = "open"            # open / resolved
    resolved_by_evidence_id: Optional[str] = None
