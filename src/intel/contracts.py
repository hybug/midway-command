"""S2 基础契约（Phase S2.0，规格：docs/design/S2_INTEL_SYSTEM.md）。

固定数据边界与命名：
- 五类状态机（消息/证据/接触/工作项/审批）的合法转换表
- 统一数据链 DAG（无循环，由测试守卫）
- 角色权限矩阵——权限控制在状态转换层执行，不依赖 prompt 提醒（计划 §八）
- actual_enemy 防泄漏：FORBIDDEN_SCOPES 对所有角色禁读，含玩家 API

本模块为纯契约层：不导入 src.state 等运行时模型。
"""
from enum import Enum
from typing import Optional


# ── 消息状态（§M2.2）──

class MessageStatus(str, Enum):
    DRAFT = "draft"          # 起草中（发报侧）
    FILED = "filed"          # 已拍发
    IN_TRANSIT = "in_transit"  # 传输中（未到达旗舰）
    RECEIVED = "received"    # 旗舰已收到（玩家可读起点）
    LOGGED = "logged"        # 通信官已登记
    ROUTED = "routed"        # 已分发给参谋
    PROCESSED = "processed"  # 已被参谋处理（产出工作项/判断）
    ARCHIVED = "archived"    # 归档
    LOST = "lost"            # 传输丢失（内容永不泄露）
    CORRECTED = "corrected"  # 已被勘误电报更正（原电文保留，只追加状态）


class CommCondition(str, Enum):
    """通信完整性（§M2.2）"""
    COMPLETE = "complete"
    PARTIAL = "partial"
    GARBLED = "garbled"
    UNREADABLE = "unreadable"
    DUPLICATE = "duplicate"
    CORRECTED = "corrected"


# ── 证据状态（§M2.3，不可变账本）──

class EvidenceStatus(str, Enum):
    ACTIVE = "active"          # 现行有效
    CORRECTED = "corrected"    # 被勘误证据替代（保留）
    SUPERSEDED = "superseded"  # 被新证据替代（保留）
    REJECTED = "rejected"      # 被否定（误报，保留）


# ── 接触生命周期（§M2.4）──

class ContactStatus(str, Enum):
    BEARING_ONLY = "bearing_only"  # 仅有方位
    TENTATIVE = "tentative"        # 暂定接触
    PLOTTED = "plotted"            # 已批准上图
    STALE = "stale"                # 陈旧
    LOST = "lost"                  # 失去接触
    REJECTED = "rejected"          # 误报否定（终态，不可复活）
    SUPERSEDED = "superseded"      # 被新判断替代
    ARCHIVED = "archived"          # 归档（终态）


# ── 情报工作队列（§M2.5）──

class WorkItemStatus(str, Enum):
    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_EVIDENCE = "waiting_for_evidence"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class WorkPriority(str, Enum):
    FLASH = "flash"          # 打断例行工作
    URGENT = "urgent"
    ROUTINE = "routine"      # 可合并到定期简报
    CORRECTION = "correction"


# ── 简报/标图审批（§M2.6）──

class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    REVISION_REQUESTED = "revision_requested"
    PARTIALLY_APPROVED = "partially_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    SUPERSEDED = "superseded"


# ── 骰子检定类型（§九；JUDGMENT_CHECK 公式由 S3 提供）──

class CheckType(str, Enum):
    DETECTION_CHECK = "detection_check"
    OBSERVATION_QUALITY_CHECK = "observation_quality_check"
    COMMUNICATION_CHECK = "communication_check"
    JUDGMENT_CHECK = "judgment_check"
    CORRECTION_CHECK = "correction_check"


# ── 来源类型（§M2.1，D18）──

class SourceType(str, Enum):
    CARRIER_SCOUT = "carrier_scout"    # 舰载侦察机（SBD 等，D19 主纵切）
    PATROL_AIR = "patrol_air"          # PBY 等空中巡逻机
    VISUAL_LOOKOUT = "visual_lookout"  # 舰艇瞭望
    RADAR = "radar"
    SONAR = "sonar"
    FRIENDLY_REPORT = "friendly_report"  # TF16/TF17 等友军电报


