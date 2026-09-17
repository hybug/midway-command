"""S2.0 基础契约测试（Phase S2.0，红灯先行）。

覆盖 s2-intelligence-system-plan.md §十三 Phase S2.0 验收：
- 消息/证据/接触/工作项/审批状态机（§M2.2/§M2.3/§M2.4/§M2.5/§M2.6 枚举）
- 数据流图无循环（DAG 校验）
- 角色权限矩阵与 actual_enemy 防泄漏规范
- S3 JudgmentPolicy 接口（不锁定维度数量，D20）
"""
import pytest

from src.intel.contracts import (
    ActorRole,
    ApprovalStatus,
    CheckType,
    CommCondition,
    ContactStatus,
    DATA_FLOW_EDGES,
    FORBIDDEN_SCOPES,
    MessageStatus,
    EvidenceStatus,
    RoleScope,
    WorkItemStatus,
    WorkPriority,
    approval_transitions,
    can_transition,
    contact_transitions,
    evidence_transitions,
    message_transitions,
    role_can_read,
    role_readable_scopes,
    work_item_transitions,
    INITIAL_STATUSES,
)
from src.intel.judgment import (
    ActorProfile,
    AssessmentDraft,
    EvidenceView,
    JudgmentDice,
    JudgmentPolicy,
)


# ── 枚举值与计划文本一致 ──

def test_message_status_values():
    assert {s.value for s in MessageStatus} == {
        "draft", "filed", "in_transit", "received", "logged",
        "routed", "processed", "archived", "lost", "corrected",
    }


def test_comm_condition_values():
    assert {c.value for c in CommCondition} == {
        "complete", "partial", "garbled", "unreadable", "duplicate", "corrected",
    }


def test_evidence_status_values():
    assert {s.value for s in EvidenceStatus} == {
        "active", "corrected", "superseded", "rejected",
    }


def test_contact_status_values():
    assert {s.value for s in ContactStatus} == {
        "bearing_only", "tentative", "plotted", "stale",
        "lost", "rejected", "superseded", "archived",
    }


def test_work_item_status_values():
    assert {s.value for s in WorkItemStatus} == {
        "queued", "assigned", "in_progress", "waiting_for_evidence",
        "submitted", "acknowledged", "closed", "cancelled",
    }


def test_work_priority_values():
    assert {p.value for p in WorkPriority} == {
        "flash", "urgent", "routine", "correction",
    }


def test_approval_status_values():
    assert {s.value for s in ApprovalStatus} == {
        "draft", "proposed", "revision_requested", "partially_approved",
        "approved", "rejected", "deferred", "superseded",
    }


def test_check_type_values():
    assert {c.value for c in CheckType} == {
        "detection_check", "observation_quality_check",
        "communication_check", "judgment_check", "correction_check",
    }


# ── 初始状态唯一性（每个对象都能回答"从哪来"）──

def test_initial_statuses():
    assert INITIAL_STATUSES[MessageStatus] == {MessageStatus.DRAFT}
    assert INITIAL_STATUSES[EvidenceStatus] == {EvidenceStatus.ACTIVE}
    assert INITIAL_STATUSES[ContactStatus] <= {
        ContactStatus.BEARING_ONLY, ContactStatus.TENTATIVE,
    }
    assert INITIAL_STATUSES[WorkItemStatus] == {WorkItemStatus.QUEUED}
    assert INITIAL_STATUSES[ApprovalStatus] == {ApprovalStatus.DRAFT}


# ── 消息状态机 ──

def test_message_happy_path():
    path = [
        MessageStatus.DRAFT, MessageStatus.FILED, MessageStatus.IN_TRANSIT,
        MessageStatus.RECEIVED, MessageStatus.LOGGED, MessageStatus.ROUTED,
        MessageStatus.PROCESSED, MessageStatus.ARCHIVED,
    ]
    for a, b in zip(path, path[1:]):
        assert can_transition(message_transitions(), a, b)


def test_message_lost_terminal():
    assert can_transition(message_transitions(), MessageStatus.FILED, MessageStatus.LOST)
    assert can_transition(message_transitions(), MessageStatus.IN_TRANSIT, MessageStatus.LOST)
    assert not can_transition(message_transitions(), MessageStatus.LOST, MessageStatus.RECEIVED)
    assert message_transitions()[MessageStatus.LOST] == frozenset()


def test_message_correction_only_after_received():
    # 勘误只能施加于已送达旗舰的电文（D4：原始记录不可覆盖，勘误是追加状态）
    for s in (MessageStatus.DRAFT, MessageStatus.FILED, MessageStatus.IN_TRANSIT):
        assert not can_transition(message_transitions(), s, MessageStatus.CORRECTED)
    for s in (MessageStatus.RECEIVED, MessageStatus.LOGGED, MessageStatus.ROUTED,
              MessageStatus.PROCESSED, MessageStatus.ARCHIVED):
        assert can_transition(message_transitions(), s, MessageStatus.CORRECTED)
    assert message_transitions()[MessageStatus.CORRECTED] == frozenset()


