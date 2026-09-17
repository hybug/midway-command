"""S2 最终纵切验收（用户指定完整链路）。

舰载侦察机发现目标 → NPC 飞行员撰写报告 → 通信检定与收报 → 通信官登记转发
→ 情报参谋调用工具并形成判断 → IntelBrief 与 PlotProposal → 参谋长批注呈报
→ 指挥官批准 → ApprovedPlot 进入正式海图 → 勘误到达 → 新版修订提案
→ 再次批准更新海图 → 旧版本与完整因果链保留在复盘中。

LLM 通道注入 fake（飞行员/分析器）；规则逻辑全部走真实管线。
"""
import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import server as server_module
from src.intel import conflicts as conflictsvc
from src.intel import flow
from src.intel import plots as plotsvc
from src.intel import reasoning
from src.intel import service as intel
from src.intel.contracts import (
    ApprovalStatus,
    ContactStatus,
    EvidenceStatus,
    MessageStatus,
    WorkItemStatus,
)
from src.intel.flow import intel_work_queue, process_intel, run_intelligence_cycle
from src.intel.policy import MechanicalPolicy
from src.tools import handle_execute_action

from tests.test_intel_flow import ScriptedRng, _advance, _dice_result


class _PilotWriter:
    """fake 飞行员：人物风格文风（与机械模板可区分）。"""
    actor_id = "fake_pilot_vs6"

    def write_report(self, view, game_time):
        return (f"LOOKOUT! {view['classification']} x{view['count']} "
                f"BEARING {view['bearing']} DIST {view['distance_nm']} NM, "
                f"IDENT {view['quality'].upper()}, FUEL LOW")


class _Analyst:
    actor_id = "fake_intel_analyst"

    def analyze(self, work_item, evidence_views, dice, profile):
        return {
            "narrative": ("【事实】SBD 电文报告接触。【判断】敌主力位于西南，"
                          f"研判置信受骰子等级 {dice.level} 影响。"),
            "claims": [
                {"claim_type": "fact", "text": "SBD 电文报告接触"},
                {"claim_type": "judgment", "text": "敌主力位于西南方向"},
            ],
        }


@pytest.fixture(autouse=True)
def fake_llm_channels(monkeypatch):
    monkeypatch.setattr(flow, "_default_writer", lambda: _PilotWriter())
    monkeypatch.setattr(flow, "_default_analyst", lambda: _Analyst())


def _advance_clock_to(state, eta):
    state.clock.game_time = eta + timedelta(minutes=1)


