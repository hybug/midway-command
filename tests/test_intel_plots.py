"""S2.4 作战标图审批测试（红灯先行）。

验收（s2-intelligence-system-plan.md Phase S2.4）：
- 未批准标图不会进入正式海图
- 新证据不会静默覆盖已批准标图
- 批准、修订和否定全程可追溯
"""
from datetime import timedelta

import pytest

from src.intel import flow
from src.intel import service as intel
from src.intel import plots as plotsvc
from src.intel.contracts import (
    ApprovalStatus,
    CommCondition,
    ContactStatus,
    WorkItemStatus,
)
from src.intel.flow import intel_work_queue, process_intel, run_intelligence_cycle
from src.intel.policy import MechanicalPolicy
from src.intel.models import PlotGeometry


class _FakeWriter:
    actor_id = "fake_pilot_vs6"

    def write_report(self, view, game_time):
        return (f"CONTACT {view['classification']} x{view['count']} "
                f"BEARING {view['bearing']} DIST {view['distance_nm']} NM")


class _FakeAnalyst:
    actor_id = "fake_intel_analyst"

    def analyze(self, work_item, evidence_views, dice, profile):
        return {"narrative": "【事实】报告到达。【判断】敌主力存在。",
                "claims": [{"claim_type": "judgment", "text": "敌主力存在"}]}


from tests.test_intel_flow import (
    ScriptedRng,
    _advance,
    _dice_result,
    _detect_until_message,
    _launch,
    make_state,
)


@pytest.fixture(autouse=True)
def fake_llm_channels(monkeypatch):
    monkeypatch.setattr(flow, "_default_writer", lambda: _FakeWriter())
    monkeypatch.setattr(flow, "_default_analyst", lambda: _FakeAnalyst())


def _state_with_proposal():
    """纵切推进到「简报 + 初版标图提案已呈报」。"""
    state, msg, _ = _detect_until_message()
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    item = intel_work_queue(state)[0]
    brief = run_intelligence_cycle(state, item, policy=MechanicalPolicy(),
                                   analyst=_FakeAnalyst())
    assert brief.plot_proposal_ids, "简报应产生标图提案"
    proposal = next(p for p in state.plot_proposals
                    if p.id == brief.plot_proposal_ids[0])
    return state, proposal, msg


# ── 未批准不上图（D13）──

def test_unapproved_proposal_not_on_chart():
    state, proposal, _ = _state_with_proposal()
    assert proposal.status == ApprovalStatus.PROPOSED.value
    assert state.approved_plots == []
    # 玩家敌情公共视图：无已批准标图时直通 legacy（迁移期），不含提案几何
    view = intel.known_enemy_compat_view(state)
    assert all("APPROVED PLOT" not in e.description for e in view)


def test_geometry_from_contact():
    state, proposal, _ = _state_with_proposal()
    g = proposal.geometry
    assert g is not None
    assert g.bearing_line_deg is not None
    assert 150 <= g.distance_nm <= 240  # 报告距离量级
    assert g.bearing_from_label == "TF16"


# ── 批准 → 上图 ──

def test_approval_puts_plot_on_chart():
    state, proposal, _ = _state_with_proposal()
    plot = plotsvc.decide(state, proposal, action="approve", by="player",
                          comment="按此标图")
    assert proposal.status == ApprovalStatus.APPROVED.value
    assert len(state.approved_plots) == 1
    assert plot.state == "active"
    assert plot.current_version == 1
    assert len(plot.history) == 1
    # 接触上图联动
    contact = next(c for c in state.contacts if c.id == proposal.contact_id)
    assert contact.status == ContactStatus.PLOTTED
    # 决议与审计可追溯
    assert len(state.commander_decisions) == 1
    assert state.commander_decisions[0].action == "approve"
    assert state.intel_audit[-1].action == "plot_approve"
    # 玩家敌情公共视图切换为已批准标图
    view = intel.known_enemy_compat_view(state)
    assert len(view) == 1
    assert "APPROVED PLOT v1" in view[0].description


def test_double_approve_rejected():
    state, proposal, _ = _state_with_proposal()
    plotsvc.decide(state, proposal, action="approve")
    with pytest.raises(ValueError):
        plotsvc.decide(state, proposal, action="approve")


# ── 新证据不静默覆盖已批准标图（D14）──

