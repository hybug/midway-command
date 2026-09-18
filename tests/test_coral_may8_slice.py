"""S3.7 珊瑚海五月八日扩展测试（红灯先行）。

历史链路（计划 §十 5/8 扩展）：
黎明 360° 搜索后列克星敦侦察机报告「两艘航母四艘重巡多驱逐」
  （航向 006°、120 海里、15 节）
  → 报告修正为「真方位 028°、175 海里」（基准点变化）
  → 各参谋按多版本证据坚持或修订（玩家可比较改变是否因证据合理）
  → 09:08 Fitch 被指定为战术指挥官（OTC）。

验收：
- 同一 NPC 能处理多版本证据（修订链完整、旧版本保留）
- 新旧判断链完整（supersedes 链 + 修订理由）
- 玩家可以比较参谋是否因证据合理改变（revision_comparison）
- Fitch 指挥权变化入档（审计 + 名册档案可见）
"""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import server as server_module
from src.cognition.evidence_fit import compute_evidence_fit
from src.cognition.scenarios.coral_may7 import (
    CoralMay7Generators,
    build_coral_may7_state,
    brief_new_evidence,
)
from src.cognition.scenarios.coral_may8 import (
    CoralMay8Generators,
    file_dawn_search_report,
    file_true_bearing_correction,
    promote_fitch_otc,
    reassess_all,
    revision_comparison,
    staff_judgments_contact,
)
from src.intel.flow import process_intel


def _run_until_delivered(seed):
    state = build_coral_may7_state(seed)
    state.clock.game_time = state.clock.game_time.replace(
        day=8, hour=5, minute=30)
    msg = file_dawn_search_report(state)
    if msg.status.value == "lost":
        return None, None
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    if not state.evidence:
        return None, None
    return state, msg


def _first_delivered_seed():
    for seed in range(60):
        state, msg = _run_until_delivered(seed)
        if state is not None:
            return seed
    pytest.fail("60 个种子内未能送达黎明搜索报告")


@pytest.fixture(scope="module")
def delivered():
    seed = _first_delivered_seed()
    state, msg = _run_until_delivered(seed)
    return state, msg, seed


def test_motion_fit_uses_reported_course_speed(delivered):
    """5/8 报告含航向航速 → motion 维度真实参与评分（不再是空维）。"""
    state, msg, seed = delivered
    from src.cognition.models import Hypothesis
    from src.intel.judgment import EvidenceView
    # 装配视图直接从 state 证据取（权限内）
    from src.cognition import context as cognition
    from src.cognition.roster import get_actor
    views = cognition.actor_evidence_views(state, get_actor("tf17_intel"))
    assert views and views[0].dimensions.get("reported_course") == 6.0
    assert views[0].dimensions.get("reported_speed") == 15.0
    h = Hypothesis(id="H1", text="x", predicted_course_range=(0, 20),
                   predicted_speed_range=(12, 18))
    fit = compute_evidence_fit(h, views, now=state.clock.game_time)
    assert fit.motion_fit is not None and fit.motion_fit > 0.5


def test_multistage_report_and_officer_revision_comparison(delivered):
    state, msg, seed = delivered
    first = staff_judgments_contact(state, generators=CoralMay8Generators(),
                                    phase="pre")
    chosen_before = {aid: first[aid]["result"] for aid in first}
    # 基准点变化：真方位修正（勘误协议）
    correction = file_true_bearing_correction(state, msg)
    state.clock.game_time = correction.transit_eta + timedelta(minutes=1)
    process_intel(state)
    brief_new_evidence(state)
    assert len(state.evidence) >= 2                 # 原始+修正
    assert any(e.supersedes_evidence_id for e in state.evidence)  # 勘误替代链

    revised = reassess_all(state, first, generators=CoralMay8Generators())
    # 同一 NPC 处理多版本证据：修订链完整
    for aid, outcome in revised.items():
        result = outcome["result"]
        old_mem = next(m for m in state.judgment_memories
                       if m.result_id == chosen_before[aid].id)
        assert old_mem.status == "revised"          # 旧记忆翻状态
        assert result.created_at > chosen_before[aid].created_at
    # 至少一名参谋修订，且修订理由引用新证据
    assert revised
    assert any(m.revision_reason for m in state.judgment_memories)
    # 旧结果完整保留（追加制）
    assert chosen_before["tf17_intel"].id in {r.id for r in state.judgment_results}

    # 玩家比较视图：谁改了、谁坚持、为什么
    comparison = revision_comparison(state)
    by_actor = {c["actor_id"]: c for c in comparison}
    assert {"tf17_intel", "fitch", "tf17_ops"} <= set(by_actor)
    for aid, c in by_actor.items():
        assert set(c) >= {"before_result_id", "after_result_id", "changed",
                          "revision_reason"}
        assert c["before_result_id"] != c["after_result_id"]
    assert any(c["changed"] for c in by_actor.values())   # 有人修订
    # 坚持或修订都必须可归因（理由在案）
    assert all(c["revision_reason"] for c in by_actor.values())


def test_fitch_otc_change_recorded_and_visible(delivered):
    state, msg, seed = delivered
    entry = promote_fitch_otc(state)
    assert entry.action == "otc_change"
    assert entry.target_id == "fitch"
    # 名册档案可见（自然语言状态，非数值）
    server_module.game_state = state
    client = TestClient(server_module.app)
    roster = client.get("/staff/roster").json()
    fitch = next(a for a in roster["staff"] if a["actor_id"] == "fitch")
    assert any("战术指挥" in r["note"] for r in fitch["dossier"]["recent"])


def test_same_seed_replay_may8():
    seed = _first_delivered_seed()

    def run():
        state, msg = _run_until_delivered(seed)
        first = staff_judgments_contact(state, generators=CoralMay8Generators(),
                                        phase="pre")
        correction = file_true_bearing_correction(state, msg)
        state.clock.game_time = correction.transit_eta + timedelta(minutes=1)
        process_intel(state)
        brief_new_evidence(state)
        revised = reassess_all(state, first, generators=CoralMay8Generators())
        return (
            {k: v["result"].model_dump(mode="json") for k, v in first.items()},
            {k: v["result"].model_dump(mode="json") for k, v in revised.items()},
            [r.model_dump(mode="json") for r in state.check_records],
        )

    assert run() == run()
