"""S3.4 判断记忆与修订测试（红灯先行）。

验收（s3-staff-cognition-system-plan.md Phase S3.4）：
- NPC 不会忘记或随机漂移（跨任务召回 + 锚定坚持）
- 修订必须引用新证据或反馈（无引用拒绝建版）
- 旧版本完整保留（修订链 supersedes，旧结果/记忆可查）
- 记忆权限：NPC 默认不能读取其他 NPC 的私有判断（D7/D8）
- 指挥官反馈只进记忆，不改写原结果（§8.3/D10）
"""
from datetime import datetime, timedelta, timezone

import pytest

from src.cognition.memory import (
    apply_anchor,
    create_revision_task,
    latest_open_memory,
    record_commander_feedback,
    recall_relevant_memories,
)
from src.cognition.models import ActorProfile, JudgmentContext, JudgmentTask
from src.cognition.rule_engine import RuleJudgmentEngine
from src.intel.judgment import EvidenceView
from src.state import GameState

NOW = datetime(1942, 5, 7, 10, 0, tzinfo=timezone.utc)

_CANDIDATES = [
    {"text": "发现日军主力航母群，应立即全力攻击。",
     "predicted_class": "CV", "predicted_count_range": (2, 3),
     "predicted_position": (-12.2, 157.0),
     "supporting_evidence_ids": ["EV-000001"], "assumptions": ["识别正确"],
     "recommendation": "立即放飞全力攻击群。",
     "change_my_mind": ["陆军飞机证实为掩护群时收拢攻击队"]},
]


class _Gen:
    def generate(self, task, context):
        return _CANDIDATES


def _actor(actor_id="tf17_intel", **over):
    attrs = {"competence": 5, "risk_tolerance": 5, "imagination": 5,
             "initiative": 5, "autonomy": 5}
    attrs.update(over)
    return ActorProfile(actor_id=actor_id, attributes=attrs)


def _task(evidence_ids=None, **kw):
    params = dict(task_type="assess", domain="intelligence",
                  actor_id="tf17_intel",
                  question="这份接触报告是否足以支持立即放飞全力攻击？",
                  evidence_ids=evidence_ids or ["EV-000001"],
                  context_version=1)
    params.update(kw)
    return JudgmentTask(**params)


def _view(evidence_id="EV-000001", count=2.0):
    return EvidenceView(
        evidence_id=evidence_id, source_label="VS-5",
        observed_at=NOW - timedelta(hours=1),
        received_at=NOW - timedelta(hours=1),
        source_reliability=0.8, summary="米西马以北两艘航母",
        dimensions={"identity_signal": 1.0, "identity_precision": 0.8,
                    "position_precision": 0.8, "count_precision": 0.8,
                    "reported_count": count, "reported_lat": -12.2,
                    "reported_lon": 157.0},
    )


def _assess(state, task=None, actor=None, evidence=None):
    engine = RuleJudgmentEngine(state, _Gen())
    return engine.assess(task or _task(), JudgmentContext(
        actor=actor or _actor(), evidence=evidence or [_view()], memories=[]))


# ── 召回与权限 ──

def test_recall_returns_own_memories_only():
    state = GameState(clock={"game_time": NOW})
    _assess(state)
    mine = recall_relevant_memories(state, "tf17_intel",
                                    evidence_ids=["EV-000001"])
    assert len(mine) == 1 and mine[0].actor_id == "tf17_intel"
    # 其他 NPC 默认读不到（D7）：不抛错但永远为空
    assert recall_relevant_memories(state, "fitch",
                                    evidence_ids=["EV-000001"]) == []
    assert recall_relevant_memories(state, "tf17_ops") == []


def test_recall_ranks_by_evidence_overlap_and_recency():
    state = GameState(clock={"game_time": NOW})
    _assess(state, _task(["EV-000001"]))
    _assess(state, _task(["EV-000002"], context_version=1))
    recalled = recall_relevant_memories(state, "tf17_intel",
                                        evidence_ids=["EV-000001"])
    assert recalled[0].evidence_ids == ["EV-000001"]   # 重叠高者优先


