"""操作语义契约（action-semantics-remediation-plan AS.0）。

统一原则：内容自由文本，动作固定枚举，范围固定选项，执行明确确认。
正式操作四层：Content（正文/备注）/ Action（固定枚举）/ Scope（固定对象）/
Confirm（明确确认）。本模块只定义契约与审计形状，不做业务执行；
S4 通知动作与 S5 Order 端点在各自实现处复用这些枚举。
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """v0 动作目录（整改计划 §三；延期动作不入目录）。"""

    # 通信
    SEND_TELEGRAM = "SEND_TELEGRAM"
    FORWARD_TO_CHAIN = "FORWARD_TO_CHAIN"
    # 核心参谋
    REQUEST_ASSESSMENT = "REQUEST_ASSESSMENT"
    REQUEST_RECONSIDERATION = "REQUEST_RECONSIDERATION"
    RECORD_COMMANDER_FEEDBACK = "RECORD_COMMANDER_FEEDBACK"
    ACKNOWLEDGE_STAFF_NOTICE = "ACKNOWLEDGE_STAFF_NOTICE"
    DEFER_STAFF_NOTICE = "DEFER_STAFF_NOTICE"
    CLOSE_STAFF_NOTICE = "CLOSE_STAFF_NOTICE"
    # 情报与标图
    PROPOSE_PLOT = "PROPOSE_PLOT"
    APPROVE_PLOT = "APPROVE_PLOT"
    REJECT_PLOT = "REJECT_PLOT"
    DEFER_PLOT = "DEFER_PLOT"
    REQUEST_PLOT_REVISION = "REQUEST_PLOT_REVISION"
    MARK_CONTACT_STALE = "MARK_CONTACT_STALE"
    REJECT_CONTACT = "REJECT_CONTACT"
    # 航线
    PROPOSE_ROUTE = "PROPOSE_ROUTE"
    APPROVE_ROUTE = "APPROVE_ROUTE"
    CANCEL_ROUTE = "CANCEL_ROUTE"
    REQUEST_ROUTE_REVISION = "REQUEST_ROUTE_REVISION"
    # 正式命令（S5 Order 类型）
    SET_COURSE = "SET_COURSE"
    LAUNCH_SCOUT = "LAUNCH_SCOUT"


class AvailableAction(BaseModel):
    """对象详情接口下发的当前允许动作（UI 只渲染后端允许的动作）。"""

    action_type: ActionType
    label: str
    required_options: list[str] = Field(default_factory=list)
    allowed_recipients: list[str] = Field(default_factory=list)
    enabled: bool = True
    disabled_reason: str = ""
    requires_confirmation: bool = True


class ActionCommand(BaseModel):
    """统一命令信封：动作由固定枚举表达，自然语言只承载 note/正文。"""

    command_id: str
    action_type: ActionType
    source_type: str = ""
    source_id: str = ""
    target_type: str = ""
    target_id: str = ""
    options: dict[str, Any] = Field(default_factory=dict)
    recipients: list[str] = Field(default_factory=list)
    priority: str = "routine"
    note: str = ""
    requires_response: bool = False
    requires_confirmation: bool = True
    created_by: str = "player"
    created_at: Optional[datetime] = None


class AuditRecord(BaseModel):
    """每次正式动作的统一审计记录（追加制）。"""

    id: str
    actor_id: str
    action_type: str
    source: str = ""
    targets: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)
    note: str = ""
    before_state: str = ""
    after_state: str = ""
    at: datetime
    result: str = ""
