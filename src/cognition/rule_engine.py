"""S3 规则判断引擎（Phase S3.2，计划 §十二 JudgmentEngine 实现）。

流程（计划 §八 8.1）：
  稳定键缓存（D9）→ 恰好一次 JUDGMENT_CHECK（D3）→ LLM 候选规范化（D2）→
  evidence_fit → plausible_set → 偏差预算 → 公式选择 → 错误/置信度 →
  JudgmentResult + JudgmentMemory + JudgmentAuditRecord。

纪律：LLM 不改写 chosen（本引擎在 LLM 调用后锁定）；actual_enemy 永不进入
（本引擎只消费 JudgmentContext 内的 EvidenceView，D6/D11）。
"""
from datetime import datetime
from typing import Optional

from src.cognition.candidates import CandidateGenerator, normalize_candidates
from src.cognition.contracts import FORMULA_VERSION, ConfidenceBand
from src.cognition.evidence_fit import (
    AMBIGUITY_BAND_DEFAULT,
    compute_evidence_fit,
    plausible_set,
)
from src.cognition.errors import evaluate_error
from src.cognition.formula import (
    compute_deviation_budget,
    normalize_attributes,
    score_candidates,
    select_chosen,
)
from src.cognition.memory import (
    anchor_bonus_for,
    apply_anchor,
    recall_relevant_memories,
)
from src.cognition.models import (
    ActorProfile,
    Hypothesis,
    JudgmentAuditRecord,
    JudgmentContext,
    JudgmentMemory,
    JudgmentResult,
    JudgmentTask,
)
from src.intel import service as intel
from src.intel.contracts import CheckType
from src.intel.policy import roll_judgment_dice
from src.intel.rng import RNGService

# §7.7 置信度阈值（v0 设计值；S3.8 消融校准）
CONFIDENCE_HIGH_FIT = 0.75
CONFIDENCE_HIGH_STRENGTH = 0.70
CONFIDENCE_MARGIN = 0.15
STALENESS_HOURS = 6.0


def find_cached_result(state, stable_key: str) -> Optional[JudgmentResult]:
    """D9：同稳定键返回已有结果（不重骰）。"""
    task_ids = {t.id for t in state.judgment_tasks if t.stable_key == stable_key}
    for r in state.judgment_results:
        if r.task_id in task_ids:
            return r
    return None


def _situational_mods(views: list) -> dict[str, int]:
    situational: dict[str, int] = {}
    if len(views) <= 1:
        situational["单一来源"] = -5
    if any((v.dimensions.get("identity_precision", 1) < 0.5) for v in views):
        situational["低精度证据"] = -5
    return situational


def evidence_strength(views: list) -> float:
    """证据强度（§7.7 输入）：可靠性 0.4 + 识别/位置/数量精度各 0.2（缺项归一）。"""
    if not views:
        return 0.0
    vals = []
    for v in views:
        terms = {"reliability": (v.source_reliability or 0.0, 0.4)}
        for key, w in (("identity_precision", 0.2), ("position_precision", 0.2),
                       ("count_precision", 0.2)):
            val = v.dimensions.get(key)
            if val is not None:
                terms[key] = (float(val), w)
        total_w = sum(w for _, w in terms.values())
        vals.append(sum(val * w for val, w in terms.values()) / total_w)
    return sum(vals) / len(vals)


def _is_stale(views: list, now: Optional[datetime]) -> bool:
    if now is None:
        return False
    stamps = [v.received_at or v.observed_at for v in views]
    stamps = [s for s in stamps if s is not None]
    if not stamps:
        return False
    age_h = (now - max(stamps)).total_seconds() / 3600.0
    return age_h > STALENESS_HOURS


def confidence_band(*, chosen_in_plausible: bool, best_fit: float, margin: float,
                    strength: float, stale: bool, conflict_high: bool) -> str:
    """§7.7 三档置信度：只由证据决定（fit/兼容集/强度/陈旧/冲突）。"""
    if not chosen_in_plausible:
        return ConfidenceBand.LOW.value
    if stale or conflict_high or strength < CONFIDENCE_HIGH_STRENGTH:
        return ConfidenceBand.LOW.value
    if best_fit >= CONFIDENCE_HIGH_FIT and margin >= CONFIDENCE_MARGIN:
        return ConfidenceBand.HIGH.value
    return ConfidenceBand.MEDIUM.value


