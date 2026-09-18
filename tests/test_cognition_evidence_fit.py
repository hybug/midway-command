"""S3.1 候选判断与证据适配测试（红灯先行）。

验收（s3-staff-cognition-system-plan.md Phase S3.1）：
- LLM 无法覆盖 scoring（候选规范化剥除评分字段；fit 只由规则函数计算）
- 模糊证据产生多个合理候选（plausible_set）
- 无证据维度不会给出虚假 fit（缺维不评分，权重重新归一化）
- 候选规范化：id 指派、去重、数量控制、规则侧 aggressiveness/novelty
"""
import pytest

from src.cognition.contracts import FORMULA_VERSION
from src.cognition.evidence_fit import (
    AMBIGUITY_BAND_DEFAULT,
    FIT_WEIGHTS,
    compute_evidence_fit,
    plausible_set,
)
from src.cognition.models import EvidenceFit, Hypothesis
from src.intel.judgment import EvidenceView


# ── 候选生成与规范化 ──

class FakeCandidateGenerator:
    """fake LLM：按人物产 1-3 个结构化候选（测试注入，不触网）。"""

    def __init__(self, raw_candidates):
        self.raw = raw_candidates
        self.calls = 0

    def generate(self, task, context):
        self.calls += 1
        return self.raw


def _mishima_candidates():
    """珊瑚海 5/7 米西马方向三候选（计划 §十）。"""
    return [
        {"text": "发现日军主力航母群，应立即全力攻击。",
         "predicted_class": "CV", "predicted_count_range": (2, 4),
         "predicted_position": (-12.2, 157.8),
         "predicted_course_range": (100, 140), "predicted_speed_range": (16, 22),
         "supporting_evidence_ids": ["EV-000001"], "assumptions": ["识别正确"]},
        {"text": "发现的是莫尔兹比港掩护群，甚至包括轻航母。",
         "predicted_class": "CVL", "predicted_count_range": (2, 3),
         "predicted_position": (-11.5, 156.8),
         "supporting_evidence_ids": ["EV-000001"]},
        {"text": "标图、基准点或通信发生错误，当前报告不可靠。",
         "supporting_evidence_ids": [], "assumptions": ["单机远程识别易错"]},
    ]


def test_normalize_assigns_ids_and_preserves_order():
    from src.cognition.candidates import normalize_candidates
    hs = normalize_candidates(_mishima_candidates())
    assert [h.id for h in hs] == ["H1", "H2", "H3"]
    assert hs[0].predicted_class == "CV"
    assert hs[2].predicted_class is None


def test_normalize_strips_llm_score_fields():
    """LLM 不能自带评分：raw 里塞 fit/score 字段被剥除。"""
    from src.cognition.candidates import normalize_candidates
    raw = _mishima_candidates()[:1] + [
        {"text": "伪装高分候选", "evidence_fit": 0.99, "weighted_fit": 0.99,
         "score": 0.99, "predicted_class": "CV"},
    ]
    h = normalize_candidates(raw)[1]
    dumped = h.model_dump()
    for banned in ("evidence_fit", "weighted_fit", "score"):
        assert banned not in dumped or dumped.get(banned) is None


def test_normalize_dedupes_identical_and_near_duplicates():
    from src.cognition.candidates import normalize_candidates
    raw = [
        {"text": "发现日军主力航母群，应立即全力攻击。",
         "predicted_class": "CV", "predicted_count_range": (2, 4)},
        {"text": "发现日军主力航母群，应立即全力攻击",   # 仅标点差异
         "predicted_class": "CV", "predicted_count_range": (2, 4)},
        {"text": "发现日军主力航母群应当立刻全力攻击！",
         "predicted_class": "CV", "predicted_count_range": (2, 4)},  # 结构同+高文本重合
        {"text": "莫尔兹比港掩护群，含轻航母。",
         "predicted_class": "CVL", "predicted_count_range": (2, 3)},
    ]
    hs = normalize_candidates(raw)
    assert len(hs) == 2
    assert {h.predicted_class for h in hs} == {"CV", "CVL"}


def test_normalize_caps_candidate_count():
    from src.cognition.candidates import normalize_candidates, MAX_CANDIDATES
    raw = [{"text": f"候选 {i}", "predicted_class": c}
           for i, c in enumerate(["CV", "CVL", "CA", "transport", "BB"])]
    hs = normalize_candidates(raw)
    assert len(hs) == MAX_CANDIDATES == 3


def test_rule_decorated_aggressiveness_and_novelty_directions():
    from src.cognition.candidates import normalize_candidates
    hs = normalize_candidates(_mishima_candidates())
    h1, h3 = hs[0], hs[2]
    # 进攻性：明确 CV+位置的主力接触候选 > 无预测的怀疑候选
    assert h1.aggressiveness > h3.aggressiveness
    assert -1.0 <= h1.aggressiveness <= 1.0
    # 新颖度：无预测/无证据支撑的怀疑候选 > 主流证据支撑候选
    assert h3.novelty > h1.novelty
    assert 0.0 <= h3.novelty <= 1.0


def test_candidate_generator_protocol():
    from src.cognition.candidates import CandidateGenerator
    assert isinstance(FakeCandidateGenerator([]), CandidateGenerator)


# ── evidence_fit ──

