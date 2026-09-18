"""错误语义距离（Phase S3.2 落地 §7.8；S3.3 补充事后事实误差）。

「错」的定义（M3.5）：相对证据兼容集合（plausible_set）的偏离——
chosen ∈ 兼容集 ⇒ 不算认知错误（error_type=none, severity=0）；
chosen ∉ 兼容集 ⇒ 以兼容集最优候选为参照，按五维结构化距离计算：

  D_error = 0.70 * max(distances) + 0.30 * weighted_mean(distances)
  error_type = 最大距离对应维度（同值按固定维度序，保证可回放）

actual_enemy 不参与实时错误判定（D11）——本模块只比较两个 Hypothesis 的
结构化预测，无任何规则侧真值输入。
"""
import math

from src.cognition.models import Hypothesis

MAX_WEIGHT = 0.70
MEAN_WEIGHT = 0.30

# 维度固定序（argmax 并列时的确定性打破）
_DISTANCE_DIMS = ("identity", "count", "position", "course", "speed")

# 单侧缺预测的中性距离（无法比较也不给虚假满分）
_MISSING_PENALTY = 0.5

_IDENTITY_SIGNAL = {
    "cv": 1.0, "cvl": 0.8, "bb": 0.9, "ca": 0.4, "cl": 0.4,
    "transport": 0.2, "unknown": 0.0,
}


def _signal(cls: str | None) -> float | None:
    if cls is None:
        return None
    return _IDENTITY_SIGNAL.get(cls.lower(), 0.3)


def _range_mid(rng) -> float | None:
    if rng is None:
        return None
    return (rng[0] + rng[1]) / 2.0


def hypothesis_distances(chosen: Hypothesis, reference: Hypothesis) -> dict[str, float]:
    """chosen 相对参照候选的五维结构化距离（全部 ∈ [0,1]）。"""
    out: dict[str, float] = {}
    # 识别：类别信号差
    cs, rs = _signal(chosen.predicted_class), _signal(reference.predicted_class)
    if cs is None and rs is None:
        out["identity"] = 0.0
    elif cs is None or rs is None:
        out["identity"] = _MISSING_PENALTY
    else:
        out["identity"] = round(abs(cs - rs), 4)
    # 数量：区间中点差 / 4（4 艘 = 满误差）
    cm, rm = _range_mid(chosen.predicted_count_range), _range_mid(reference.predicted_count_range)
    if cm is None and rm is None:
        out["count"] = 0.0
    elif cm is None or rm is None:
        out["count"] = _MISSING_PENALTY
    else:
        out["count"] = round(min(1.0, abs(cm - rm) / 4.0), 4)
    # 位置：局部平面距离 / 200nm
    cp, rp = chosen.predicted_position, reference.predicted_position
    if cp is None and rp is None:
        out["position"] = 0.0
    elif cp is None or rp is None:
        out["position"] = _MISSING_PENALTY
    else:
        d = math.hypot((cp[0] - rp[0]) * 60.0,
                       (cp[1] - rp[1]) * 60.0 * math.cos(math.radians(cp[0])))
        out["position"] = round(min(1.0, d / 200.0), 4)
    # 航向：区间中点圆周差 / 90°
    ccm, rcm = _range_mid(chosen.predicted_course_range), _range_mid(reference.predicted_course_range)
    if ccm is None and rcm is None:
        out["course"] = 0.0
    elif ccm is None or rcm is None:
        out["course"] = _MISSING_PENALTY
    else:
        delta = abs((ccm - rcm + 180) % 360 - 180)
        out["course"] = round(min(1.0, delta / 90.0), 4)
    # 航速：区间中点差 / 20kn
    csm, rsm = _range_mid(chosen.predicted_speed_range), _range_mid(reference.predicted_speed_range)
    if csm is None and rsm is None:
        out["speed"] = 0.0
    elif csm is None or rsm is None:
        out["speed"] = _MISSING_PENALTY
    else:
        out["speed"] = round(min(1.0, abs(csm - rsm) / 20.0), 4)
    return out


def evaluate_error(chosen: Hypothesis, reference: Hypothesis) -> tuple[str, float]:
    """返回 (error_type, error_severity)：类型=最大距离维度，严重度=§7.8 合成。"""
    distances = hypothesis_distances(chosen, reference)
    worst = max(distances[d] for d in _DISTANCE_DIMS)
    if worst <= 0.0:
        return "none", 0.0
    mean = sum(distances[d] for d in _DISTANCE_DIMS) / len(_DISTANCE_DIMS)
    severity = max(0.0, min(1.0, MAX_WEIGHT * worst + MEAN_WEIGHT * mean))
    # 固定维度序打破并列（可回放）
    error_type = next(d for d in _DISTANCE_DIMS if distances[d] == worst)
    return error_type, round(severity, 4)
