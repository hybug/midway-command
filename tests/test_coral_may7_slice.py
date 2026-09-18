"""S3.6 珊瑚海五月七日纵切测试（红灯先行）。

历史链路（s3-staff-cognition-system-plan.md §十/Phase S3.6）：
米西马方向接触报告（contact pad 错误）
  → 情报参谋评估候选与可靠性 / Fitch 给出航空建议 / 作战参谋给出舰队风险
  → 玩家得到三份人物化建议 → contact pad 勘误到达 + 陆军飞机报告米西马航母群
  → 各 NPC 按记忆和新证据坚持或修订 → 指挥官反馈 → 战后复盘区分认知错误与事实结果。

验收：
- 四角色职责边界成立（含职责外拒绝）
- 候选判断、公式选择、报告和记忆全链贯通
- 错误和修订可复现（同种子回放）、可归因（审计+认知/事实分离）
"""
from datetime import timedelta

import pytest

from src.cognition.errors import after_action_error_report
from src.cognition.memory import (
    create_revision_task,
    latest_open_memory,
    record_commander_feedback,
)
from src.cognition.scenarios.coral_may7 import (
    TRUE_COVER_GROUP,
    CoralMay7Generators,
    build_coral_may7_state,
    brief_new_evidence,
    commander_feedback,
    file_army_air_report,
    file_misima_contact,
    file_pad_error_correction,
    reassess,
    staff_judgment_one,
    staff_judgments_misima,
)
from src.intel.flow import process_intel

OFFICERS = ("tf17_intel", "fitch", "tf17_ops")


def _run_until_delivered(seed):
    """通信检定可能丢失电文——按 S2 纵切同款方式选种子。"""
    state = build_coral_may7_state(seed)
    msg = file_misima_contact(state)
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
    pytest.fail("60 个种子内未能送达米西马接触报告")


@pytest.fixture(scope="module")
def delivered():
    seed = _first_delivered_seed()
    state, msg = _run_until_delivered(seed)
    return state, msg, seed


def test_full_slice_three_officers_judge_independently(delivered):
    state, msg, seed = delivered
    outcomes = staff_judgments_misima(state, generators=CoralMay7Generators())
    assert set(outcomes) == set(OFFICERS)
    for actor_id, outcome in outcomes.items():
        result = outcome["result"]
        assert result.actor_id == actor_id
        assert result.chosen_hypothesis_id in {"H1", "H2", "H3"}
        assert result.dice_record_id                          # 恰好一次检定在案
        assert outcome["report"]                              # 人物化报告存在
        memory = latest_open_memory(state, actor_id)
        assert memory and memory.selected_hypothesis == result.chosen_hypothesis_id
    # 三名参谋独立判断（各自任务/结果/记忆）
    assert len(state.judgment_results) == 3
    assert len({r.task_id for r in state.judgment_results}) == 3
    # plausible_set 允许多个合理候选（模糊接触报告）
    intel_result = outcomes["tf17_intel"]["result"]
    assert len(intel_result.plausible_hypothesis_ids) >= 2


def test_duty_boundary_enforced_in_slice(delivered):
    state, msg, seed = delivered
    # 情报参谋被问航空调度（domain=air）→ 拒绝并转交 Fitch
    outcome = staff_judgment_one(state, "tf17_intel", "air",
                                 "CAP 轮换应当如何安排？",
                                 generators=CoralMay7Generators())
    result = outcome["result"]
    assert result.refusal_reason == "out_of_duty"
    assert "fitch" in (result.recommendation or "")