class RuleJudgmentEngine:
    """通用 JudgmentEngine v0 实现（D15：不以 NPC 姓名拆分引擎）。"""

    def __init__(self, state, generator: CandidateGenerator,
                 rng: Optional[RNGService] = None):
        self._state = state
        self._generator = generator
        self._rng = rng

    def assess(self, task: JudgmentTask, context: JudgmentContext) -> JudgmentResult:
        state = self._state
        cached = find_cached_result(state, task.stable_key)
        if cached is not None:
            return cached

        # 1. 任务落档
        task.id = task.id or intel.next_id(state, "JT")
        task.created_at = context.now or state.clock.game_time
        state.judgment_tasks.append(task)

        # 2. 恰好一次 JUDGMENT_CHECK（D3）
        rng = self._rng or RNGService(state)
        actor = context.actor
        situational = _situational_mods(context.evidence)
        dice_result, check_rec = rng.roll_check(
            check_type=CheckType.JUDGMENT_CHECK,
            actor_id=actor.actor_id,
            npc_modifier=int(actor.attributes.get("competence", 5) * 2),
            situational_mods=situational,
            reason=f"{task.id} 参谋判断检定",
            inputs={"stable_key": task.stable_key,
                    "evidence": list(task.evidence_ids),
                    "domain": task.domain},
        )
        dice = roll_judgment_dice(rng, actor_id=actor.actor_id,
                                  level=dice_result.level,
                                  record_id=check_rec.check_id)

        # 3. LLM 候选 → 规范化（LLM 自带评分在此剥除，D2）
        hypotheses = normalize_candidates(self._generator.generate(task, context))

        # 4. 规则层评分（LLM 不可覆盖）
        now = context.now or state.clock.game_time
        band = context.scenario.get("ambiguity_band", AMBIGUITY_BAND_DEFAULT)
        fits = {
            h.id: compute_evidence_fit(h, context.evidence, now=now,
                                       conflicts=context.conflicts)
            for h in hypotheses
        }
        plausible = plausible_set(fits, ambiguity_band=band)

        # 5. 偏差预算 + 公式选择（含记忆锚定：坚持旧判断，M3.6.3）
        budget = compute_deviation_budget(
            dice.level, actor.attributes.get("competence", 5))
        scores = score_candidates(hypotheses, fits, actor,
                                  deviation_budget=budget)
        memories = context.memories or recall_relevant_memories(
            state, actor.actor_id, evidence_ids=task.evidence_ids)
        candidate_ids = {h.id for h in hypotheses}
        anchor = next((m for m in memories
                       if m.status == "open"
                       and m.selected_hypothesis in candidate_ids), None)
        bonus = 0.0
        if anchor is not None:
            bonus = anchor_bonus_for(anchor)
            scores = apply_anchor(scores, anchor.selected_hypothesis, bonus)
        chosen = select_chosen(scores)
        chosen_in_plausible = chosen in plausible

        # 6. 错误语义（§7.8：兼容集内不算错；集外按距离）与置信度（§7.7）
        by_id = {h.id: h for h in hypotheses}
        if chosen_in_plausible:
            error_type, error_severity = "none", 0.0
        else:
            reference = by_id[plausible[0]] if plausible else None
            error_type, error_severity = evaluate_error(
                by_id[chosen], reference) if reference else ("position", 1.0)
        margin = 1.0
        if len(fits) > 1:
            ordered = sorted((f.weighted_fit for f in fits.values()), reverse=True)
            margin = ordered[0] - ordered[1]
        conf = confidence_band(
            chosen_in_plausible=chosen_in_plausible,
            best_fit=fits[chosen].weighted_fit if chosen else 0.0,
            margin=margin,
            strength=evidence_strength(context.evidence),
            stale=_is_stale(context.evidence, now),
            conflict_high=any(c.severity >= 0.5 for c in context.conflicts),
        )

        # 7. JudgmentResult 落档（此后 LLM 只渲染不改写；建议域随 chosen 转移）
        chosen_h = by_id.get(chosen)
        result = JudgmentResult(
            id=intel.next_id(state, "JR"),
            task_id=task.id,
            actor_id=actor.actor_id,
            chosen_hypothesis_id=chosen,
            plausible_hypothesis_ids=list(plausible),
            dice_record_id=check_rec.check_id,
            error_type=error_type,
            error_severity=error_severity,
            confidence_band=conf,
            recommendation=chosen_h.recommendation if chosen_h else None,
            assumptions=list(chosen_h.assumptions) if chosen_h else [],
            change_my_mind=list(chosen_h.change_my_mind) if chosen_h else [],
            formula_version=FORMULA_VERSION,
            created_at=now,
        )
        state.judgment_results.append(result)

        # 8. JudgmentMemory（D8：按 actor 隔离；D10：由自身判断创建；
        #    修订链 supersedes：旧记忆只翻状态，M3.6.6）
        superseded = None
        if task.supersedes_task_id:
            old_task_ids = {task.supersedes_task_id}
            old_result_ids = {r.id for r in state.judgment_results
                              if r.task_id in old_task_ids and r.id != result.id}
            for m in state.judgment_memories:
                if (m.actor_id == actor.actor_id and m.status == "open"
                        and m.result_id in old_result_ids):
                    m.status = "revised"
                    superseded = m
        memory = JudgmentMemory(
            id=intel.next_id(state, "JM"),
            actor_id=actor.actor_id,
            task_type=task.task_type,
            domain=task.domain,
            result_id=result.id,
            selected_hypothesis=chosen,
            alternative_hypotheses=[h for h in plausible if h != chosen],
            evidence_ids=list(task.evidence_ids),
            confidence=conf,
            assumptions=result.assumptions,
            change_my_mind=list(result.change_my_mind),
            created_at=now,
            supersedes_id=superseded.id if superseded else None,
            revision_reason=task.revision_reason,
        )
        state.judgment_memories.append(memory)

        # 9. JudgmentAuditRecord（M3.9：可回放归因；候选快照供事后事实误差比对）
        state.judgment_audits.append(JudgmentAuditRecord(
            id=intel.next_id(state, "JA"),
            task_id=task.id,
            result_id=result.id,
            actor_id=actor.actor_id,
            formula_version=FORMULA_VERSION,
            attribute_snapshot=dict(actor.attributes),
            hypotheses=[h.model_dump() for h in hypotheses],
            candidate_scores=dict(scores),
            plausible_set=list(plausible),
            dice_record_id=check_rec.check_id,
            memory_ids=[memory.id],
            anchor_memory_id=anchor.id if anchor is not None else None,
            anchor_bonus=bonus,
            context_version=task.context_version,
            random_seed=check_rec.random_seed,
            created_at=now,
        ))
        intel._audit(state, actor_id=actor.actor_id, action="judgment",
                     target_id=result.id, reason=task.question_normalized,
                     evidence_ids=list(task.evidence_ids),
                     details={"task": task.id, "dice": check_rec.check_id,
                              "memory": memory.id})
        return result