def _view(evidence_id="EV-000001", *, count=2, lat=-12.2, lon=157.8,
          identity_signal=1.0, reliability=0.7, precision=0.6,
          observed_hours_ago=1.0, now_hours=10.0):
    from datetime import datetime, timedelta, timezone
    base = datetime(1942, 5, 7, 10, 0, tzinfo=timezone.utc)
    return EvidenceView(
        evidence_id=evidence_id,
        source_label="VS-5 侦察机",
        observed_at=base - timedelta(hours=observed_hours_ago),
        received_at=base - timedelta(hours=observed_hours_ago),
        source_reliability=reliability,
        summary="米西马以北报告两艘航母",
        dimensions={
            "identity_signal": identity_signal,
            "position_precision": precision,
            "count_precision": precision,
            "reported_count": float(count),
            "reported_lat": lat,
            "reported_lon": lon,
        },
    )


def test_fit_full_dimensions_hand_computed():
    h = Hypothesis(id="H1", text="主力航母群",
                   predicted_class="CV", predicted_count_range=(2, 4),
                   predicted_position=(-12.2, 157.8),
                   supporting_evidence_ids=["EV-000001"])
    ev = _view()
    fit = compute_evidence_fit(h, [ev], now=ev.received_at)
    assert isinstance(fit, EvidenceFit)
    # 完全一致的位置 → position_fit = 1.0
    assert fit.position_fit == pytest.approx(1.0)
    # 数量中点 3 vs 报告 2 → 1 - 1/3
    assert fit.count_fit == pytest.approx(1 - 1 / 3)
    # 识别信号一致 → identity_fit = 1.0
    assert fit.identity_fit == pytest.approx(1.0)
    assert 0.0 <= fit.weighted_fit <= 1.0


def test_fit_missing_dimension_excluded_and_weights_renormalized():
    """无证据维度不评分：无 predicted_class 的候选不产 identity_fit，权重重新归一化。"""
    h = Hypothesis(id="H3", text="报告不可靠")   # 无任何结构化预测
    ev = _view()
    fit = compute_evidence_fit(h, [ev], now=ev.received_at)
    assert fit.identity_fit is None
    assert fit.position_fit is None
    assert fit.count_fit is None
    # 仍有 source/freshness 维（证据存在即可评）
    assert fit.source_fit is not None
    # weighted_fit 只由可用维度加权（手算对照）
    avail = {"source": fit.source_fit, "freshness": fit.freshness_fit}
    total_w = sum(FIT_WEIGHTS[k] for k in avail)
    expect = sum(FIT_WEIGHTS[k] * v for k, v in avail.items()) / total_w
    assert fit.weighted_fit == pytest.approx(expect)


def test_fit_identity_mismatch_scores_low():
    h = Hypothesis(id="H2", text="掩护群",
                   predicted_class="transport", predicted_count_range=(4, 6),
                   predicted_position=(-11.5, 156.8))
    ev = _view()
    fit = compute_evidence_fit(h, [ev], now=ev.received_at)
    assert fit.identity_fit < 0.5
    assert fit.count_fit < 0.5
    assert fit.position_fit < 0.9


def test_fit_contradiction_penalty_applies():
    from src.intel.models import EvidenceConflict
    h = Hypothesis(id="H1", text="主力航母群",
                   predicted_class="CV", predicted_count_range=(2, 4),
                   supporting_evidence_ids=["EV-000001"])
    ev1 = _view("EV-000001")
    ev2 = _view("EV-000002", count=5, lat=-14.0, lon=159.0)
    conflict = EvidenceConflict(id="CFL-000001", kind="count",
                                evidence_ids=["EV-000001", "EV-000002"],
                                severity=0.5, note="数量冲突")
    fit_clean = compute_evidence_fit(h, [ev1], now=ev1.received_at)
    fit_conflict = compute_evidence_fit(h, [ev1, ev2], now=ev1.received_at,
                                        conflicts=[conflict])
    assert fit_clean.contradiction_penalty == 0.0
    assert fit_conflict.contradiction_penalty > 0.0
    assert fit_conflict.weighted_fit < fit_clean.weighted_fit


def test_plausible_set_boundary_inclusive():
    fits = {
        "H1": EvidenceFit(hypothesis_id="H1", weighted_fit=0.80),
        "H2": EvidenceFit(hypothesis_id="H2", weighted_fit=0.65),   # 差 0.15 ≤ band
        "H3": EvidenceFit(hypothesis_id="H3", weighted_fit=0.60),   # 差 0.20 > band
    }
    ps = plausible_set(fits, ambiguity_band=AMBIGUITY_BAND_DEFAULT)
    assert set(ps) == {"H1", "H2"}


def test_ambiguous_evidence_yields_multiple_plausible_candidates():
    """模糊证据（低精度单一来源）→ 多个合理候选并存。"""
    from src.cognition.candidates import normalize_candidates
    hs = normalize_candidates(_mishima_candidates()[:2])   # H1 主力 / H2 掩护群
    ev = _view(precision=0.25, identity_signal=1.0, reliability=0.5,
               observed_hours_ago=2.0)
    fits = {h.id: compute_evidence_fit(h, [ev], now=ev.received_at) for h in hs}
    ps = plausible_set(fits)
    assert len(ps) >= 2        # 模糊局势允许多个合理候选


def test_formula_version_stamped_on_fit_source():
    """权重常量与公式版本绑定（S3.8 消融调参前不得散落硬编码）。"""
    assert FIT_WEIGHTS["identity"] + FIT_WEIGHTS["position"] \
        + FIT_WEIGHTS["count"] + FIT_WEIGHTS["motion"] \
        + FIT_WEIGHTS["source"] + FIT_WEIGHTS["freshness"] == pytest.approx(1.0)
    assert AMBIGUITY_BAND_DEFAULT == 0.15