def test_message_cannot_go_backwards():
    assert not can_transition(message_transitions(), MessageStatus.RECEIVED, MessageStatus.FILED)
    assert not can_transition(message_transitions(), MessageStatus.ROUTED, MessageStatus.RECEIVED)


# ── 证据状态机（不可变账本：active 是唯一活态）──

def test_evidence_terminal_states():
    for s in (EvidenceStatus.CORRECTED, EvidenceStatus.SUPERSEDED, EvidenceStatus.REJECTED):
        assert evidence_transitions()[s] == frozenset()
    assert can_transition(evidence_transitions(), EvidenceStatus.ACTIVE, EvidenceStatus.SUPERSEDED)
    assert not can_transition(evidence_transitions(), EvidenceStatus.SUPERSEDED, EvidenceStatus.ACTIVE)


# ── 接触生命周期（D9：允许竞争假设，不允许静默复活）──

def test_contact_lifecycle():
    t = contact_transitions()
    assert can_transition(t, ContactStatus.BEARING_ONLY, ContactStatus.TENTATIVE)
    assert can_transition(t, ContactStatus.TENTATIVE, ContactStatus.PLOTTED)
    assert can_transition(t, ContactStatus.PLOTTED, ContactStatus.STALE)
    assert can_transition(t, ContactStatus.STALE, ContactStatus.TENTATIVE)  # 重新接触
    assert can_transition(t, ContactStatus.TENTATIVE, ContactStatus.REJECTED)
    assert can_transition(t, ContactStatus.PLOTTED, ContactStatus.SUPERSEDED)


def test_contact_rejected_is_terminal():
    # 误报否定（§7.4）：REJECTED 不允许复活——重新发现必须建立新接触
    assert contact_transitions()[ContactStatus.REJECTED] == frozenset()


def test_contact_superseded_only_to_archived():
    t = contact_transitions()
    assert t[ContactStatus.SUPERSEDED] == frozenset({ContactStatus.ARCHIVED})
    assert t[ContactStatus.ARCHIVED] == frozenset()


# ── 工作项状态机 ──

def test_work_item_lifecycle():
    t = work_item_transitions()
    assert not can_transition(t, WorkItemStatus.QUEUED, WorkItemStatus.IN_PROGRESS)
    assert can_transition(t, WorkItemStatus.QUEUED, WorkItemStatus.ASSIGNED)
    assert can_transition(t, WorkItemStatus.ASSIGNED, WorkItemStatus.IN_PROGRESS)
    assert can_transition(t, WorkItemStatus.IN_PROGRESS, WorkItemStatus.SUBMITTED)
    assert can_transition(t, WorkItemStatus.SUBMITTED, WorkItemStatus.ACKNOWLEDGED)
    assert can_transition(t, WorkItemStatus.ACKNOWLEDGED, WorkItemStatus.CLOSED)
    assert t[WorkItemStatus.CLOSED] == frozenset()


def test_work_item_waiting_for_evidence():
    t = work_item_transitions()
    assert can_transition(t, WorkItemStatus.IN_PROGRESS, WorkItemStatus.WAITING_FOR_EVIDENCE)
    assert can_transition(t, WorkItemStatus.WAITING_FOR_EVIDENCE, WorkItemStatus.IN_PROGRESS)
    assert can_transition(t, WorkItemStatus.WAITING_FOR_EVIDENCE, WorkItemStatus.CLOSED)


# ── 审批状态机（D13/D14：批准后只能被新版本替代，不可回退）──

def test_approval_lifecycle():
    t = approval_transitions()
    assert not can_transition(t, ApprovalStatus.DRAFT, ApprovalStatus.APPROVED)
    assert can_transition(t, ApprovalStatus.DRAFT, ApprovalStatus.PROPOSED)
    for s in (ApprovalStatus.REVISION_REQUESTED, ApprovalStatus.PARTIALLY_APPROVED,
              ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.DEFERRED):
        assert can_transition(t, ApprovalStatus.PROPOSED, s)
    assert can_transition(t, ApprovalStatus.REVISION_REQUESTED, ApprovalStatus.PROPOSED)
    assert can_transition(t, ApprovalStatus.DEFERRED, ApprovalStatus.PROPOSED)
    assert can_transition(t, ApprovalStatus.PARTIALLY_APPROVED, ApprovalStatus.APPROVED)


def test_approval_approved_only_superseded():
    t = approval_transitions()
    assert t[ApprovalStatus.APPROVED] == frozenset({ApprovalStatus.SUPERSEDED})
    assert not can_transition(t, ApprovalStatus.APPROVED, ApprovalStatus.PROPOSED)
    assert t[ApprovalStatus.REJECTED] == frozenset()


# ── 数据流图无循环 ──