def test_memory_not_lost_across_tasks():
    """NPC 不会忘记：新任务（证据小幅变化）仍能召回旧判断。"""
    state = GameState(clock={"game_time": NOW})
    _assess(state, _task(["EV-000001"]))
    _assess(state, _task(["EV-000001", "EV-0009"], context_version=2))
    assert len(state.judgment_memories) == 2
    assert all(m.selected_hypothesis for m in state.judgment_memories)


# ── 锚定与坚持（M3.6.3）──

def test_apply_anchor_boosts_score_only():
    scores = {"H1": 0.60, "H2": 0.62}
    boosted = apply_anchor(scores, "H1", 0.05)
    assert boosted["H1"] == pytest.approx(0.65)
    assert boosted["H2"] == 0.62
    assert apply_anchor(scores, None, 0.05) == scores
    # 选择级：近平局下锚定足以维持原判断（坚持），大幅证据变化仍可翻转
    from src.cognition.formula import select_chosen
    assert select_chosen(apply_anchor({"H1": 0.60, "H2": 0.62}, "H1", 0.05)) == "H1"


def test_anchoring_recorded_in_audit_and_keeps_choice_stable():
    """带旧记忆重判 → 审计记录锚定；小幅新证据下选择不漂移。"""
    state = GameState(clock={"game_time": NOW})
    r1 = _assess(state, _task(["EV-000001"]))
    # 新证据到达（修订任务）：证据略有变化
    task2 = create_revision_task(state, state.judgment_tasks[-1],
                                 new_evidence_ids=["EV-0002"],
                                 reason="第二份接触报告到达")
    r2 = _assess(state, task2, evidence=[_view(), _view("EV-0002", count=3.0)])
    audit2 = state.judgment_audits[-1]
    assert audit2.anchor_memory_id                      # 锚定生效并留痕
    assert r2.chosen_hypothesis_id == r1.chosen_hypothesis_id  # 无原因不漂移
    # 修订链：旧记忆 revised，新记忆 supersedes
    old_mem, new_mem = state.judgment_memories[0], state.judgment_memories[-1]
    assert old_mem.status == "revised"
    assert new_mem.supersedes_id == old_mem.id
    assert new_mem.id != old_mem.id
    assert len(state.judgment_results) == 2             # 旧结果完整保留


def test_revision_task_requires_new_evidence_or_feedback():
    state = GameState(clock={"game_time": NOW})
    old = _task(["EV-000001"])
    state.judgment_tasks.append(old)
    with pytest.raises(ValueError):
        create_revision_task(state, old, new_evidence_ids=[], reason="")
    t = create_revision_task(state, old, new_evidence_ids=["EV-0002"],
                             reason="新报告到达")
    assert t.supersedes_task_id == old.id
    assert t.context_version == old.context_version + 1
    assert t.stable_key != old.stable_key               # 新键 → 允许重判（D9 不被绕过）
    assert set(t.evidence_ids) == {"EV-000001", "EV-0002"}
    t2 = create_revision_task(state, old, new_evidence_ids=[], reason="指挥官要求重新研判")
    assert t2.stable_key != old.stable_key              # 反馈也可触发（上下文版本递增）


# ── 指挥官反馈（§8.3 / D10）──

def test_commander_feedback_updates_memory_not_result():
    state = GameState(clock={"game_time": NOW})
    r1 = _assess(state)
    result_before = r1.model_dump()
    mem = latest_open_memory(state, "tf17_intel")
    record_commander_feedback(state, r1.id, "reject",
                              by="fletcher", note="证据不足，暂不采纳")
    assert mem.commander_decision == "reject"
    assert r1.model_dump() == result_before             # 原结果不被改写
    assert mem.status == "open"                         # 反馈不等于修订
    actions = [a for a in state.intel_audit if a.action == "commander_feedback"]
    assert actions and actions[-1].actor_id == "fletcher"


def test_invalid_commander_decision_rejected():
    state = GameState(clock={"game_time": NOW})
    r1 = _assess(state)
    with pytest.raises(ValueError):
        record_commander_feedback(state, r1.id, "praise", by="fletcher")


def test_no_drift_without_revision_inputs():
    """同一稳定键（同问题+同证据+同上下文）重复请求 → 永远返回同一结果。"""
    state = GameState(clock={"game_time": NOW})
    r1 = _assess(state)
    r2 = _assess(state)
    assert r1.id == r2.id and r2.model_dump() == r1.model_dump()
