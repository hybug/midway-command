"""证据适配评分（Phase S3.1，计划 §M3.3 / §七 7.2-7.3）。

规则引擎独占评分（D2/M3.3 验收）：fit 只由本模块纯函数计算——
- 候选未做预测、或证据不含该维度 ⇒ 该维不参与评分，剩余权重重新归一化；
- contradiction_penalty 来自 S2 冲突登记（只减分，不裁决）；
- weighted_fit ∈ [0, 1]，公式版本绑定（S3.8 消融校准，不得散落硬编码）。
全部确定性：同输入 ⇒ 同输出（可回放）。
"""
import math
from datetime import datetime
from typing import Optional, Sequence

from src.cognition.models import EvidenceFit, Hypothesis
from src.intel.judgment import EvidenceView
from src.intel.models import EvidenceConflict

# §7.2 维度权重（和为 1；S3.8 消融调参的唯一出处）
FIT_WEIGHTS: dict[str, float] = {
    "identity": 0.25,
    "position": 0.25,
    "count": 0.15,
    "motion": 0.10,
    "source": 0.15,
    "freshness": 0.10,
}
CONFLICT_WEIGHT = 0.20        # 冲突惩罚权重（§7.2 -w_conflict * penalty）
AMBIGUITY_BAND_DEFAULT = 0.15  # §7.3 plausible_set 容带（scenario 可覆盖）

# 候选类别 → 识别信号（与 context 装配的证据 identity_signal 同一刻度）
_CLASS_IDENTITY_SIGNAL = {
    "cv": 1.0, "cvl": 0.8, "bb": 0.9, "ca": 0.4, "cl": 0.4,
    "transport": 0.2, "unknown": 0.0,
}


def _identity_signal_of_class(predicted_class: str | None) -> float:
    return _CLASS_IDENTITY_SIGNAL.get((predicted_class or "").lower(), 0.3)


def _dim(view: EvidenceView, key: str) -> Optional[float]:
    v = view.dimensions.get(key)
    return float(v) if v is not None else None


