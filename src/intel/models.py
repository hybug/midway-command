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