# ── 角色与权限矩阵（计划 §八）──

class ActorRole(str, Enum):
    PLAYER = "player"                  # 旗舰指挥官
    COMMS_OFFICER = "comms_officer"    # 通信官：收报与转递
    INTEL_OFFICER = "intel_officer"    # 情报参谋：分析研判
    CHIEF_OF_STAFF = "chief_of_staff"  # 参谋长：批注呈报
    CAPTAIN = "captain"                # 舰长
    NAVIGATOR = "navigator"            # 航海参谋：不生成敌情
    FRIENDLY_FORCE = "friendly_force"  # 友军部队


# （角色, 可见域）白名单——权限控制的数据层声明。
# 可见域键：inbox=已收电文档案；transit=传输中电文（通信链）；evidence_scoped=
# 权限内证据集；work_queue=情报工作队列；briefs_submitted=已呈报简报；
# briefs_all=全部简报（参谋长）；approved_plots=已批准标图；fleet_global=本方全局态势；
# own_carrier=本舰；own_force=本部队。
_ROLE_SCOPES: list[tuple[ActorRole, str]] = [
    (ActorRole.PLAYER, "inbox"),
    (ActorRole.PLAYER, "briefs_submitted"),
    (ActorRole.PLAYER, "approved_plots"),
    (ActorRole.PLAYER, "work_queue"),
    (ActorRole.COMMS_OFFICER, "inbox"),
    (ActorRole.COMMS_OFFICER, "transit"),
    (ActorRole.INTEL_OFFICER, "evidence_scoped"),
    (ActorRole.INTEL_OFFICER, "inbox"),
    (ActorRole.INTEL_OFFICER, "work_queue"),
    (ActorRole.INTEL_OFFICER, "approved_plots"),
    (ActorRole.CHIEF_OF_STAFF, "briefs_all"),
    (ActorRole.CHIEF_OF_STAFF, "inbox"),
    (ActorRole.CHIEF_OF_STAFF, "approved_plots"),
    (ActorRole.CHIEF_OF_STAFF, "fleet_global"),
    (ActorRole.CHIEF_OF_STAFF, "work_queue"),
    (ActorRole.CAPTAIN, "own_carrier"),
    (ActorRole.NAVIGATOR, "fleet_global"),
    (ActorRole.FRIENDLY_FORCE, "own_force"),
]


class RoleScope:
    """（角色, 可见域）白名单的只读入口。"""

    @staticmethod
    def select() -> list[tuple[ActorRole, str]]:
        return list(_ROLE_SCOPES)


# 全角色禁读域：规则侧真相与未送达材料（§四强制约束 3/6、§十禁止暴露清单）。
# 越权读取在任何角色下都非法——NPC 可推测误判，但不能越权（D17）。
FORBIDDEN_SCOPES = frozenset({
    "actual_enemy",         # 规则侧真相
    "internal_truth_ref",   # SourceObservation 规则侧引用
    "unreceived_messages",  # 未收到电文原文
})

# 玩家 API 允许下发的可见域（§十：收报档案、公开判断、已批准标图、复盘数据）。
PLAYER_VISIBLE_SCOPES = frozenset({
    "inbox", "briefs_submitted", "approved_plots", "work_queue",
})


def role_readable_scopes(role: ActorRole) -> frozenset[str]:
    """角色可见域集合。"""
    return frozenset(s for r, s in _ROLE_SCOPES if r == role)


def role_can_read(role: ActorRole, scope: str) -> bool:
    """权限判定：白名单内且非禁读域。"""
    if scope in FORBIDDEN_SCOPES:
        return False
    return scope in role_readable_scopes(role)


# ── 状态机转换表 ──

def _t(**kwargs) -> dict[Enum, frozenset]:
    return {k: frozenset(v) for k, v in kwargs.items()}


