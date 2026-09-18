"""S3.2 判断公式与骰子测试（红灯先行）。

验收（s3-staff-cognition-system-plan.md Phase S3.2）：
- 同输入返回同结果（稳定键缓存 + 同种子回放）
- 统计测试验证人物参数方向（competence/risk/imagination ↑，initiative/autonomy 不影响选择）
- 骰子记录完整且可回放（每次判断恰好一次 JUDGMENT_CHECK）
"""
from datetime import datetime, timedelta, timezone

import pytest

from src.cognition.candidates import normalize_candidates
from src.cognition.contracts import FORMULA_VERSION
from src.cognition.evidence_fit import compute_evidence_fit
from src.cognition.formula import (
    BASE_DEVIATION_BUDGET,
    compute_deviation_budget,
    score_candidates,
)
from src.cognition.models import ActorProfile, JudgmentTask
from src.cognition.rule_engine import RuleJudgmentEngine, find_cached_result
from src.intel.contracts import CheckType
from src.intel.judgment import EvidenceView
from src.intel.models import EvidenceConflict
from src.state import GameState

NOW = datetime(1942, 5, 7, 10, 0, tzinfo=timezone.utc)


# ── 固定场景：米西马三候选 ──

def _view(*, reliability=0.55, precision=0.8, hours_ago=1.0,
          evidence_id="EV-000001"):
    return EvidenceView(
        evidence_id=evidence_id,
        source_label="VS-5 侦察机",
        observed_at=NOW - timedelta(hours=hours_ago),
        received_at=NOW - timedelta(hours=hours_ago),
        source_reliability=reliability,
        summary="米西马以北报告两艘航母",
        dimensions={
            "identity_signal": 1.0,
            "identity_precision": precision,
            "position_precision": precision,
            "count_precision": precision,
            "reported_count": 2.0,
            "reported_lat": -12.2,
            "reported_lon": 157.8,
        },
    )


def _raw_candidates():
    return [
        {"text": "发现日军主力航母群，应立即全力攻击。",
         "predicted_class": "CV", "predicted_count_range": (2, 3),
         "predicted_position": (-12.2, 156.8),   # 偏东约 59nm
         "supporting_evidence_ids": ["EV-000001"]},
        {"text": "敌兵力薄弱，可放心推进。",
         "predicted_class": "CV", "predicted_count_range": (1, 2),
         "predicted_position": (-12.2, 156.6),   # 偏东约 70nm
         "supporting_evidence_ids": ["EV-000001"]},
        {"text": "标图或基准点可能出错，当前报告不可靠。"},
    ]


def _actor(**attr_overrides):
    attrs = {"competence": 5, "risk_tolerance": 5, "imagination": 5,
             "initiative": 5, "autonomy": 5}
    attrs.update(attr_overrides)
    return ActorProfile(actor_id="tf17_intel", role="情报参谋",
                        domain="intelligence", attributes=attrs)


def _task(seed_i=0):
    return JudgmentTask(
        id=f"JT-T{seed_i}", task_type="assess", domain="intelligence",
        actor_id="tf17_intel",
        question="这份米西马方向接触报告是否足以支持立即放飞全力攻击？",
        evidence_ids=["EV-000001"], context_version=1,
    )


class _FixedGenerator:
    def __init__(self, raw=None):
        self.raw = raw or _raw_candidates()

    def generate(self, task, context):
        return self.raw


def _fits():
    hs = normalize_candidates(_raw_candidates())
    return {h.id: compute_evidence_fit(h, [_view()], now=NOW) for h in hs}


# ── 偏差预算 ──

def test_deviation_budget_base_mapping():
    assert BASE_DEVIATION_BUDGET == {
        "critical_success": 0.00, "success": 0.05, "partial": 0.15,
        "failure": 0.30, "critical_failure": 0.45,
    }


def test_deviation_budget_scales_with_competence_and_bounded():
    assert compute_deviation_budget("partial", 5) == pytest.approx(0.15 * 0.7)
    # competence 越高预算越小；边界受控
    assert compute_deviation_budget("critical_failure", 9) \
        < compute_deviation_budget("critical_failure", 3)
    assert compute_deviation_budget("critical_failure", 0) == pytest.approx(0.45 * 1.2)
    assert compute_deviation_budget("critical_success", 0) == 0.0


# ── 评分公式 ──

