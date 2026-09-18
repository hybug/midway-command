"""S3.3 错误语义、置信度与建议测试（红灯先行）。

验收（s3-staff-cognition-system-plan.md Phase S3.3）：
- 合理候选不会被判错（兼容集内 error=none）
- 认知错误不依赖 actual_enemy（距离=候选×兼容集参照）
- 置信度和建议可解释（recommendation/change_my_mind 随 chosen 转移到结果）
- 认知错误与事后事实误差分离（factual_error 只在复盘层、由调用方传入真值）
"""
from datetime import datetime, timedelta, timezone

import pytest

from src.cognition.candidates import normalize_candidates
from src.cognition.errors import (
    evaluate_error,
    evaluate_factual_error,
    hypothesis_distances,
)
from src.cognition.models import ActorProfile, Hypothesis, JudgmentContext
from src.cognition.rule_engine import RuleJudgmentEngine
from src.intel.judgment import EvidenceView
from src.state import GameState

NOW = datetime(1942, 5, 7, 10, 0, tzinfo=timezone.utc)


# ── 结构化错误距离（§7.8）──

def test_identical_predictions_no_error():
    h = Hypothesis(id="H1", text="x", predicted_class="CV",
                   predicted_count_range=(2, 4), predicted_position=(-12.2, 157.8))
    assert evaluate_error(h, h.model_copy()) == ("none", 0.0)


def test_identity_error_is_max_dimension():
    chosen = Hypothesis(id="H1", text="x", predicted_class="transport",
                        predicted_count_range=(2, 4), predicted_position=(-12.2, 157.8))
    ref = Hypothesis(id="H2", text="y", predicted_class="CV",
                     predicted_count_range=(2, 4), predicted_position=(-12.2, 157.8))
    d = hypothesis_distances(chosen, ref)
    assert d["identity"] == pytest.approx(0.8)     # |0.2 - 1.0|
    error_type, severity = evaluate_error(chosen, ref)
    assert error_type == "identity"
    assert 0.0 < severity <= 1.0


def test_position_distance_hand_computed():
    chosen = Hypothesis(id="H1", text="x", predicted_position=(-12.2, 157.8))
    ref = Hypothesis(id="H2", text="y", predicted_position=(-12.2, 156.8))
    # 1° lon ≈ 58.7nm（局部平面）→ d = 58.7/200
    d = hypothesis_distances(chosen, ref)
    assert d["position"] == pytest.approx(58.7 / 200.0, abs=1e-3)


def test_missing_prediction_counts_neutral_not_zero():
    """单侧缺预测：距离记中性 0.5（不因沉默白拿满分）。"""
    chosen = Hypothesis(id="H1", text="x")            # 无预测
    ref = Hypothesis(id="H2", text="y", predicted_class="CV",
                     predicted_count_range=(2, 4), predicted_position=(0.0, 0.0))
    d = hypothesis_distances(chosen, ref)
    assert d["identity"] == 0.5
    assert d["count"] == 0.5
    assert d["position"] == 0.5
    assert d["course"] == 0.0 and d["speed"] == 0.0   # 双侧沉默 = 0


def test_engine_error_none_when_chosen_in_compatible_set():
    state = GameState(clock={"game_time": NOW})
    state.rng_seed = 5
    engine = RuleJudgmentEngine(state, _Gen([_CANDIDATES[0]]))
    r = engine.assess(_task(), JudgmentContext(
        actor=_actor(), evidence=[_view()], memories=[]))
    assert r.chosen_hypothesis_id in r.plausible_hypothesis_ids
    assert r.error_type == "none" and r.error_severity == 0.0


def test_engine_error_marked_when_persona_overrides_fit():
    """骰子+人物偏好把 chosen 推出兼容集 ⇒ 认知错误即时标记（非事后）。"""
    state = GameState(clock={"game_time": NOW})
    state.rng_seed = 5
    weak = {
        "text": "敌军已被此前空袭重创，残部正在撤退。",
        "predicted_class": "transport", "predicted_count_range": (1, 1),
        "predicted_position": (-14.8, 160.0),       # 远离报告位置 → 低 fit
        "supporting_evidence_ids": ["EV-000001"],
    }
    engine = RuleJudgmentEngine(state, _Gen([_CANDIDATES[0], weak]))
    ctx = JudgmentContext(actor=_actor(risk_tolerance=9), evidence=[_view()],
                          memories=[], scenario={"ambiguity_band": 0.01})
    r = engine.assess(_task(), ctx)
    if r.chosen_hypothesis_id not in r.plausible_hypothesis_ids:
        assert r.error_type != "none" and r.error_severity > 0.0
        assert r.confidence_band == "low"
    else:   # 该种子下骰子未放大偏差——兼容集内必须仍是无错
        assert r.error_type == "none"


# ── 建议域（M3.8.1/3.8.5）──

