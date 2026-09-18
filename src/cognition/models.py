"""S3 核心数据模型（Phase S3.0，计划 §六 6.1–6.7）。

纪律：
- 判断以 JudgmentTask → JudgmentResult 为基本单位（D1），不以聊天消息为单位。
- Hypothesis 是 LLM 候选的规范化载体：不携带规则侧评分（evidence_fit 由
  规则层计算，LLM 不能覆盖——M3.3 验收）。
- 判断保留人物归属（D4）；记忆按 actor 隔离（D7/D8）。
- 本模块模型不含规则侧真值字段（actual_enemy / internal_truth_ref）。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from src.cognition.contracts import (
    ACTIVE_ATTRIBUTE_DIMS,
    ATTRIBUTE_MAX,
    ATTRIBUTE_MIN,
    CANDIDATE_ATTRIBUTE_DIMS,
    compute_stable_key,
    normalize_question,
)


def _validate_attributes(attributes: dict[str, float]) -> dict[str, float]:
    missing = [d for d in ACTIVE_ATTRIBUTE_DIMS if d not in attributes]
    if missing:
        raise ValueError(f"ActorProfile 缺少有效维度: {missing}")
    for key, value in attributes.items():
        if key not in ACTIVE_ATTRIBUTE_DIMS and key not in CANDIDATE_ATTRIBUTE_DIMS:
            raise ValueError(f"未登记的人物参数维度: {key}")
        if not (ATTRIBUTE_MIN <= value <= ATTRIBUTE_MAX):
            raise ValueError(f"人物参数 {key}={value} 超出 [0, 10]")
    return attributes


class ActorProfile(BaseModel):
    """判断者档案（§6.1，M3.1.1）。五项有效维度必填（D17），候选维度可选（D18）。"""
    actor_id: str
    role: str = ""
    domain: str = ""                     # intelligence / air / operations / ship
    attributes: dict[str, float] = Field(default_factory=dict)
    profile_version: str = "v0"
    persona_prompt_ref: str = ""

    @model_validator(mode="after")
    def _check(self):
        _validate_attributes(self.attributes)
        return self


class JudgmentTask(BaseModel):
    """判断任务（§6.2）。stable_key 由输入派生，重复请求据此命中缓存（D9）。"""
    id: str = ""
    task_type: str = "assess"            # TaskType 值
    domain: str = "intelligence"
    actor_id: str
    question: str
    question_normalized: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    context_version: int = 1
    source: str = "commander"            # commander / work_item / self_initiated
    created_at: Optional[datetime] = None
    priority: str = "routine"
    stable_key: str = ""
    supersedes_task_id: Optional[str] = None

    @model_validator(mode="after")
    def _derive(self):
        self.question_normalized = self.question_normalized or normalize_question(
            self.question)
        self.stable_key = self.stable_key or compute_stable_key(
            actor_id=self.actor_id, task_type=self.task_type,
            domain=self.domain, question_normalized=self.question_normalized,
            evidence_ids=list(self.evidence_ids),
            context_version=self.context_version,
        )
        return self


class Hypothesis(BaseModel):
    """候选假设（§6.3）。LLM 生成文本与预测，规则层补 aggressiveness/novelty；
    本模型不含任何 fit/score 字段（LLM 不能自带评分）。
    """
    id: str
    text: str
    predicted_class: Optional[str] = None          # CV / CA / transport / unknown…
    predicted_count_range: Optional[tuple[int, int]] = None
    predicted_position: Optional[tuple[float, float]] = None  # (lat, lon)
    predicted_position_model: str = ""             # 位置来源：reported_bearing_distance / dead_reckoning…
    predicted_course_range: Optional[tuple[int, int]] = None  # 度
    predicted_speed_range: Optional[tuple[float, float]] = None  # 节
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    aggressiveness: float = Field(default=0.0, ge=-1.0, le=1.0)  # 规则可计算
    novelty: float = Field(default=0.0, ge=0.0, le=1.0)          # 规则可计算

    @model_validator(mode="after")
    def _check(self):
        if self.predicted_count_range is not None:
            lo, hi = self.predicted_count_range
            if lo > hi:
                raise ValueError("predicted_count_range min>max")
        if self.predicted_course_range is not None:
            lo, hi = self.predicted_course_range
            if lo > hi:
                raise ValueError("predicted_course_range min>max")
        if self.predicted_speed_range is not None:
            lo, hi = self.predicted_speed_range
            if lo > hi:
                raise ValueError("predicted_speed_range min>max")
        return self


class EvidenceFit(BaseModel):
    """证据适配评分（§6.4，S3.1 计算；S3.0 先固定 schema）。

    没有对应证据的维度不参与评分，剩余权重重新归一化（M3.3 验收）。
    """
    hypothesis_id: str
    identity_fit: Optional[float] = None
    position_fit: Optional[float] = None
    count_fit: Optional[float] = None
    motion_fit: Optional[float] = None
    source_fit: Optional[float] = None
    freshness_fit: Optional[float] = None
    contradiction_penalty: float = 0.0
    weighted_fit: float = 0.0


class JudgmentResult(BaseModel):
    """判断结果（§6.5）。chosen_hypothesis 由规则公式选出，LLM 不得改写。"""
    id: str = ""
    task_id: str
    actor_id: str
    chosen_hypothesis_id: Optional[str] = None     # 拒绝时可为 None
    plausible_hypothesis_ids: list[str] = Field(default_factory=list)
    dice_record_id: str = ""                       # 恰好一次 JUDGMENT_CHECK（D3）
    error_type: str = "none"                       # ErrorType 值
    error_severity: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_band: str = "low"                   # ConfidenceBand 值
    recommendation: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)
    change_my_mind: list[str] = Field(default_factory=list)
    refusal_reason: Optional[str] = None           # RefusalReason 值
    formula_version: str = ""
    result_version: int = 1
    created_at: Optional[datetime] = None
    supersedes_result_id: Optional[str] = None


class JudgmentMemory(BaseModel):
    """判断记忆（§6.6，D8/D10）：只由自身判断、指挥官反馈、新证据与可观察结果更新。
    按 actor 隔离：其他 NPC 默认不可读（D7）。
    """
    id: str = ""
    actor_id: str
    task_type: str = "assess"
    domain: str = ""
    result_id: str = ""
    selected_hypothesis: Optional[str] = None
    alternative_hypotheses: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: str = "low"
    assumptions: list[str] = Field(default_factory=list)
    change_my_mind: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    status: str = "open"                           # MemoryStatus 值
    supersedes_id: Optional[str] = None
    commander_decision: Optional[str] = None       # approve/reject/defer/request_revision
    observable_outcome_ids: list[str] = Field(default_factory=list)


class JudgmentAuditRecord(BaseModel):
    """判断审计（§6.7，M3.9）：同种子同输入可回放（D9/验收 13）。"""
    id: str = ""
    task_id: str
    result_id: str = ""
    actor_id: str
    formula_version: str = ""
    attribute_snapshot: dict[str, float] = Field(default_factory=dict)
    candidate_scores: dict[str, float] = Field(default_factory=dict)
    plausible_set: list[str] = Field(default_factory=list)
    dice_record_id: str = ""
    memory_ids: list[str] = Field(default_factory=list)
    context_version: int = 1
    random_seed: str = ""
    created_at: Optional[datetime] = None


class JudgmentContext(BaseModel):
    """一次判断的装配上下文（计划 §四 输入）。证据只经 EvidenceView 投影（D6）。"""
    actor: ActorProfile
    evidence: list = Field(default_factory=list)   # Sequence[EvidenceView]
    memories: list[JudgmentMemory] = Field(default_factory=list)
    now: Optional[datetime] = None
    pressure: dict[str, float] = Field(default_factory=dict)  # 时间压力等（v0 登记）
    duty_boundary: list[str] = Field(default_factory=list)    # 职责边界说明
    conflicts: list = Field(default_factory=list)  # Sequence[EvidenceConflict]（S2.5 登记，只减分不裁决）
    scenario: dict = Field(default_factory=dict)   # scenario 覆盖（如 ambiguity_band）