def test_data_flow_is_dag():
    nodes = set()
    for a, b in DATA_FLOW_EDGES:
        nodes.update((a, b))
    # Kahn 拓扑排序：能完整排序 ⇒ 无环
    indegree = {n: 0 for n in nodes}
    adj = {n: [] for n in nodes}
    for a, b in DATA_FLOW_EDGES:
        adj[a].append(b)
        indegree[b] += 1
    queue = [n for n, d in indegree.items() if d == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for m in adj[n]:
            indegree[m] -= 1
            if indegree[m] == 0:
                queue.append(m)
    assert seen == len(nodes), "数据流图存在循环依赖"


def test_data_flow_covers_core_chain():
    names = {a for a, _ in DATA_FLOW_EDGES} | {b for _, b in DATA_FLOW_EDGES}
    for required in (
        "SourceObservation", "FiledMessage", "ReceivedMessage", "Evidence",
        "IntelWorkItem", "NPCAssessment", "IntelBrief", "PlotProposal",
        "CommanderDecision", "ApprovedPlot", "Chart",
    ):
        assert required in names


# ── 角色权限矩阵与防泄漏 ──

def test_every_role_has_scopes():
    for role in ActorRole:
        scopes = role_readable_scopes(role)
        assert isinstance(scopes, frozenset)
        assert len(scopes) > 0


def test_forbidden_scopes_defined():
    assert "actual_enemy" in FORBIDDEN_SCOPES
    assert "internal_truth_ref" in FORBIDDEN_SCOPES
    assert "unreceived_messages" in FORBIDDEN_SCOPES


def test_no_role_reads_forbidden_scopes():
    for role in ActorRole:
        scopes = role_readable_scopes(role)
        assert scopes.isdisjoint(FORBIDDEN_SCOPES), (
            f"{role} 的可见域包含禁读域: {scopes & FORBIDDEN_SCOPES}"
        )


def test_player_cannot_read_in_transit():
    # D1：玩家只能阅读真正送达旗舰的材料
    assert not role_can_read(ActorRole.PLAYER, "transit")
    assert role_can_read(ActorRole.PLAYER, "inbox")


def test_comms_officer_reads_transit_but_not_god_view():
    assert role_can_read(ActorRole.COMMS_OFFICER, "transit")
    assert not role_can_read(ActorRole.COMMS_OFFICER, "actual_enemy")


def test_unknown_scope_denied():
    assert not role_can_read(ActorRole.PLAYER, "nonexistent_scope")


def test_player_visible_scopes_allowlist():
    from src.intel.contracts import PLAYER_VISIBLE_SCOPES
    # 玩家 API 只下发：收报档案、公开判断、已批准标图、工作队列
    assert PLAYER_VISIBLE_SCOPES == frozenset({
        "inbox", "briefs_submitted", "approved_plots", "work_queue",
    })
    assert PLAYER_VISIBLE_SCOPES.isdisjoint(FORBIDDEN_SCOPES)


def test_role_scope_pairs_are_declared():
    # RoleScope 声明（角色, 可见域）白名单——权限控制发生在状态转换层（§八）
    pairs = {(r, s) for r, s in RoleScope.select()}
    assert (ActorRole.INTEL_OFFICER, "evidence_scoped") in pairs
    assert (ActorRole.COMMS_OFFICER, "transit") in pairs
    assert (ActorRole.PLAYER, "approved_plots") in pairs
    for role, scope in pairs:
        assert scope not in FORBIDDEN_SCOPES


# ── S3 JudgmentPolicy 接口（不锁定维度，D20）──

def test_judgment_policy_protocol_satisfied_by_dummy():
    import inspect
    class DummyPolicy:
        def assess(self, work_item, evidence, actor, dice):
            return AssessmentDraft()
    # runtime_checkable Protocol：方法签名存在即可
    assert isinstance(DummyPolicy(), JudgmentPolicy)
    assert hasattr(JudgmentPolicy, "assess")


def test_assessment_draft_open_dimensions():
    draft = AssessmentDraft()
    assert draft.claims == []
    assert draft.confidence_dimensions == {}
    # 置信度是开放多维 dict（D8/D20：维度由 S3 定，S2 不锁定）
    draft.confidence_dimensions["source_reliability"] = 0.7
    assert draft.confidence_dimensions["source_reliability"] == 0.7


def test_judgment_dice_structure():
    dice = JudgmentDice(
        record_id="chk_001",
        level="partial",
        error_direction="overestimate",
        error_severity=0.4,
        express_certainty=0.8,
    )
    assert dice.record_id == "chk_001"
    assert dice.error_direction == "overestimate"


def test_evidence_view_has_no_internal_truth():
    fields = set(EvidenceView.model_fields.keys()) if hasattr(EvidenceView, "model_fields") else set()
    # EvidenceView 是 NPC 可见投影：不允许携带规则侧真值引用
    for banned in ("internal_truth_ref", "actual_enemy"):
        assert banned not in fields