def message_transitions() -> dict[MessageStatus, frozenset]:
    """消息状态机（§M2.2）。

    不可覆盖原则（D4）：RECEIVED 之后任何状态都可被 CORRECTED 追加；
    CORRECTED 与 LOST 为终态；玩家可读起点为 RECEIVED。
    """
    return _t(
        **{
            MessageStatus.DRAFT: {MessageStatus.FILED},
            MessageStatus.FILED: {MessageStatus.IN_TRANSIT, MessageStatus.LOST},
            MessageStatus.IN_TRANSIT: {MessageStatus.RECEIVED, MessageStatus.LOST},
            MessageStatus.RECEIVED: {
                MessageStatus.LOGGED, MessageStatus.CORRECTED, MessageStatus.ARCHIVED,
            },
            MessageStatus.LOGGED: {
                MessageStatus.ROUTED, MessageStatus.CORRECTED, MessageStatus.ARCHIVED,
            },
            MessageStatus.ROUTED: {
                MessageStatus.PROCESSED, MessageStatus.CORRECTED, MessageStatus.ARCHIVED,
            },
            MessageStatus.PROCESSED: {MessageStatus.ARCHIVED, MessageStatus.CORRECTED},
            MessageStatus.ARCHIVED: {MessageStatus.CORRECTED},
            MessageStatus.LOST: set(),
            MessageStatus.CORRECTED: set(),
        }
    )


def evidence_transitions() -> dict[EvidenceStatus, frozenset]:
    """证据状态机：ACTIVE 唯一活态，其余终态（原记录保留不删除）。"""
    return _t(
        **{
            EvidenceStatus.ACTIVE: {
                EvidenceStatus.CORRECTED,
                EvidenceStatus.SUPERSEDED,
                EvidenceStatus.REJECTED,
            },
            EvidenceStatus.CORRECTED: set(),
            EvidenceStatus.SUPERSEDED: set(),
            EvidenceStatus.REJECTED: set(),
        }
    )


def contact_transitions() -> dict[ContactStatus, frozenset]:
    """接触生命周期（§M2.4，D9）。

    - STALE 可重新激活（重新接触）
    - REJECTED 是终态：误报否定后不可复活，重新发现必须建立新接触
    - SUPERSEDED → ARCHIVED：被替代后归档，历史版本全部保留
    """
    return _t(
        **{
            ContactStatus.BEARING_ONLY: {
                ContactStatus.TENTATIVE, ContactStatus.PLOTTED,
                ContactStatus.STALE, ContactStatus.REJECTED, ContactStatus.SUPERSEDED,
            },
            ContactStatus.TENTATIVE: {
                ContactStatus.PLOTTED, ContactStatus.STALE, ContactStatus.LOST,
                ContactStatus.REJECTED, ContactStatus.SUPERSEDED,
            },
            ContactStatus.PLOTTED: {
                ContactStatus.STALE, ContactStatus.LOST,
                ContactStatus.REJECTED, ContactStatus.SUPERSEDED,
            },
            ContactStatus.STALE: {
                ContactStatus.TENTATIVE, ContactStatus.PLOTTED, ContactStatus.LOST,
                ContactStatus.REJECTED, ContactStatus.SUPERSEDED,
            },
            ContactStatus.LOST: {
                ContactStatus.TENTATIVE, ContactStatus.PLOTTED, ContactStatus.SUPERSEDED,
            },
            ContactStatus.REJECTED: set(),
            ContactStatus.SUPERSEDED: {ContactStatus.ARCHIVED},
            ContactStatus.ARCHIVED: set(),
        }
    )


def work_item_transitions() -> dict[WorkItemStatus, frozenset]:
    """工作项状态机（§M2.5）。"""
    return _t(
        **{
            WorkItemStatus.QUEUED: {WorkItemStatus.ASSIGNED, WorkItemStatus.CANCELLED},
            WorkItemStatus.ASSIGNED: {
                WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED,
            },
            WorkItemStatus.IN_PROGRESS: {
                WorkItemStatus.WAITING_FOR_EVIDENCE,
                WorkItemStatus.SUBMITTED,
                WorkItemStatus.CANCELLED,
            },
            WorkItemStatus.WAITING_FOR_EVIDENCE: {
                WorkItemStatus.IN_PROGRESS,
                WorkItemStatus.CLOSED,
                WorkItemStatus.CANCELLED,
            },
            WorkItemStatus.SUBMITTED: {WorkItemStatus.ACKNOWLEDGED},
            WorkItemStatus.ACKNOWLEDGED: {WorkItemStatus.CLOSED},
            WorkItemStatus.CLOSED: set(),
            WorkItemStatus.CANCELLED: set(),
        }
    )