def test_pad_error_correction_triggers_revision(delivered):
    state, msg, seed = delivered
    first = staff_judgments_misima(state, generators=CoralMay7Generators())
    chosen_before = {aid: first[aid]["result"].chosen_hypothesis_id
                     for aid in OFFICERS}
    results_before = len(state.judgment_results)

    # 勘误（contact pad 错误）+ 陆军飞机报告（同一 S2 电文协议到达）
    corr = file_pad_error_correction(state, msg)
    state.clock.game_time = corr.transit_eta + timedelta(minutes=1)
    process_intel(state)
    army = file_army_air_report(state)
    state.clock.game_time = army.transit_eta + timedelta(minutes=1)
    process_intel(state)
    brief_new_evidence(state)                    # 情报参谋研判新证据并呈报（S2 链）
    assert len(state.evidence) >= 3              # 原始+勘误+陆军
    assert any(b.status == "proposed" for b in state.intel_briefs)

    revised = {}
    for actor_id in OFFICERS:
        old_mem = next(m for m in state.judgment_memories
                       if m.actor_id == actor_id)
        old_result = next(r for r in state.judgment_results
                          if r.id == old_mem.result_id)
        old_task = next(t for t in state.judgment_tasks if t.id == old_result.task_id)
        rev_task = create_revision_task(
            state, old_task,
            new_evidence_ids=[e.id for e in state.evidence[1:]],
            reason="勘误与陆军报告到达，重新研判")
        outcome = reassess(state, actor_id, rev_task,
                           generators=CoralMay7Generators())
        if outcome["result"].chosen_hypothesis_id != chosen_before[actor_id]:
            revised[actor_id] = outcome
    # 至少一名参谋修订；旧版本完整保留；修订链引用新证据
    assert revised, "新证据到达后必须至少一名参谋修订判断"
    assert len(state.judgment_results) > results_before
    for actor_id, outcome in revised.items():
        new_mem = next(m for m in state.judgment_memories
                       if m.result_id == outcome["result"].id)
        assert new_mem.revision_reason
        old = next(m for m in state.judgment_memories
                   if m.result_id == first[actor_id]["result"].id)
        assert old.status == "revised"           # 旧记忆翻状态不删除
    # 修订可归因：新记忆引用修订理由（新证据在案）
    assert any("勘误" in (m.revision_reason or "") or "陆军" in (m.revision_reason or "")
               for m in state.judgment_memories)


def test_commander_feedback_and_cognition_fact_separation(delivered):
    state, msg, seed = delivered
    outcomes = staff_judgments_misima(state, generators=CoralMay7Generators())
    intel_result = outcomes["tf17_intel"]["result"]
    # 玩家比较三份建议后给出反馈（不改写原结果）
    before = intel_result.model_dump()
    commander_feedback(state, "tf17_intel", intel_result.id, "reject",
                       note="单份报告不足以支持全力攻击，等待印证")
    assert intel_result.model_dump() == before
    mem = latest_open_memory(state, "tf17_intel")
    assert mem.commander_decision == "reject"
    # 战后复盘：认知错误 vs 事实误差 分离（actual 只在此处进入，D11）
    report = after_action_error_report(state, TRUE_COVER_GROUP)
    by_actor = {r.actor_id: r for r in report}
    assert "tf17_intel" in by_actor
    cog = by_actor["tf17_intel"].cognitive_error_type
    fact = by_actor["tf17_intel"].factual_error_type
    # 认知错误相对证据兼容集判定；事实误差相对真实结果——两者独立呈现（D12）
    assert fact in {"identity", "count", "position", "course", "speed", "none"}
    if intel_result.chosen_hypothesis_id in intel_result.plausible_hypothesis_ids:
        assert cog == "none"


def test_same_seed_replay_full_slice():
    """同种子全链回放：结果、报告、检定序列逐字段一致。"""
    seed = _first_delivered_seed()

    def run():
        state, msg = _run_until_delivered(seed)
        assert state is not None
        outcomes = staff_judgments_misima(state, generators=CoralMay7Generators())
        return (
            {k: v["result"].model_dump(mode="json") for k, v in outcomes.items()},
            {k: v["report"] for k, v in outcomes.items()},
            [r.model_dump(mode="json") for r in state.check_records],
        )

    assert run() == run()


def test_slice_never_leaks_actual_enemy(delivered):
    state, msg, seed = delivered
    staff_judgments_misima(state, generators=CoralMay7Generators())
    import json
    blob = json.dumps({
        "tasks": [t.model_dump(mode="json") for t in state.judgment_tasks],
        "results": [r.model_dump(mode="json") for r in state.judgment_results],
        "memories": [m.model_dump(mode="json") for m in state.judgment_memories],
        "audits": [a.model_dump(mode="json") for a in state.judgment_audits],
        "reports": dict(state.judgment_reports),
        "evidence": [e.summary for e in state.evidence],
        "messages": [m.raw_text for m in state.messages
                     if m.status.value not in ("in_transit", "lost", "draft", "filed")],
    }, ensure_ascii=False).lower()
    for banned in ("shokaku", "zuikaku", "actual_enemy", "internal_truth_ref",
                   "kido butai"):
        assert banned not in blob, f"纵切可见面泄露 {banned}"
