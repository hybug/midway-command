"""S8 UI.3 INTEL 接口测试（SITREP / EVIDENCE 白名单视图，红灯先行）。

验收：
- SITREP：已批准接触数/最近批准/未决冲突/待处理简报（全部由玩家可读对象派生）
- EVIDENCE：只显示已呈报（简报/已批准标图）引用的证据 + 使用者跳转数据
- 未呈报证据与规则侧真值不可见
"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import server as server_module
from src.intel import service as intel
from src.intel.contracts import ActorRole, ApprovalStatus, SourceType
from src.intel.models import IntelBrief, MessageEnvelope, NPCAssessment
from src.state import GameState, GameClock

NOW = datetime(1942, 5, 7, 10, 0, tzinfo=timezone.utc)


def _client_with(state):
    server_module.game_state = state
    return TestClient(server_module.app)


def _state():
    return GameState(clock=GameClock(game_time=NOW))


def _register_contact(s, call_sign="VS5-1", summary="米西马以北两艘航母"):
    msg = MessageEnvelope(
        id=f"MSG-{len(s.messages) + 1:06d}",
        sender_id=call_sign, sender_call_sign=call_sign,
        observed_at=NOW - timedelta(minutes=30),
        received_at=NOW - timedelta(minutes=10),
        raw_text=summary, status=__import__("src.intel.contracts",
                                            fromlist=["MessageStatus"]).MessageStatus.LOGGED,
    )
    s.messages.append(msg)
    return intel.register_evidence(
        s, message=msg, source_id=call_sign,
        source_type=SourceType.CARRIER_SCOUT,
        access_roles=[ActorRole.INTEL_OFFICER], summary=summary,
    )


def test_sitrep_counts_derived_from_player_readable_objects():
    s = _state()
    ev = _register_contact(s)
    s.intel_briefs.append(IntelBrief(id="BRF-000001", author_actor_id="tf17_intel",
                                     new_evidence_ids=[ev.id], status="proposed"))
    client = _client_with(s)
    sit = client.get("/intel/sitrep").json()
    assert sit["approved_contacts"] == 0
    assert sit["pending_briefs"] == 1
    assert sit["latest_brief"]["id"] == "BRF-000001"
    assert sit["open_conflicts"] == []


def test_evidence_visible_only_after_submission():
    s = _state()
    ev_submitted = _register_contact(s, "VS5-1", "已呈报证据摘要")
    ev_hidden = _register_contact(s, "VS5-2", "未呈报证据摘要")
    assessment = NPCAssessment(id="AS-000001", author_actor_id="tf17_intel",
                               based_on_evidence_ids=[ev_submitted.id])
    s.assessments.append(assessment)
    s.intel_briefs.append(IntelBrief(id="BRF-000001", author_actor_id="tf17_intel",
                                     new_evidence_ids=[ev_submitted.id],
                                     changed_judgments=[assessment.id],
                                     status=ApprovalStatus.PROPOSED.value))
    client = _client_with(s)
    data = client.get("/intel/evidence").json()["evidence"]
    ids = [e["id"] for e in data]
    assert ev_submitted.id in ids and ev_hidden.id not in ids
    row = next(e for e in data if e["id"] == ev_submitted.id)
    assert row["used_by_assessment_ids"] == ["AS-000001"]
    assert "未呈报证据摘要" not in str(data)          # 未呈报内容不可见


def test_evidence_visible_via_approved_plot():
    s = _state()
    ev = _register_contact(s, "VS5-3", "标图引用证据")
    from src.intel.models import ApprovedPlot, PlotProposal
    proposal = PlotProposal(id="PP-000001", plot_id="PLOT-000001", version=1,
                            author_actor_id="tf17_intel",
                            based_on_evidence_ids=[ev.id])
    s.plot_proposals.append(proposal)
    # 未批准 → 不可见
    client = _client_with(s)
    assert client.get("/intel/evidence").json()["evidence"] == []
    # 批准 → 可见
    s.approved_plots.append(ApprovedPlot(plot_id="PLOT-000001", current_version=1))
    ids = [e["id"] for e in client.get("/intel/evidence").json()["evidence"]]
    assert ev.id in ids