def _dist_nm(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot((a[0] - b[0]) * 60.0,
                      (a[1] - b[1]) * 60.0 * math.cos(math.radians(a[0])))


def _used_views(h: Hypothesis, views: Sequence[EvidenceView]) -> list[EvidenceView]:
    if h.supporting_evidence_ids:
        ids = set(h.supporting_evidence_ids)
        subset = [v for v in views if v.evidence_id in ids]
        if subset:
            return subset
    return list(views)


def _identity_fit(h: Hypothesis, used: Sequence[EvidenceView]) -> Optional[float]:
    if h.predicted_class is None:
        return None
    signals = [_dim(v, "identity_signal") for v in used]
    signals = [s for s in signals if s is not None]
    if not signals:
        return None
    return max(0.0, 1.0 - abs(_identity_signal_of_class(h.predicted_class)
                              - sum(signals) / len(signals)))


def _position_fit(h: Hypothesis, used: Sequence[EvidenceView]) -> Optional[float]:
    if h.predicted_position is None:
        return None
    fits = []
    for v in used:
        lat, lon = _dim(v, "reported_lat"), _dim(v, "reported_lon")
        if lat is None or lon is None:
            continue
        d = _dist_nm(h.predicted_position, (lat, lon))
        fits.append(1.0 - min(1.0, d / 200.0))   # 200nm 量表（v0）
    return sum(fits) / len(fits) if fits else None


def _count_fit(h: Hypothesis, used: Sequence[EvidenceView]) -> Optional[float]:
    if h.predicted_count_range is None:
        return None
    mid = (h.predicted_count_range[0] + h.predicted_count_range[1]) / 2.0
    fits = []
    for v in used:
        c = _dim(v, "reported_count")
        if c is None:
            continue
        fits.append(1.0 - min(1.0, abs(mid - c) / 3.0))   # 3 艘量表（v0）
    return sum(fits) / len(fits) if fits else None


def _motion_fit(h: Hypothesis, used: Sequence[EvidenceView]) -> Optional[float]:
    course_fits, speed_fits = [], []
    for v in used:
        if h.predicted_course_range is not None:
            c = _dim(v, "reported_course")
            if c is not None:
                mid = (h.predicted_course_range[0] + h.predicted_course_range[1]) / 2.0
                delta = abs((c - mid + 180) % 360 - 180)
                course_fits.append(1.0 - min(1.0, delta / 90.0))
        if h.predicted_speed_range is not None:
            s = _dim(v, "reported_speed")
            if s is not None:
                mid = (h.predicted_speed_range[0] + h.predicted_speed_range[1]) / 2.0
                speed_fits.append(1.0 - min(1.0, abs(s - mid) / 20.0))  # 20kn 量表
    sub = course_fits + speed_fits
    return sum(sub) / len(sub) if sub else None


def _source_fit(h: Hypothesis, used: Sequence[EvidenceView]) -> Optional[float]:
    rels = [v.source_reliability for v in used if v.source_reliability is not None]
    return sum(rels) / len(rels) if rels else None


def _freshness_fit(h: Hypothesis, used: Sequence[EvidenceView],
                   now: Optional[datetime]) -> Optional[float]:
    if now is None:
        return None
    stamps = [v.received_at or v.observed_at for v in used]
    stamps = [s for s in stamps if s is not None]
    if not stamps:
        return None
    age_h = max(0.0, (now - max(stamps)).total_seconds() / 3600.0)
    return 1.0 / (1.0 + age_h / 6.0)   # 6 小时半衰（v0）


def _contradiction_penalty(h: Hypothesis, used: Sequence[EvidenceView],
                           conflicts: Sequence[EvidenceConflict] | None) -> float:
    if not conflicts:
        return 0.0
    cited = {v.evidence_id for v in used}
    penalty = 0.0
    for c in conflicts:
        if cited & set(c.evidence_ids):
            penalty += c.severity
    return min(1.0, penalty)


def compute_evidence_fit(h: Hypothesis, views: Sequence[EvidenceView], *,
                         now: Optional[datetime] = None,
                         conflicts: Sequence[EvidenceConflict] | None = None,
                         weights: dict[str, float] | None = None) -> EvidenceFit:
    """候选 × 证据视图 → EvidenceFit（规则独占；确定性纯函数）。"""
    w = dict(FIT_WEIGHTS if weights is None else weights)
    used = _used_views(h, views)
    dims = {
        "identity": _identity_fit(h, used),
        "position": _position_fit(h, used),
        "count": _count_fit(h, used),
        "motion": _motion_fit(h, used),
        "source": _source_fit(h, used),
        "freshness": _freshness_fit(h, used, now),
    }
    penalty = _contradiction_penalty(h, used, conflicts)
    avail = {k: v for k, v in dims.items() if v is not None}
    w_avail = sum(w[k] for k in avail)
    if w_avail <= 0:
        base = 0.0
    else:
        base = sum(w[k] * v for k, v in avail.items()) / w_avail
    weighted = max(0.0, min(1.0, base * (1.0 - CONFLICT_WEIGHT * penalty)))
    return EvidenceFit(
        hypothesis_id=h.id,
        identity_fit=dims["identity"],
        position_fit=dims["position"],
        count_fit=dims["count"],
        motion_fit=dims["motion"],
        source_fit=dims["source"],
        freshness_fit=dims["freshness"],
        contradiction_penalty=round(penalty, 4),
        weighted_fit=round(weighted, 4),
    )


def plausible_set(fits: dict[str, EvidenceFit],
                  ambiguity_band: float = AMBIGUITY_BAND_DEFAULT) -> list[str]:
    """§7.3 证据兼容集合：fit ≥ max_fit - band（含边界）；按 fit 降序。"""
    if not fits:
        return []
    max_fit = max(f.weighted_fit for f in fits.values())
    members = [f for f in fits.values()
               if f.weighted_fit >= max_fit - ambiguity_band - 1e-9]
    members.sort(key=lambda f: (-f.weighted_fit, f.hypothesis_id))
    return [f.hypothesis_id for f in members]
