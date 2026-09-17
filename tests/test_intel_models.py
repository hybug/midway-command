"""S2.2 电文、证据与角色信念测试（Phase S2.2，红灯先行）。

验收（s2-intelligence-system-plan.md Phase S2.2）：
- 同一报告不会进入所有 NPC 的全局敌情表（BeliefState 按角色隔离）
- 勘误不会覆盖原始电文（追加制）
- 玩家和 NPC 只能看到权限内证据（access_policy + EvidenceView 投影）
"""
from datetime import datetime, timedelta, timezone

import pytest

from src.intel.contracts import (
    ActorRole,
    ApprovalStatus,
    CommCondition,
    ContactStatus,
    EvidenceStatus,
    MessageStatus,
    SourceType,
    WorkPriority,
    approval_transitions,
    contact_transitions,
    message_transitions,
)
from src.intel.judgment import EvidenceView
from src.intel.models import (
    BeliefState,
    ContactHypothesis,
    Evidence,
    IntelAuditEntry,
    MessageEnvelope,
    NPCClaim,
)
from src.intel import service as intel
from src.state import GameClock, GameState, Position

T0 = datetime(1942, 6, 4, 5, 0, tzinfo=timezone.utc)


def make_state():
    return GameState(clock=GameClock(game_time=T0), rng_seed=42)


def make_envelope(**kw):
    base = dict(
        sender_id="vs6_pilot",
        sender_call_sign="VS-6",
        recipient_ids=["tf16_flag"],
        priority=WorkPriority.URGENT,
        message_kind="scout_report",
        observed_at=T0 - timedelta(minutes=10),
        filed_at=T0,
        raw_text="ENEMY SPOTTED 233 DEG 195 NM 4 CV",
    )
    base.update(kw)
    return MessageEnvelope(**base)


# ── 消息状态机与收报室 ──

def test_message_full_lifecycle_with_history():
    state = make_state()
    msg = intel.file_message(state, make_envelope(), by="vs6_pilot")
    assert msg.status == MessageStatus.FILED
    intel.mark_in_transit(state, msg, by="comm_chain")
    intel.receive_message(state, msg, by="tf16_comms",
                          condition=CommCondition.COMPLETE)
    assert msg.status == MessageStatus.RECEIVED
    assert msg.received_at is not None
    intel.log_message(state, msg, by="radio_officer")
    intel.route_message(state, msg, by="radio_officer", route_to="intel_officer")
    intel.process_message(state, msg, by="intel_officer")
    intel.archive_message(state, msg, by="system")
    assert msg.status == MessageStatus.ARCHIVED
    assert [h.to_status for h in msg.status_history] == [
        MessageStatus.FILED, MessageStatus.IN_TRANSIT, MessageStatus.RECEIVED,
        MessageStatus.LOGGED, MessageStatus.ROUTED, MessageStatus.PROCESSED,
        MessageStatus.ARCHIVED,
    ]


def test_illegal_message_transition_raises():
    state = make_state()
    msg = intel.file_message(state, make_envelope(), by="vs6_pilot")
    with pytest.raises(ValueError):
        intel.receive_message(state, msg, by="tf16_comms")  # FILED → RECEIVED 非法


def test_player_inbox_only_received_messages():
    state = make_state()
    m1 = intel.file_message(state, make_envelope(), by="vs6_pilot")
    m2 = intel.file_message(
        state,
        make_envelope(raw_text="SECOND CONTACT REPORT 210 DEG 150 NM"),
        by="vs6_pilot",
    )
    intel.mark_in_transit(state, m1, by="comm_chain")
    intel.mark_in_transit(state, m2, by="comm_chain")
    # m1 送达，m2 仍在途
    intel.receive_message(state, m1, by="tf16_comms")
    inbox = intel.player_inbox(state)
    ids = {m.id for m in inbox}
    assert m1.id in ids and m2.id not in ids
    # 未送达电文原文不得经任何玩家视图泄露
    assert m2.raw_text not in str(inbox)


def test_lost_message_never_in_inbox():
    state = make_state()
    msg = intel.file_message(state, make_envelope(), by="vs6_pilot")
    intel.mark_in_transit(state, msg, by="comm_chain")
    intel.lose_message(state, msg, by="comm_chain", reason="TBS 静默")
    assert msg.status == MessageStatus.LOST
    assert intel.player_inbox(state) == []
    assert msg.raw_text not in str(intel.player_inbox(state))


# ── 勘误：追加而非覆盖 ──

