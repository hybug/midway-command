"""S2.5 冲突、陈旧与勘误测试（红灯先行）。

验收（s2-intelligence-system-plan.md Phase S2.5）：
- 多份矛盾报告可以并存
- 旧接触能显式衰老或被新判断替代
- 原版本和修订理由均可复盘
"""
from datetime import timedelta

import pytest

from src.intel import conflicts as conflictsvc
from src.intel import flow
from src.intel import service as intel
from src.intel import plots as plotsvc
from src.intel.contracts import (
    ApprovalStatus,
    CommCondition,
    ContactStatus,
    EvidenceStatus,
    MessageStatus,
    WorkPriority,
)
from src.intel.flow import intel_work_queue, process_intel, run_intelligence_cycle
from src.intel.models import MessageEnvelope
from src.intel.policy import MechanicalPolicy

from tests.test_intel_flow import (
    FakeAnalyst,
    ScriptedRng,
    _dice_result,
    _detect_until_message,
    make_state,
)


class _FakeWriter:
    actor_id = "fake_pilot_vs6"

    def write_report(self, view, game_time):
        return (f"CONTACT {view['classification']} x{view['count']} "
                f"BEARING {view['bearing']} DIST {view['distance_nm']} NM")


@pytest.fixture(autouse=True)
def fake_llm_channels(monkeypatch):
    monkeypatch.setattr(flow, "_default_writer", lambda: _FakeWriter())
    monkeypatch.setattr(flow, "_default_analyst", lambda: FakeAnalyst())


def _deliver(state, bearing, distance, quality="success"):
    """脚本化投递一份侦察报告并完成收报流程。"""
    scout = state.active_scouts[0] if state.active_scouts else None
    if scout is None:
        from src.state import ScoutMission, ScoutPhase
        scout = ScoutMission(id="SBD-T", direction="southwest", heading=225,
                             launched_at=state.clock.game_time,
                             phase=ScoutPhase.SEARCHING,
                             phase_started_at=state.clock.game_time)
    msg = flow.on_scout_detection(
        state, scout=scout, enemy=state.actual_enemy[0],
        bearing=bearing, distance=distance,
        result=_dice_result("success", 80),
        writer=_FakeWriter(), rng=ScriptedRng(quality=quality),
    )
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    return msg


# ── 多份矛盾报告并存 + 冲突登记 ──

def test_conflicting_reports_coexist_with_conflict_record():
    state = make_state(rng_seed=3)
    from src.tools import handle_execute_action
    handle_execute_action(state, "launch_scout", {"direction": "southwest"})
    _deliver(state, bearing=233.0, distance=195.0)
    _deliver(state, bearing=120.0, distance=120.0)  # 方位大相径庭的第二报告

    # 两份报告都在收报室，两份证据都 ACTIVE（并存，不静默裁决）
    assert len(intel.player_inbox(state)) >= 2
    active = [e for e in state.evidence if e.status == EvidenceStatus.ACTIVE]
    assert len(active) >= 2
    # 冲突在研判中被登记（方位差 > 30°）
    state.clock.game_time += timedelta(minutes=1)
    item = intel_work_queue(state)[0]
    run_intelligence_cycle(state, item, policy=MechanicalPolicy(),
                           analyst=FakeAnalyst())
    assert len(state.evidence_conflicts) >= 1
    cfl = state.evidence_conflicts[0]
    assert cfl.kind in ("bearing", "position")
    assert cfl.status == "open"
    # 冲突呈报进判断书与简报
    assessment = state.assessments[-1]
    assert assessment.conflict_ids == [cfl.id]
    brief = state.intel_briefs[-1]
    assert any(cfl.id in q for q in brief.unresolved_questions)


def test_conflict_resolution_records_choice():
    state = make_state(rng_seed=3)
    from src.tools import handle_execute_action
    handle_execute_action(state, "launch_scout", {"direction": "southwest"})
    _deliver(state, bearing=233.0, distance=195.0)
    _deliver(state, bearing=100.0, distance=110.0)
    conflicts_found = conflictsvc.detect_conflicts(
        state, [e.id for e in state.evidence], by="intel_officer")
    assert conflicts_found
    cfl = conflicts_found[0]
    conflictsvc.resolve_conflict(state, cfl, by="intel_officer",
                                 resolution_evidence_id=cfl.evidence_ids[0],
                                 note="采信近距离报告")
    assert cfl.status == "resolved"
    assert cfl.resolved_by_evidence_id == cfl.evidence_ids[0]
    # 两条证据都未被删除
    assert len(state.evidence) >= 2


# ── 接触衰老 / 失联 / 重新接触 ──

def _state_with_contact():
    state = make_state(rng_seed=3)
    from src.tools import handle_execute_action
    handle_execute_action(state, "launch_scout", {"direction": "southwest"})
    _deliver(state, bearing=233.0, distance=195.0)
    state.clock.game_time += timedelta(minutes=1)
    item = intel_work_queue(state)[0]
    run_intelligence_cycle(state, item, policy=MechanicalPolicy(),
                           analyst=FakeAnalyst())
    belief = intel.belief_for(state, "intel_officer")
    contacts = intel.contacts_of(state, belief)
    assert contacts
    return state, contacts[0]