def test_recommendation_and_change_my_mind_transfer_from_chosen():
    cand = dict(_CANDIDATES[0])
    cand["recommendation"] = "立即放飞全力攻击群，先发制人。"
    cand["change_my_mind"] = ["陆军飞机证实为掩护群时收拢攻击队"]
    state = GameState(clock={"game_time": NOW})
    state.rng_seed = 5
    engine = RuleJudgmentEngine(state, _Gen([cand]))
    r = engine.assess(_task(), JudgmentContext(
        actor=_actor(), evidence=[_view()], memories=[]))
    assert r.recommendation == "立即放飞全力攻击群，先发制人。"
    assert r.change_my_mind == ["陆军飞机证实为掩护群时收拢攻击队"]
    assert r.assumptions == ["识别正确"]
    memory = state.judgment_memories[-1]
    assert memory.change_my_mind == r.change_my_mind


# ── 认知错误 vs 事后事实误差（M3.5.8 / D11 / D12）──

def test_factual_error_computed_only_against_provided_truth():
    chosen = Hypothesis(id="H1", text="两艘航母", predicted_class="CV",
                        predicted_count_range=(2, 3),
                        predicted_position=(-12.2, 157.0))
    actual = {"classification": "CV", "count": 1,
              "position": (-12.0, 157.2), "course": 120, "speed": 20}
    record = evaluate_factual_error(chosen, actual, result_id="JR-000001",
                                    actor_id="tf17_intel")
    assert record.factual_error_type == "count"    # 实际 1 艘 vs 预测 2.5
    assert record.factual_error_severity > 0.0
    assert record.cognitive_error_type == "unset"  # 由结果回填，本函数不碰


def test_after_action_report_separates_cognition_and_fact():
    state = GameState(clock={"game_time": NOW})
    state.rng_seed = 5
    cand = dict(_CANDIDATES[0])
    engine = RuleJudgmentEngine(state, _Gen([cand]))
    r = engine.assess(_task(), JudgmentContext(
        actor=_actor(), evidence=[_view()], memories=[]))
    actual = {"classification": "CVL", "count": 1,
              "position": (-11.5, 156.8)}
    from src.cognition.errors import after_action_error_report
    report = after_action_error_report(state, actual)
    assert len(report) == 1
    rec = report[0]
    assert rec.result_id == r.id
    assert rec.cognitive_error_type == r.error_type        # 判断当时的认知错误
    assert rec.factual_error_type in {"identity", "count", "position",
                                      "course", "speed", "none"}
    # 候选快照随审计落档（复盘可重建判断内容）
    audit = state.judgment_audits[-1]
    assert any(h["id"] == r.chosen_hypothesis_id for h in audit.hypotheses)


def test_actual_truth_never_enters_judgment_state():
    """D11：actual 数据只在复盘函数入参——判断/记忆/审计四容器无真值。"""
    state = GameState(clock={"game_time": NOW})
    state.rng_seed = 5
    engine = RuleJudgmentEngine(state, _Gen([_CANDIDATES[0]]))
    engine.assess(_task(), JudgmentContext(
        actor=_actor(), evidence=[_view()], memories=[]))
    import json
    blob = json.dumps({
        "tasks": [t.model_dump(mode="json") for t in state.judgment_tasks],
        "results": [r.model_dump(mode="json") for r in state.judgment_results],
        "memories": [m.model_dump(mode="json") for m in state.judgment_memories],
        "audits": [a.model_dump(mode="json") for a in state.judgment_audits],
    }, ensure_ascii=False).lower()
    for banned in ("actual_enemy", "shokaku", "zuikaku", "kido butai"):
        assert banned not in blob


# ── fixtures ──

_CANDIDATES = [
    {"text": "发现日军主力航母群，应立即全力攻击。",
     "predicted_class": "CV", "predicted_count_range": (2, 3),
     "predicted_position": (-12.2, 157.0),
     "supporting_evidence_ids": ["EV-000001"], "assumptions": ["识别正确"]},
]


class _Gen:
    def __init__(self, raw):
        self.raw = raw

    def generate(self, task, context):
        return self.raw


def _actor(**over):
    attrs = {"competence": 5, "risk_tolerance": 5, "imagination": 5,
             "initiative": 5, "autonomy": 5}
    attrs.update(over)
    return ActorProfile(actor_id="tf17_intel", attributes=attrs)


def _task():
    from src.cognition.models import JudgmentTask
    return JudgmentTask(task_type="assess", domain="intelligence",
                        actor_id="tf17_intel", question="报告是否支持立即攻击？",
                        evidence_ids=["EV-000001"], context_version=1)


def _view(*, precision=0.8):
    return EvidenceView(
        evidence_id="EV-000001", source_label="VS-5",
        observed_at=NOW - timedelta(hours=1),
        received_at=NOW - timedelta(hours=1),
        source_reliability=0.8, summary="米西马以北两艘航母",
        dimensions={"identity_signal": 1.0, "identity_precision": precision,
                    "position_precision": precision, "count_precision": precision,
                    "reported_count": 2.0, "reported_lat": -12.2,
                    "reported_lon": 157.0},
    )