def test_new_version_requires_reapproval():
    state, proposal_v1, msg = _state_with_proposal()
    plotsvc.decide(state, proposal_v1, action="approve")
    v1_lat = proposal_v1.geometry.lat

    # 新证据到达 → 新研判 → 同链新版本提案（PROPOSED，不自动上图）
    msg2 = flow.on_scout_detection(
        state, scout=state.active_scouts[0], enemy=state.actual_enemy[0],
        bearing=236.0, distance=185.0,
        result=_dice_result("success", 80),
        writer=_FakeWriter(), rng=ScriptedRng(),
    )
    state.clock.game_time = msg2.transit_eta + timedelta(minutes=1)
    process_intel(state)
    item2 = intel_work_queue(state)[0]
    brief2 = run_intelligence_cycle(state, item2, policy=MechanicalPolicy(),
                                    analyst=_FakeAnalyst())
    proposal_v2 = next(p for p in state.plot_proposals
                       if p.id == brief2.plot_proposal_ids[0])
    # 同链 + 版本递增 + 尚未上图
    assert proposal_v2.plot_id == proposal_v1.plot_id
    assert proposal_v2.version == 2
    assert proposal_v2.status == ApprovalStatus.PROPOSED.value
    # 批准前：正式海图仍是 v1
    plot = state.approved_plots[0]
    assert plot.current_version == 1
    view = intel.known_enemy_compat_view(state)
    assert "v1" in view[0].description

    # 批准 v2 → 旧版 superseded，历史保留
    plotsvc.decide(state, proposal_v2, action="approve", comment="新版更准确")
    assert plot.current_version == 2
    assert plot.state == "active"
    assert len(plot.history) == 2
    assert proposal_v1.status == ApprovalStatus.SUPERSEDED.value
    history = plotsvc.plot_chain_history(state, proposal_v1.plot_id)
    assert [h["version"] for h in history] == [1, 2]
    assert history[0]["change_summary"] and history[1]["change_summary"]


# ── 驳回 / 暂缓 / 修订请求 ──

def test_reject_is_terminal_and_chart_untouched():
    state, proposal, _ = _state_with_proposal()
    plotsvc.decide(state, proposal, action="reject", comment="证据不足")
    assert proposal.status == ApprovalStatus.REJECTED.value
    assert state.approved_plots == []
    with pytest.raises(ValueError):
        plotsvc.decide(state, proposal, action="approve")


def test_defer_then_resubmit():
    state, proposal, _ = _state_with_proposal()
    plotsvc.decide(state, proposal, action="defer")
    assert proposal.status == ApprovalStatus.DEFERRED.value
    plotsvc.reopen_deferred(state, proposal, by="player")
    assert proposal.status == ApprovalStatus.PROPOSED.value


def test_request_revision_then_revised_version():
    state, proposal, _ = _state_with_proposal()
    plotsvc.decide(state, proposal, action="request_revision",
                   comment="把不确定圈收窄后再报")
    assert proposal.status == ApprovalStatus.REVISION_REQUESTED.value
    revised = plotsvc.revise_plot_proposal(
        state, proposal, author_actor_id="intel_officer",
        change_summary="按指挥官意见收窄不确定圈",
        geometry=PlotGeometry(
            lat=proposal.geometry.lat, lon=proposal.geometry.lon,
            uncertainty_radius_nm=15,
        ),
    )
    assert revised.version == 2
    assert revised.plot_id == proposal.plot_id
    assert revised.status == ApprovalStatus.PROPOSED.value
    plotsvc.decide(state, revised, action="approve")
    assert state.approved_plots[0].current_version == 2


def test_partial_approval_flow():
    state, proposal, _ = _state_with_proposal()
    plotsvc.decide(state, proposal, action="partial_approve",
                   items_approved=["contact_main"], comment="先批主机接触")
    assert proposal.status == ApprovalStatus.PARTIALLY_APPROVED.value
    assert state.approved_plots == []  # 部分批准不上图
    plotsvc.decide(state, proposal, action="approve")
    assert len(state.approved_plots) == 1


# ── 参谋长批注（追加式）──

def test_chief_annotation_appends():
    state, proposal, _ = _state_with_proposal()
    a1 = plotsvc.annotate_proposal(state, proposal, by="browning",
                                   stance="endorse", note="同意呈报")
    a2 = plotsvc.annotate_proposal(state, proposal, by="browning",
                                   stance="concern", note="数量建议下调一档")
    assert proposal.annotations == [a1, a2]  # 追加不覆盖
    assert proposal.annotations[1]["by"] == "browning"
