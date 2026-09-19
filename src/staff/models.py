"""S4 数据对象（s4-staff-relations-system-plan §五）。

CommanderContactChannel / CommanderNotice / ChainReport / DossierSummary。
纪律：notice_reason 为固定枚举；同 actor 同时只一个 open notice；
主动事项不携带任何舰队状态变更语义（D7）。
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ContactPermission(str, Enum):
    DIRECT_IN_PERSON = "DIRECT_IN_PERSON"   # 同舰，可当面呈报
    DIRECT_RADIO = "DIRECT_RADIO"           # 不同舰，TBS/无线电直连
    CHAIN_ONLY = "CHAIN_ONLY"               # 只能逐级上呈
    REPORT_ONLY = "REPORT_ONLY"             # 只能书面报告
    NO_INITIATIVE = "NO_INITIATIVE"         # 只能被动应答


class NoticeReason(str, Enum):
    """主动提醒的固定业务理由（性格只影响表达，不创造理由）。"""

    NEW_EVIDENCE = "NEW_EVIDENCE"
    DECISION_REQUIRED = "DECISION_REQUIRED"
    RISK_WARNING = "RISK_WARNING"
    OPPORTUNITY = "OPPORTUNITY"
    REPORT_ESCALATION = "REPORT_ESCALATION"
    CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"


class NoticePriority(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    FLASH = "flash"


class NoticeState(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    DEFERRED = "deferred"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class CommanderContactChannel(BaseModel):
    """直接沟通名单条目（scenario roster 决定，数量不预设）。"""

    actor_id: str
    personnel_id: str = ""
    display_name: str
    rank: str = ""
    role: str = ""
    flagship: str = ""
    contact_permission: ContactPermission
    can_be_summoned: bool = False
    can_initiate: bool = False
    evidence_grade: str = "UNKNOWN"
    source_ids: list[str] = Field(default_factory=list)


class CommanderNotice(BaseModel):
    """名单内人员主动提醒（同一联系人同一主题只保留一个未处理事项）。"""

    id: str
    actor_id: str
    topic: str
    priority: NoticePriority
    source_type: str
    source_id: str
    notice_reason: NoticeReason
    state: NoticeState = NoticeState.OPEN
    created_at: datetime
    cooldown_until: Optional[datetime] = None
    escalated: bool = False
    handled_by: list[dict] = Field(default_factory=list)


class ChainReportState(str, Enum):
    IN_CHAIN = "in_chain"
    DELIVERED = "delivered"
    DEFERRED = "deferred"
    CLOSED = "closed"


class ChainReport(BaseModel):
    """指挥链上呈报告（来源不丢、批注不改原文、逐跳记录时间）。"""

    id: str
    origin_actor_id: str
    origin_role: str = ""
    current_holder_id: str
    next_holder_id: str
    route: list[str] = Field(default_factory=list)
    source_type: str
    source_id: str
    summary: str
    priority: str = "routine"
    state: ChainReportState = ChainReportState.IN_CHAIN
    at: datetime
    delivered_at: Optional[datetime] = None
    annotations: list[dict] = Field(default_factory=list)
    history: list[dict] = Field(default_factory=list)