def test_correction_appends_never_overwrites():
    state = make_state()
    msg = intel.file_message(state, make_envelope(), by="vs6_pilot")
    intel.mark_in_transit(state, msg, by="comm_chain")
    intel.receive_message(state, msg, by="tf16_comms")
    original_text = msg.raw_text
    correction = intel.correct_message(
        state, old=msg, raw_text="CORRECTION: 2 CV NOT 4",
        by="vs6_pilot", reason="识别更正",
    )
    # 原电文不被覆盖
    assert msg.raw_text == original_text
    assert msg.status == MessageStatus.CORRECTED
    # 新勘误电文引用旧电文
    assert correction.supersedes_message_id == msg.id
    assert correction.message_kind == "correction"
    assert correction.id != msg.id
    assert correction.raw_text == "CORRECTION: 2 CV NOT 4"
    # 旧电文出现在玩家收报室（原文保留 + CORRECTED 标记）
    inbox = intel.player_inbox(state)
    assert any(m.id == msg.id and m.status == MessageStatus.CORRECTED for m in inbox)


def test_correction_requires_received_message():
    state = make_state()
    msg = intel.file_message(state, make_envelope(), by="vs6_pilot")
    with pytest.raises(ValueError):
        intel.correct_message(state, old=msg, raw_text="X", by="vs6_pilot",
                              reason="too early")


# ── 证据账本：不可变 + 时间链 + 权限视图 ──

def received_msg_with_evidence(state):
    msg = intel.file_message(state, make_envelope(), by="vs6_pilot")
    intel.mark_in_transit(state, msg, by="comm_chain")
    intel.receive_message(state, msg, by="tf16_comms")
    ev = intel.register_evidence(
        state, message=msg, source_id="VS-6", source_type=SourceType.CARRIER_SCOUT,
        position=Position(lat=30.2, lon=-178.1),
        reported={"bearing": 233, "distance_nm": 195, "count": 4},
        access_roles=[ActorRole.INTEL_OFFICER, ActorRole.CHIEF_OF_STAFF],
        summary="VS-6 报告方位233°距离195海里4艘航母",
    )
    return msg, ev


def test_evidence_registered_from_received_message():
    state = make_state()
    msg, ev = received_msg_with_evidence(state)
    assert ev.status == EvidenceStatus.ACTIVE
    assert ev.message_id == msg.id
    assert ev.observed_at <= ev.received_at  # 时间链
    assert intel.validate_time_chain(ev) is True


def test_evidence_time_chain_violation_detected():
    state = make_state()
    msg, ev = received_msg_with_evidence(state)
    bad = ev.model_copy(update={
        "observed_at": ev.received_at + timedelta(hours=1),
    })
    with pytest.raises(ValueError):
        intel.validate_time_chain(bad, raise_on_violation=True)


def test_evidence_supersede_keeps_original():
    state = make_state()
    msg, ev = received_msg_with_evidence(state)
    ev2 = intel.supersede_evidence(
        state, old=ev,
        position=Position(lat=30.4, lon=-178.4),
        reported={"bearing": 235, "distance_nm": 190, "count": 2},
        summary="勘误后证据",
        by="intel_officer",
    )
    assert ev.status == EvidenceStatus.SUPERSEDED
    assert ev.reported == {"bearing": 233, "distance_nm": 195, "count": 4}  # 原值不变
    assert ev2.supersedes_evidence_id == ev.id
    assert ev2.status == EvidenceStatus.ACTIVE


def test_evidence_view_permission_filtering():
    state = make_state()
    msg, ev = received_msg_with_evidence(state)
    # 情报参谋在 access_policy 内 → 可读
    view = intel.evidence_view(ev, ActorRole.INTEL_OFFICER)
    assert isinstance(view, EvidenceView)
    assert view.evidence_id == ev.id
    # 舰长不在 access_policy → 拒绝
    with pytest.raises(PermissionError):
        intel.evidence_view(ev, ActorRole.CAPTAIN)
    # 可见集合过滤
    visible = intel.visible_evidence(state, ActorRole.INTEL_OFFICER)
    assert [e.id for e in visible] == [ev.id]
    assert intel.visible_evidence(state, ActorRole.NAVIGATOR) == []


def test_evidence_view_has_no_truth_fields():
    # 模型层静态防泄漏：Evidence/EvidenceView 不携带规则侧真值字段
    for model in (Evidence, EvidenceView):
        fields = set(model.model_fields.keys())
        assert "internal_truth_ref" not in fields
        assert "actual_enemy" not in fields


# ── 信念隔离与接触假设 ──