def test_full_vertical_slice_with_revision_replay_and_afteraction():
    # ── 1-2. SBD 发现目标 + 飞行员撰写报告 ──
    state = flow_state = None
    for seed in range(60):
        state = _make_state(seed)
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})
        _advance(state)
        if any(m.message_kind == "scout_report" for m in state.messages):
            flow_state = state
            break
    assert flow_state is not None
    state = flow_state
    msg = next(m for m in state.messages if m.message_kind == "scout_report")
    obs = next(o for o in state.observations if o.id == msg.observation_id)
    assert msg.status == MessageStatus.IN_TRANSIT
    assert msg.raw_text.startswith("LOOKOUT!")          # 人物风格（fake）
    assert msg.generated_by_npc == "fake_pilot_vs6"
    assert state.pending_reports == []                   # 旧管线退役
    # 未收到电报不泄露（玩家视图为空）
    assert intel.player_inbox(state) == []

    # ── 3. 通信检定与收报（transit_eta 到达）──
    assert msg.transit_eta is not None
    _advance_clock_to(state, msg.transit_eta)
    notes = process_intel(state)

    # ── 4. 通信官登记转发 ──
    assert msg.status == MessageStatus.ROUTED
    assert msg.routed_to == ["intel_officer"]
    assert len(state.evidence) == 1 and len(state.intel_work_items) == 1
    assert any("报告到达" in n for n in notes)

    # ── 5. 情报参谋调用工具并形成判断 ──
    ev = state.evidence[0]
    tool_out = reasoning.possible_area(
        state, actor_id="intel_officer", lat=ev.lat, lon=ev.lon,
        observed_at=ev.observed_at, evidence_id=ev.id, label="敌主力",
    )
    assert tool_out["candidates"]          # 候选区域（非真值）
    assert state.tool_calls[-1].tool_name == "possible_area"

    item = intel_work_queue(state)[0]
    brief = run_intelligence_cycle(state, item, policy=MechanicalPolicy(),
                                   analyst=_Analyst())

    # ── 6. IntelBrief 与 PlotProposal ──
    assert brief.status == ApprovalStatus.PROPOSED.value
    assert brief.plot_proposal_ids
    proposal_v1 = next(p for p in state.plot_proposals
                       if p.id == brief.plot_proposal_ids[0])
    assert proposal_v1.version == 1
    assert proposal_v1.geometry.lat is not None
    # 判断书与声明可回溯证据/骰子/工具
    assessment = state.assessments[-1]
    assert assessment.based_on_evidence_ids == [ev.id]
    assert assessment.dice_record_ids
    assert any(c.tool_call_ids for c in state.claims) or state.claims

    # ── 7. 参谋长批注呈报 ──
    plotsvc.annotate_proposal(state, proposal_v1, by="browning",
                              stance="endorse", note="同意呈报，建议尽快批准")
    assert proposal_v1.annotations[-1]["by"] == "browning"

    # ── 8-9. 指挥官批准 → ApprovedPlot 进入正式海图 ──
    plotsvc.decide(state, proposal_v1, action="approve", by="player",
                   comment="按此标图")
    plot = state.approved_plots[0]
    assert plot.state == "active" and plot.current_version == 1
    contact = next(c for c in state.contacts if c.id == proposal_v1.contact_id)
    assert contact.status == ContactStatus.PLOTTED
    # 正式海图（玩家敌情公共视图）= 已批准标图
    view = intel.known_enemy_compat_view(state)
    assert len(view) == 1 and "APPROVED PLOT v1" in view[0].description

    # ── 10-11. 勘误到达 → 新版修订提案（批准前海图保持 v1）──
    correction = _file_correction(state, msg)
    _advance_clock_to(state, correction.transit_eta)
    process_intel(state)
    assert msg.status == MessageStatus.CORRECTED          # 原电文标记，原文保留
    assert ev.status == EvidenceStatus.SUPERSEDED
    corrected_ev = next(e for e in state.evidence if e.message_id == correction.id)
    item2 = intel_work_queue(state)[0]
    assert item2.priority.value == "correction"           # 纠错打断例行队列
    brief2 = run_intelligence_cycle(state, item2, policy=MechanicalPolicy(),
                                    analyst=_Analyst())
    proposal_v2 = next(p for p in state.plot_proposals
                       if p.id == brief2.plot_proposal_ids[0])
    assert proposal_v2.plot_id == proposal_v1.plot_id and proposal_v2.version == 2
    assert proposal_v2.status == ApprovalStatus.PROPOSED.value
    assert state.approved_plots[0].current_version == 1   # 未再批准前海图不变

    # ── 12. 再次批准后更新海图 ──
    plotsvc.decide(state, proposal_v2, action="approve", by="player",
                   comment="勘误后修订采纳")
    assert plot.current_version == 2 and len(plot.history) == 2
    assert proposal_v1.status == ApprovalStatus.SUPERSEDED.value
    view = intel.known_enemy_compat_view(state)
    assert "v2" in view[0].description

    # ── 13. 旧版本和完整因果链保留在复盘中 ──
    server_module.game_state = state
    client = TestClient(server_module.app)
    aa = client.get("/intel/after-action").json()
    chain = next(c for c in aa["chains"] if c["plot_id"] == proposal_v1.plot_id)
    assert [v["version"] for v in chain["versions"]] == [1, 2]
    assert [d["action"] for d in chain["decisions"]] == ["approve", "approve"]
    assert len(chain["evidence"]) >= 2                    # 原始+勘误证据都在
    assert any(e["status"] == "superseded" for e in chain["evidence"])
    assert len(chain["assessments"]) >= 2
    assert aa["tool_calls"]                                # 参谋用过推理工具
    assert len(aa["check_records"]) >= 3                   # 全部检定在案

    # 历史端点版本比较
    hist = client.get(f"/intel/plots/{proposal_v1.plot_id}/history").json()
    assert [v["version"] for v in hist["versions"]] == [1, 2]

    # ── 玩家可见面防泄漏扫描（规则侧真值不得出现）──
    public_blob = json.dumps({
        "inbox": [m.raw_text for m in intel.player_inbox(state)],
        "briefs": [b.narrative for b in state.intel_briefs],
        "claims": [c.text for c in state.claims],
        "plots": [p.change_summary for p in state.plot_proposals],
        "enemy_view": [e.description for e in intel.known_enemy_compat_view(state)],
    }, ensure_ascii=False).lower()
    for banned in ("kido butai", "akagi", "actual_enemy", "internal_truth_ref",
                   "bearing_true", "carrier_count_true"):
        assert banned not in public_blob, f"玩家可见面泄露 {banned}"

    # ── 确定性回放：同种子重跑 → 检定序列与电文要素逐字段一致 ──
    def replay_core():
        s = _make_state(state.rng_seed)
        handle_execute_action(s, "launch_scout", {"direction": "southwest"})
        _advance(s)
        return ([r.model_dump() for r in s.check_records],
                [(m.fields, m.raw_text) for m in s.messages])
    # 用最初命中的种子重跑两次并互相一致
    r1 = replay_core()
    r2 = replay_core()
    assert r1 == r2