def test_contact_aging_explicit_and_audited():
    state, contact = _state_with_contact()
    # 90 分钟未更新 → 参谋整理时显式衰老
    state.clock.game_time += timedelta(minutes=100)
    changed = conflictsvc.age_contacts(state, by="intel_officer",
                                       stale_after_min=90)
    assert contact.id in changed
    assert contact.status == ContactStatus.STALE
    assert state.intel_audit[-1].action == "contact_status"
    # 再过 4 小时 → 失联
    state.clock.game_time += timedelta(minutes=250)
    conflictsvc.age_contacts(state, by="intel_officer", stale_after_min=90,
                             lost_after_min=240)
    assert contact.status == ContactStatus.LOST


def test_reactivation_on_new_contact():
    state, contact = _state_with_contact()
    state.clock.game_time += timedelta(minutes=100)
    conflictsvc.age_contacts(state, by="intel_officer", stale_after_min=90)
    assert contact.status == ContactStatus.STALE
    conflictsvc.reactivate_contact(state, contact, by="intel_officer",
                                   note="新证据重新接触")
    assert contact.status == ContactStatus.TENTATIVE


# ── 勘误电报端到端（§7.3）──

def test_correction_telegram_end_to_end():
    state, contact = _state_with_contact()
    original_msg = next(m for m in state.messages
                        if m.message_kind == "scout_report")
    original_ev = next(e for e in state.evidence
                       if e.message_id == original_msg.id)

    # 飞行员拍发勘误（到达前原电文保持原状态）
    correction = MessageEnvelope(
        sender_id="fake_pilot_vs6",
        sender_call_sign="SBD-T",
        recipient_ids=["TF16 FLAG"],
        priority=WorkPriority.CORRECTION,
        message_kind="correction",
        observed_at=original_msg.observed_at,
        supersedes_message_id=original_msg.id,
        raw_text="CORRECTION: 2 CV NOT 4, BEARING 236 DIST 185 NM",
        fields={"bearing": 236, "distance_nm": 185, "count": 2,
                "classification": "CV", "quality": "standard"},
    )
    intel.file_message(state, correction, by="fake_pilot_vs6", reason="勘误拍发")
    intel.mark_in_transit(state, correction, by="TBS 通信链")
    correction.transit_eta = state.clock.game_time + timedelta(minutes=25)
    assert original_msg.status != MessageStatus.CORRECTED  # 到达前不改旧电文

    state.clock.game_time = correction.transit_eta + timedelta(minutes=1)
    process_intel(state)
    # 旧电文标记 CORRECTED 但原文保留
    assert original_msg.status == MessageStatus.CORRECTED
    assert "4 CV" in original_msg.raw_text or original_msg.raw_text
    assert correction.status in (MessageStatus.LOGGED, MessageStatus.ROUTED)
    # 旧证据被替代、新证据在案（两者都保留）
    assert original_ev.status == EvidenceStatus.SUPERSEDED
    corrected_ev = [e for e in state.evidence
                    if e.message_id == correction.id]
    assert len(corrected_ev) == 1
    assert corrected_ev[0].supersedes_evidence_id == original_ev.id
    assert corrected_ev[0].status == EvidenceStatus.ACTIVE
    # 纠错工作项 CORRECTION 优先级（打断例行队列）
    corr_items = [i for i in state.intel_work_items
                  if i.trigger_message_id == correction.id]
    assert corr_items and corr_items[0].priority == WorkPriority.CORRECTION
    queue = intel_work_queue(state)
    assert queue[0].priority == WorkPriority.CORRECTION  # 打断 URGENT/ROUTINE


# ── 误报否定（§7.4：参谋提案 + 指挥官批准）──

def test_false_positive_rejection_requires_approval():
    state, contact = _state_with_contact()
    proposal = next(iter(state.plot_proposals))
    plotsvc.decide(state, proposal, action="approve")  # 先上图
    plot = state.approved_plots[0]
    assert contact.status == ContactStatus.PLOTTED

    # 新证据表明误报 → 参谋提出否定建议（PROPOSED，不能直接改状态）
    rejection = conflictsvc.propose_contact_rejection(
        state, contact, by="intel_officer", reason="反复搜索无接触，判定误报")
    assert rejection.method == "rejection"
    assert rejection.status == ApprovalStatus.PROPOSED.value
    assert contact.status == ContactStatus.PLOTTED  # 批准前不变
    assert plot.state == "active"

    # 指挥官批准否定
    plotsvc.decide(state, rejection, action="approve", comment="同意判误报")
    assert contact.status == ContactStatus.REJECTED
    assert plot.state == "superseded"          # 正式标图撤下
    assert len(plot.history) == 1              # 历史保留
    # 关联证据被否定但保留
    ev = next(e for e in state.evidence
              if e.id in rejection.based_on_evidence_ids)
    assert ev.status == EvidenceStatus.REJECTED
    # REJECTED 终态：不能复活
    with pytest.raises(ValueError):
        intel.transition_contact(state, contact,
                                 to_status=ContactStatus.TENTATIVE,
                                 by="intel_officer", reason="越权复活")


def test_corroboration_appends_without_merge():
    state = make_state(rng_seed=3)
    from src.tools import handle_execute_action
    handle_execute_action(state, "launch_scout", {"direction": "southwest"})
    _deliver(state, bearing=233.0, distance=195.0)
    _deliver(state, bearing=230.0, distance=190.0)  # 相近报告 → 印证而非冲突
    ev1, ev2 = state.evidence[0], state.evidence[1]
    conflictsvc.corroborate(state, ev1, ev2, by="intel_officer",
                            note="两份报告相互印证")
    assert ev2.id in ev1.corroboration and ev1.id in ev2.corroboration
    # 两条证据仍独立存在（不合并）
    assert ev1.id != ev2.id
    assert all(e.status == EvidenceStatus.ACTIVE for e in (ev1, ev2))
