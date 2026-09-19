"""S5 数据对象（s5-command-execution-system-plan §四）。

Order / OrderResult / OrderEvent。纪律：
- commander_intent_text 必填一等输入，签发后原文不可改写。
- v0 只支持 EXACT / INTENT；状态只用七态，部分完成落在 result.outcome。
- cost_policy 为 AP 专项预留占位，S5 不解释其规则（D18）。
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OrderType(str, Enum):
    SET_COURSE = "SET_COURSE"
    LAUNCH_SCOUT = "LAUNCH_SCOUT"


class AuthorityMode(str, Enum):
    EXACT = "exact"
    INTENT = "intent"


class OrderStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrderEventType(str, Enum):
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_ISSUED = "ORDER_ISSUED"
    ORDER_DELIVERED = "ORDER_DELIVERED"
    ORDER_CLARIFICATION_REQUESTED = "ORDER_CLARIFICATION_REQUESTED"
    ORDER_ALTERNATIVE_PROPOSED = "ORDER_ALTERNATIVE_PROPOSED"
    ORDER_APPROVED = "ORDER_APPROVED"
    ORDER_ACTIVATED = "ORDER_ACTIVATED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_COMPLETED = "ORDER_COMPLETED"
    ORDER_FAILED = "ORDER_FAILED"


class Order(BaseModel):
    id: str
    order_type: OrderType
    target_refs: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    commander_intent_text: str
    authority_mode: AuthorityMode
    priority: str = "routine"
    responsible_role: Optional[str] = None      # 语义岗位键（NAVIGATOR/AIR_OFFICER）
    responsible_actor_id: Optional[str] = None  # roster 绑定的现任者
    source_refs: list[str] = Field(default_factory=list)
    delivery_message_id: Optional[str] = None
    status: OrderStatus = OrderStatus.DRAFT
    reported_status: str = "draft"              # 玩家可见字段（UI 使用）
    result: Optional[dict] = None               # OrderResult 形状
    cost_policy: Optional[str] = None           # AP 专项占位（S5 不解释）
    plan: Optional[dict] = None                 # INTENT 责任参谋执行方案
    # 规则侧内部字段（永不进入玩家视图）
    delivery_eta: Optional[datetime] = None
    delivery_will_lose: bool = False
    delivery_confirmed: bool = False
    activated_at: Optional[datetime] = None   # 激活时刻（执行须晚于激活 tick）
    report_message_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OrderEvent(BaseModel):
    """生命周期事件（追加保存，可回放）。"""

    id: str
    order_id: str
    at: datetime
    actor_id: str
    event_type: OrderEventType
    summary: str = ""
    source_ref: str = ""
