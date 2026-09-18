"""v0 判断公式（Phase S3.2，计划 §七 7.1/7.4-7.6）。

五项有效维度（D17）：competence/risk_tolerance/imagination 直接进入公式；
initiative/autonomy 不改变判断选择（只影响主动性与表达，§7.6）。

score(H) = evidence_weight * fit(H) + risk_weight * risk_bias(H)
         + imagination_weight * novelty(H) + deviation_budget * persona_affinity(H)

权重常量集中于此（S3.8 消融校准的唯一出处，不散落业务代码）。
全部确定性：同输入 ⇒ 同输出。
"""
from src.cognition.contracts import FORMULA_VERSION
from src.cognition.models import ActorProfile, EvidenceFit, Hypothesis

# §7.5 JUDGMENT_CHECK 等级 → 初始偏差预算
BASE_DEVIATION_BUDGET: dict[str, float] = {
    "critical_success": 0.00,
    "success": 0.05,
    "partial": 0.15,
    "failure": 0.30,
    "critical_failure": 0.45,
}

# §7.4 v0 初始权重（S3.8 消融校准）
EVIDENCE_WEIGHT_BASE = 0.50
EVIDENCE_WEIGHT_GAIN = 0.50
RISK_WEIGHT_GAIN = 0.20
IMAGINATION_WEIGHT_GAIN = 0.15

# persona_affinity 配比（risk_bias 与 novelty 各占一半；v0 设计值）
AFFINITY_RISK_SHARE = 0.5
AFFINITY_NOVELTY_SHARE = 0.5

SCORE_MIN = -0.2
SCORE_MAX = 2.0


def normalize_attributes(actor: ActorProfile) -> dict[str, float]:
    """§7.1 归一化：属性 /10 → [0,1]。"""
    return {k: v / 10.0 for k, v in actor.attributes.items()
            if k in ("competence", "risk_tolerance", "imagination",
                     "initiative", "autonomy")}


def compute_deviation_budget(dice_level: str, competence_raw: float) -> float:
    """§7.5：budget = base(level) × (1.20 - c)，competence_raw ∈ [0,10] → c = /10。"""
    base = BASE_DEVIATION_BUDGET.get(dice_level, 0.15)
    return round(base * (1.20 - competence_raw / 10.0), 4)


def risk_bias(h: Hypothesis) -> float:
    """§7.6 进攻偏好：aggressiveness ∈ [-1,1] → [0,1]。"""
    return (h.aggressiveness + 1.0) / 2.0


def persona_affinity(h: Hypothesis) -> float:
    """§7.6 人物偏好（规则计算，不采用 LLM 自评分）。"""
    return AFFINITY_RISK_SHARE * risk_bias(h) + AFFINITY_NOVELTY_SHARE * h.novelty


def score_candidates(hypotheses: list[Hypothesis], fits: dict[str, EvidenceFit],
                     actor: ActorProfile, *, deviation_budget: float) -> dict[str, float]:
    """候选评分（§7.4）。返回 {hypothesis_id: score}，钳制到配置边界。"""
    n = normalize_attributes(actor)
    c = n.get("competence", 0.5)
    r = n.get("risk_tolerance", 0.5)
    m = n.get("imagination", 0.5)
    evidence_weight = EVIDENCE_WEIGHT_BASE + EVIDENCE_WEIGHT_GAIN * c
    risk_weight = RISK_WEIGHT_GAIN * (r - 0.5)
    imagination_weight = IMAGINATION_WEIGHT_GAIN * m
    scores: dict[str, float] = {}
    for h in hypotheses:
        fit = fits[h.id].weighted_fit if h.id in fits else 0.0
        value = (evidence_weight * fit
                 + risk_weight * risk_bias(h)
                 + imagination_weight * h.novelty
                 + deviation_budget * persona_affinity(h))
        scores[h.id] = round(max(SCORE_MIN, min(SCORE_MAX, value)), 6)
    return scores


def select_chosen(scores: dict[str, float]) -> str | None:
    """选最佳候选（同分按 id 序稳定打破，保证可回放）。"""
    if not scores:
        return None
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
