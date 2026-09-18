"""候选判断规范化（Phase S3.1，计划 §M3.3）。

职责（D2）：LLM 只生成候选文本与结构化预测；本模块把 raw 字典规范化为
Hypothesis——剥除 LLM 自带的任何评分字段（LLM 不能覆盖 evidence_fit）、
指派 H1..Hn 稳定 id、结构去重、数量控制（1–3）、规则侧计算
aggressiveness/novelty（不采用 LLM 自评分，§7.6）。
"""
import re
from typing import Any, Protocol, runtime_checkable

from src.cognition.models import Hypothesis, JudgmentContext, JudgmentTask

MAX_CANDIDATES = 3

# LLM 不允许自带的评分字段（剥除而非报错——容错 LLM 输出）
_FORBIDDEN_SCORE_FIELDS = ("evidence_fit", "weighted_fit", "score", "fit",
                           "plausible", "chosen")

# 进攻性分类系数（v0 设计值；S3.8 消融校准，§7.6/§7.4）
_CLASS_ACTIONABILITY = {
    "cv": 1.0, "cvl": 0.8, "bb": 0.7, "ca": 0.5, "cl": 0.4,
    "transport": 0.6, "unknown": 0.3,
}


@runtime_checkable
class CandidateGenerator(Protocol):
    """候选生成器（LLM 实现，S3.5 接入；测试注入 fake）。"""

    def generate(self, task: JudgmentTask, context: JudgmentContext) -> list[dict]: ...


def _text_key(text: str) -> str:
    return re.sub(r"[\W_]+", "", text or "").lower()


def _bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def _structural_signature(raw: dict) -> tuple:
    def bucket(v, size):
        return None if v is None else int(v // size)

    pos = raw.get("predicted_position")
    pos_b = None if not pos else (round(pos[0]), round(pos[1]))
    course = raw.get("predicted_course_range")
    course_b = None if not course else bucket(course[0], 30)
    speed = raw.get("predicted_speed_range")
    speed_b = None if not speed else bucket(speed[0], 5)
    return (raw.get("predicted_class"), raw.get("predicted_count_range"),
            pos_b, course_b, speed_b)


def _is_duplicate(a_raw: dict, b_key: str, b_sig: tuple) -> bool:
    a_key = _text_key(a_raw.get("text", ""))
    if a_key == b_key:
        return True
    if _structural_signature(a_raw) != b_sig:
        return False
    ga, gb = _bigrams(a_key), _bigrams(b_key)
    if not ga or not gb:
        return False
    jaccard = len(ga & gb) / len(ga | gb)
    return jaccard >= 0.6


def _coerce_hypothesis(idx: int, raw: dict) -> Hypothesis | None:
    cleaned = {k: v for k, v in raw.items() if k not in _FORBIDDEN_SCORE_FIELDS}
    cleaned["id"] = f"H{idx + 1}"
    cleaned["text"] = str(cleaned.get("text", "")).strip()
    for tuple_field in ("predicted_count_range", "predicted_position",
                        "predicted_course_range", "predicted_speed_range"):
        if isinstance(cleaned.get(tuple_field), list):
            cleaned[tuple_field] = tuple(cleaned[tuple_field])
    if not cleaned["text"]:
        return None
    try:
        return Hypothesis(**cleaned)
    except Exception:
        return None  # 规范化失败（LLM 输出畸形）→ 丢弃该候选，不臆造


def _aggressiveness(h: Hypothesis) -> float:
    """进攻倾向（§7.6 规则计算）：可打击的明确接触 + 低威胁估计 → 高。"""
    a_class = _CLASS_ACTIONABILITY.get(
        (h.predicted_class or "").lower(), 0.3)
    a_pos = 1.0 if h.predicted_position is not None else 0.4
    if h.predicted_count_range is not None:
        a_opt = 1.0 - min(1.0, h.predicted_count_range[1] / 4.0)
    else:
        a_opt = 0.5
    score = 0.5 * a_class + 0.3 * a_pos + 0.2 * a_opt
    return round(score * 2.0 - 1.0, 2)


def _novelty(h: Hypothesis, batch: list[Hypothesis]) -> float:
    """新颖度（§7.6 规则计算）：未知补全 + 少证据支撑 + 少数派解释 → 高。"""
    unknown = 1.0 if (h.predicted_class is None
                      or h.predicted_class.lower() == "unknown") else 0.0
    max_support = max(1, max(len(b.supporting_evidence_ids) for b in batch))
    support_ratio = len(h.supporting_evidence_ids) / max_support
    same_class = sum(1 for b in batch
                     if (b.predicted_class or "").lower()
                     == (h.predicted_class or "").lower())
    class_share = same_class / len(batch)
    return round(0.4 * unknown + 0.3 * (1 - support_ratio)
                 + 0.3 * (1 - class_share), 2)


def normalize_candidates(raw: list[dict]) -> list[Hypothesis]:
    """raw LLM 候选 → 规范化 Hypothesis 列表（id 指派/去重/限量/规则装饰）。"""
    cleaned: list[dict] = []
    for entry in raw or []:
        if not isinstance(entry, dict):
            continue
        key = _text_key(entry.get("text", ""))
        sig = _structural_signature(entry)
        if any(_is_duplicate(entry, k, s) for k, s, _ in cleaned):
            continue
        cleaned.append((key, sig, entry))
    hypotheses: list[Hypothesis] = []
    for idx, (_, _, entry) in enumerate(cleaned[:MAX_CANDIDATES]):
        h = _coerce_hypothesis(idx, entry)
        if h is not None:
            hypotheses.append(h)
    batch = hypotheses
    return [h.model_copy(update={
        "aggressiveness": _aggressiveness(h),
        "novelty": _novelty(h, batch),
    }) for h in hypotheses]