def test_score_formula_hand_computed_single_candidate():
    hs = normalize_candidates([_raw_candidates()[0]])
    fits = {h.id: compute_evidence_fit(h, [_view()], now=NOW) for h in hs}
    scores = score_candidates(hs, fits, _actor(competence=6), deviation_budget=0.05)
    c = 0.6
    ev_w = 0.50 + 0.50 * c
    risk_w = 0.20 * (0.5 - 0.5)
    imag_w = 0.15 * 0.5
    h = hs[0]
    risk_bias = (h.aggressiveness + 1) / 2
    affinity = 0.5 * risk_bias + 0.5 * h.novelty
    expect = ev_w * fits[h.id].weighted_fit + risk_w * risk_bias \
        + imag_w * h.novelty + 0.05 * affinity
    assert scores[h.id] == pytest.approx(expect, abs=1e-6)


def test_scores_within_configured_bounds():
    hs = normalize_candidates(_raw_candidates())
    fits = _fits()
    scores = score_candidates(hs, fits, _actor(), deviation_budget=0.45)
    for v in scores.values():
        assert -0.2 <= v <= 2.0


# ── 统计方向测试（真实引擎 + 固定种子列，确定性）──

def _trial_picks(attr_overrides, trials=60):
    """固定种子逐个跑真实引擎（每种子独立 GameState），返回 chosen 序列。"""
    picks = []
    for seed in range(trials):
        state = _make_state(seed)
        engine = RuleJudgmentEngine(state, _FixedGenerator())
        from src.cognition.models import JudgmentContext
        ctx = JudgmentContext(actor=_actor(**attr_overrides),
                              evidence=[_view()], memories=[])
        picks.append(engine.assess(_task(), ctx).chosen_hypothesis_id)
    return picks


def test_higher_competence_selects_best_fit_candidate_more():
    fits = _fits()
    best = max(fits, key=lambda k: fits[k].weighted_fit)
    rate_hi = _trial_picks({"competence": 8}).count(best) / 60
    rate_lo = _trial_picks({"competence": 2}).count(best) / 60
    assert rate_hi > rate_lo + 0.3


def test_higher_risk_tolerance_yields_stable_aggressive_bias():
    """高 risk_tolerance ⇒ 被选候选的进攻性均值稳定上移（乐观/进攻偏差）。"""
    hs = normalize_candidates(_raw_candidates())
    agg = {h.id: h.aggressiveness for h in hs}
    from statistics import mean
    mean_hi = mean(agg[p] for p in _trial_picks({"risk_tolerance": 9}))
    mean_lo = mean(agg[p] for p in _trial_picks({"risk_tolerance": 1}))
    assert mean_hi > mean_lo + 0.3


def test_higher_imagination_yields_more_novel_choices():
    """高 imagination ⇒ 被选候选的新颖度均值上移（更多新假设/未知补全）。"""
    hs = normalize_candidates(_raw_candidates())
    nov = {h.id: h.novelty for h in hs}
    from statistics import mean
    mean_hi = mean(nov[p] for p in _trial_picks({"imagination": 9}))
    mean_lo = mean(nov[p] for p in _trial_picks({"imagination": 1}))
    assert mean_hi > mean_lo + 0.3


def test_initiative_and_autonomy_do_not_change_selection():
    """initiative/autonomy 不改变相同任务的判断选择（只影响表达与主动性）。"""
    picks_a = _trial_picks({"initiative": 9, "autonomy": 9}, trials=40)
    picks_b = _trial_picks({"initiative": 1, "autonomy": 1}, trials=40)
    assert picks_a == picks_b


# ── 引擎：骰子、缓存、审计 ──

def _make_state(seed=7):
    s = GameState(clock={"game_time": NOW})
    s.rng_seed = seed
    return s


def _run_assess(state, actor=None):
    engine = RuleJudgmentEngine(state, _FixedGenerator())
    from src.cognition.models import JudgmentContext
    ctx = JudgmentContext(actor=actor or _actor(), evidence=[_view()], memories=[])
    return engine.assess(_task(), ctx)


def test_engine_single_judgment_check_per_assess():
    state = _make_state()
    result = _run_assess(state)
    jc = [r for r in state.check_records
          if r.check_type == CheckType.JUDGMENT_CHECK.value]
    assert len(jc) == 1
    assert result.dice_record_id == jc[0].check_id
    assert result.chosen_hypothesis_id in {"H1", "H2", "H3"}
    assert result.formula_version == FORMULA_VERSION


def test_same_stable_key_returns_cached_result_without_reroll():
    state = _make_state()
    r1 = _run_assess(state)
    n_records = len(state.check_records)
    r2 = _run_assess(state)
    assert r2.id == r1.id and r2.chosen_hypothesis_id == r1.chosen_hypothesis_id
    assert len(state.check_records) == n_records        # 禁止重骰（D9）
    assert find_cached_result(state, _task().stable_key) is not None