def test_beliefs_isolated_per_actor():
    state = make_state()
    msg, ev = received_msg_with_evidence(state)
    b_intel = intel.belief_for(state, "intel_officer")
    b_cos = intel.belief_for(state, "chief_of_staff")
    c1 = intel.add_contact(
        state, belief=b_intel, classification="CV",
        position=Position(lat=30.2, lon=-178.1),
        evidence_ids=[ev.id], first_seen_at=ev.observed_at or T0,
        last_seen_at=ev.observed_at or T0,
        by="intel_officer", reason="VS-6 报告",
    )
    # 参谋长未形成自己的接触 —— 同一报告不会进入所有角色的敌情表
    assert [c.id for c in intel.contacts_of(state, b_intel)] == [c1.id]
    assert intel.contacts_of(state, b_cos) == []
    assert b_intel.actor_id != b_cos.actor_id


def test_contact_transition_with_audit():
    state = make_state()
    msg, ev = received_msg_with_evidence(state)
    b = intel.belief_for(state, "intel_officer")
    c = intel.add_contact(
        state, belief=b, classification="CV",
        position=Position(lat=30.2, lon=-178.1),
        evidence_ids=[ev.id], first_seen_at=T0, last_seen_at=T0,
        by="intel_officer", reason="initial",
    )
    intel.transition_contact(
        state, contact=c, to_status=ContactStatus.TENTATIVE,
        by="intel_officer", reason="情报参谋暂定", evidence_ids=[ev.id],
    )
    assert c.status == ContactStatus.TENTATIVE
    # 信念变化审计：作者/时间/理由/证据
    entry = state.intel_audit[-1]
    assert entry.actor_id == "intel_officer"
    assert entry.target_id == c.id
    assert entry.reason == "情报参谋暂定"
    assert ev.id in entry.evidence_ids
    with pytest.raises(ValueError):
        intel.transition_contact(
            state, contact=c, to_status=ContactStatus.PLOTTED,
            by="intel_officer", reason="越级上图",
        )


def test_association_candidates_no_silent_merge():
    state = make_state()
    msg, ev = received_msg_with_evidence(state)
    b = intel.belief_for(state, "intel_officer")
    c1 = intel.add_contact(state, belief=b, classification="CV",
                           position=Position(lat=30.2, lon=-178.1),
                           evidence_ids=[ev.id], first_seen_at=T0, last_seen_at=T0,
                           by="intel_officer", reason="r1")
    c2 = intel.add_contact(state, belief=b, classification="unknown",
                           position=Position(lat=30.9, lon=-178.9),
                           evidence_ids=[ev.id], first_seen_at=T0, last_seen_at=T0,
                           by="intel_officer", reason="r2")
    intel.record_association_candidate(state, contact=c1, candidate_id=c2.id,
                                       by="intel_officer", reason="方位相近")
    # 只登记候选，不合并：两个接触都仍独立存在
    assert c2.id in c1.association_candidates
    assert {c.id for c in intel.contacts_of(state, b)} == {c1.id, c2.id}


# ── NPCClaim 审计 ──

def test_npc_claim_records_lineage():
    state = make_state()
    claim = intel.record_claim(
        state, assessment_id="AS-000001", actor_id="intel_officer",
        claim_type="judgment",
        text="敌航母主力位于西南，约2艘",
        based_on_evidence_ids=["EV-000001"],
        tool_call_ids=["chk_000001"],
        confidence_dimensions={"position": 0.6, "identity": 0.5},
    )
    assert claim.id.startswith("CL-")
    assert claim.actor_id == "intel_officer"
    assert claim.based_on_evidence_ids == ["EV-000001"]
    assert claim.claim_type == "judgment"  # 区分 事实/判断/来源
    assert state.claims[-1].id == claim.id


# ── known_enemy 兼容层 ──

def test_known_enemy_compat_view_falls_back_to_legacy():
    state = make_state()
    from src.state import EnemyKnown
    legacy = EnemyKnown(
        position=Position(lat=30.0, lon=-178.0),
        description="SBD: 敌航母约 4 艘",
        confidence="medium", source="SBD-1", reported_at=T0,
    )
    state.known_enemy.append(legacy)
    view = intel.known_enemy_compat_view(state)
    assert list(view) == [legacy]  # ApprovedPlot 出现前直通旧表


def test_next_id_sequence():
    state = make_state()
    assert intel.next_id(state, "MSG") == "MSG-000001"
    assert intel.next_id(state, "MSG") == "MSG-000002"
    assert intel.next_id(state, "EV") == "EV-000001"
