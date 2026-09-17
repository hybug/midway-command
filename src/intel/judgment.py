"""S3 JudgmentPolicy 接口草案（Phase S2.0）。

S2 只定义输入输出（计划 §九：JUDGMENT_CHECK 公式与 NPC 维度由 S3 提供）：
- EvidenceView：权限转换后的证据投影——字段集即防泄漏边界，
  不携带 internal_truth_ref / actual_enemy。
- ActorProfile：判断者档案，attributes 为开放维度集（D20：不锁定维度数量）。
- JudgmentDice：骰子系统 JUDGMENT_CHECK 的结构化输出——NPC 不重算骰子结果。
- AssessmentDraft：判断草稿，confidence_dimensions 为开放多维 dict（D8）。

S3 落地时提供具体 JudgmentPolicy 实现（公式、消融、历史校准）。
"""
from datetime import datetime
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, Field


class EvidenceView(BaseModel):
    """NPC 可见证据投影（§四强制约束 2：NPC 只能读取经过权限转换的 EvidenceView）。"""
    evidence_id: str
    message_id: str = ""
    source_type: str = ""
    source_label: str = ""
    observed_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    source_reliability: Optional[float] = None
    summary: str = ""
    # 开放维度：identity/position/count 精度等，维度集合由上游装配决定
    dimensions: dict[str, float] = Field(default_factory=dict)


class ActorProfile(BaseModel):
    """判断者档案。attributes 开放：competence 等数值由 S3 定义使用。"""
    actor_id: str
    role: str = ""
    attributes: dict[str, float] = Field(default_factory=dict)


class AssessmentDraft(BaseModel):
    """判断草稿——NPC LLM 渲染前的结构化骨架（M2.6.1 NPCAssessment 的来源）。"""
    claims: list[dict] = Field(default_factory=list)
    confidence_dimensions: dict[str, float] = Field(default_factory=dict)
    alternative_hypotheses: list[dict] = Field(default_factory=list)
    change_my_mind: list[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    notes: str = ""


class JudgmentDice(BaseModel):
    """骰子系统判定的结构化输出（§九：错误方向、严重度、表达确定性）。"""
    record_id: str
    level: str                       # 五级结果（critical_success..critical_failure）
    error_direction: Optional[str] = None   # 如 overestimate / underestimate / bearing_offset
    error_severity: float = 0.0             # 0-1
    express_certainty: float = 1.0          # 0-1：表达确定性（影响文风而非事实）


@runtime_checkable
class JudgmentPolicy(Protocol):
    """判断策略接口。

    实现（S3）在给定工作项、权限内证据、判断者档案与骰子判定结果时，
    产出结构化判断草稿。禁止实现读取规则侧真相（EvidenceView 之外的数据）。
    """

    def assess(
        self,
        work_item: Any,
        evidence: Sequence[EvidenceView],
        actor: ActorProfile,
        dice: JudgmentDice,
    ) -> AssessmentDraft: ...