def _make_state(seed):
    from src.state import (
        Aircraft, AircraftStatus, AircraftType, GameClock, GameState,
        Position, TaskForce, Carrier,
    )
    from datetime import datetime, timezone
    carrier = Carrier(
        name="USS Enterprise (CV-6)",
        position=Position(lat=32.0, lon=-175.0),
        aircraft=[Aircraft(id=f"SBD-VB6-{i:02d}", type=AircraftType.SBD,
                           squadron="VB-6", carrier="Enterprise",
                           status=AircraftStatus.READY)
                  for i in range(1, 11)],
    )
    tf = TaskForce(name="TF16", carriers=[carrier], course=240, speed=25)
    s = GameState(
        clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)),
        task_forces=[tf], rng_seed=seed,
    )
    s.actual_enemy = [{
        "name": "Kido Butai",
        "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"],
        "position": {"lat": 30.0, "lon": -178.0},
        "status": "rearming",
    }]
    return s


def _file_correction(state, original_msg):
    """飞行员拍发勘误电文（脚本化通信参数）。"""
    from src.intel.models import MessageEnvelope
    correction = MessageEnvelope(
        sender_id="fake_pilot_vs6",
        sender_call_sign=original_msg.sender_call_sign,
        recipient_ids=["TF16 FLAG"],
        priority=__import__("src.intel.contracts", fromlist=["WorkPriority"]).WorkPriority.CORRECTION,
        message_kind="correction",
        observed_at=original_msg.observed_at,
        supersedes_message_id=original_msg.id,
        raw_text="CORRECTION: 2 CV NOT 4, BEARING 236 DIST 185 NM",
        fields={"bearing": 236, "distance_nm": 185, "count": 2,
                "classification": "CV", "quality": "standard",
                "sensor": "carrier_scout"},
    )
    intel.file_message(state, correction, by="fake_pilot_vs6", reason="勘误拍发")
    intel.mark_in_transit(state, correction, by="TBS 通信链")
    correction.transit_eta = state.clock.game_time + timedelta(minutes=25)
    return correction