def approval_transitions() -> dict[ApprovalStatus, frozenset]:
    """简报/标图审批状态机（§M2.6，D13/D14）。

    批准不等于确认事实，只表示正式采纳当前判断；
    APPROVED 唯一去向是 SUPERSEDED（新版修订批准后旧版存档）。
    """
    return _t(
        **{
            ApprovalStatus.DRAFT: {ApprovalStatus.PROPOSED},
            ApprovalStatus.PROPOSED: {
                ApprovalStatus.REVISION_REQUESTED,
                ApprovalStatus.PARTIALLY_APPROVED,
                ApprovalStatus.APPROVED,
                ApprovalStatus.REJECTED,
                ApprovalStatus.DEFERRED,
            },
            ApprovalStatus.REVISION_REQUESTED: {ApprovalStatus.PROPOSED},
            ApprovalStatus.PARTIALLY_APPROVED: {
                ApprovalStatus.APPROVED,
                ApprovalStatus.REJECTED,
                ApprovalStatus.REVISION_REQUESTED,
            },
            ApprovalStatus.DEFERRED: {ApprovalStatus.PROPOSED, ApprovalStatus.REJECTED},
            ApprovalStatus.APPROVED: {ApprovalStatus.SUPERSEDED},
            ApprovalStatus.REJECTED: set(),
            ApprovalStatus.SUPERSEDED: set(),
        }
    )


def can_transition(table: dict, src: Enum, dst: Enum) -> bool:
    """dst 是否为 src 的合法后继。"""
    return dst in table.get(src, frozenset())


def require_transition(table: dict, src: Enum, dst: Enum) -> None:
    """状态转换守卫：非法转换抛 ValueError（权限/纪律控制发生在状态转换层）。"""
    if not can_transition(table, src, dst):
        raise ValueError(f"非法状态转换: {src} → {dst}")


# ── 初始状态（每个对象都能回答"从哪来"）──

INITIAL_STATUSES: dict[type, frozenset] = {
    MessageStatus: frozenset({MessageStatus.DRAFT}),
    EvidenceStatus: frozenset({EvidenceStatus.ACTIVE}),
    ContactStatus: frozenset({ContactStatus.BEARING_ONLY, ContactStatus.TENTATIVE}),
    WorkItemStatus: frozenset({WorkItemStatus.QUEUED}),
    ApprovalStatus: frozenset({ApprovalStatus.DRAFT}),
}


# ── 统一数据链（§四；DAG，由测试守卫无循环）──

DATA_FLOW_EDGES: list[tuple[str, str]] = [
    ("ActualWorld", "SourceObservation"),
    ("SourceObservation", "FiledMessage"),
    ("FiledMessage", "ReceivedMessage"),
    ("ReceivedMessage", "Evidence"),
    ("Evidence", "IntelWorkItem"),
    ("IntelWorkItem", "NPCAssessment"),
    ("NPCAssessment", "NPCClaim"),
    ("NPCAssessment", "IntelBrief"),
    ("IntelBrief", "PlotProposal"),
    ("PlotProposal", "CommanderDecision"),
    ("CommanderDecision", "ApprovedPlot"),
    ("ApprovedPlot", "Chart"),
    ("CheckRecord", "NPCAssessment"),   # 骰子检定记录流入判断（可回放）
    ("CheckRecord", "ReceivedMessage"),  # 通信检定记录流入收报
    ("ToolCallRecord", "NPCAssessment"),  # 推理工具调用流入判断（可审计）
]