def test_new_evidence_set_creates_new_result_version():
    state = _make_state()
    engine = RuleJudgmentEngine(state, _FixedGenerator())
    from src.cognition.models import JudgmentContext
    r1 = engine.assess(_task(), JudgmentContext(
        actor=_actor(), evidence=[_view()], memories=[]))
    task2 = JudgmentTask(
        task_type="assess", domain="intelligence", actor_id="tf17_intel",
        question="这份米西马方向接触报告是否足以支持立即放飞全力攻击？",
        evidence_ids=["EV-000001", "EV-000002"], context_version=1,
    )
    r2 = engine.assess(task2, JudgmentContext(
        actor=_actor(), evidence=[_view(), _view(evidence_id="EV-000002")],
        memories=[]))
    assert r2.task_id != r1.task_id                 # 证据集变化 → 新任务新结果
    assert len(state.judgment_results) == 2


def test_audit_record_completeness():
    state = _make_state()
    _run_assess(state)
    audit = state.judgment_audits[-1]
    assert audit.formula_version == FORMULA_VERSION
    assert set(audit.attribute_snapshot) >= {
        "competence", "risk_tolerance", "imagination", "initiative", "autonomy"}
    assert len(audit.candidate_scores) == 3
    assert audit.plausible_set
    assert audit.dice_record_id
    assert audit.random_seed
    assert audit.memory_ids                            # 记忆已落档
    assert state.judgment_memories[-1].actor_id == "tf17_intel"


def test_same_seed_replay_identical_result_and_records():
    def run(seed):
        s = _make_state(seed)
        r = _run_assess(s)
        return r.model_dump(mode="json"), [r.model_dump() for r in s.check_records]
    result_a, records_a = run(11)
    result_b, records_b = run(11)
    assert result_a == result_b                     # 结果逐字段一致
    assert records_a == records_b                   # 检定记录序列逐字段一致
    # 记录序列也逐字段一致
    s_a, s_b = _make_state(11), _make_state(11)
    _run_assess(s_a)
    _run_assess(s_b)
    assert [r.model_dump() for r in s_a.check_records] \
        == [r.model_dump() for r in s_b.check_records]


def test_conflict_and_staleness_lower_confidence():
    from src.cognition.models import JudgmentContext
    state = _make_state()
    engine = RuleJudgmentEngine(state, _FixedGenerator())
    conflict = EvidenceConflict(id="CFL-1", kind="count",
                                evidence_ids=["EV-000001"], severity=0.6)
    ctx = JudgmentContext(actor=_actor(), evidence=[_view()], memories=[],
                          conflicts=[conflict])
    result = engine.assess(_task(), ctx)
    assert result.confidence_band == "low"


def test_confidence_bands_three_tiers():
    from src.cognition.models import JudgmentContext
    # high：强证据 + 高 fit + 清晰边际（单候选）
    state = _make_state(3)
    engine = RuleJudgmentEngine(state, _FixedGenerator([_raw_candidates()[0]]))
    strong_view = _view(reliability=0.9, precision=0.9)
    ctx = JudgmentContext(actor=_actor(), evidence=[strong_view], memories=[])
    r_hi = engine.assess(_task(), ctx)
    assert r_hi.confidence_band == "high"
    assert r_hi.error_type == "none" and r_hi.error_severity == 0.0

    # medium：候选落在兼容集内但 fit < 0.75
    state2 = _make_state(3)
    engine2 = RuleJudgmentEngine(state2, _FixedGenerator([{
        "text": "接触在远处，方向存疑。",
        "predicted_class": "CV", "predicted_count_range": (2, 3),
        "predicted_position": (-14.5, 155.5),      # 偏北约 190nm → position_fit≈0 → fit<0.75
        "supporting_evidence_ids": ["EV-000001"]}]))
    ctx2 = JudgmentContext(actor=_actor(), evidence=[_view(reliability=0.9, precision=0.9)],
                           memories=[])
    r_md = engine2.assess(_task(), ctx2)
    assert r_md.confidence_band == "medium"

    # low：证据弱
    state3 = _make_state(3)
    engine3 = RuleJudgmentEngine(state3, _FixedGenerator([_raw_candidates()[0]]))
    ctx3 = JudgmentContext(actor=_actor(),
                           evidence=[_view(reliability=0.2, precision=0.2)],
                           memories=[])
    r_lo = engine3.assess(_task(), ctx3)
    assert r_lo.confidence_band == "low"
