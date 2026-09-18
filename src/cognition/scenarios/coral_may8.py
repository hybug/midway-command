"""珊瑚海 1942-05-08 扩展纵切（Phase S3.7，计划 §十）。

多阶段侦察报告：列克星敦侦察机黎明报告「两艘航母四艘重巡多驱逐」
（航向 006°、120 海里、15 节）→ 基准点变化：修正为「真方位 028°、175 海里」。
同一批参谋按多版本证据坚持或修订；09:08 Fitch 任战术指挥官（OTC）。

与 5/7 模块共用 S2 电文协议、判断引擎与记忆机制；本模块只编排事件与比较视图。
"""
from datetime import datetime, timedelta, timezone

from src.cognition import context as cognition
from src.cognition.memory import recall_relevant_memories
from src.cognition.models import JudgmentContext, JudgmentTask
from src.cognition.persona import render_report
from src.cognition.roster import get_actor
from src.cognition.rule_engine import RuleJudgmentEngine
from src.cognition.scenarios.coral_may7 import (
    _OFFICERS,
    _file_and_transmit,
    _hyps_public,
    brief_new_evidence,
)
from src.intel import service as intel
from src.intel.contracts import WorkPriority

# 战术问题（5/8）：敌主力接触方位多版本下的攻击决心
CONTACT_QUESTION = "黎明搜索报告的敌航母编队是否足以支持及早放飞攻击？"

_DAWN_REPORT = {
    "bearing": 6, "distance_nm": 120, "count": 2,
    "classification": "CV", "quality": "high", "sensor": "carrier_scout",
    "course": 6, "speed": 15,
}
_BEARING_CORRECTION = {
    "bearing": 28, "distance_nm": 175, "count": 2,
    "classification": "CV", "quality": "high", "sensor": "carrier_scout",
    "course": 6, "speed": 15,
}


def file_dawn_search_report(state):
    """事件 1：列克星敦侦察机黎明接触报告（含航向/航速要素）。"""
    from src.intel.models import SourceObservation
    from src.intel.contracts import SourceType
    obs = SourceObservation(
        id=intel.next_id(state, "OBS"),
        source_id="VS-2-14S", source_type=SourceType.CARRIER_SCOUT,
        observer_actor_id="sbd_scout_pilot",
        observed_at=state.clock.game_time,
        bearing_true=28.0, distance_nm_true=175.0,
        target_name_true="", carrier_count_true=2,
        quality_band="high", internal_truth_ref="MO_MAIN",
    )
    state.observations.append(obs)
    text = ("TWO CV FOUR CA MANY DD BEARING 006 DIST 120, "
            "ENEMY COURSE 006 SPEED 15")
    from src.cognition.scenarios.coral_may7 import _file_and_transmit as _ft
    return _ft(
        state, sender_id="sbd_scout_pilot", call_sign="VS-2-14S",
        kind="scout_report", raw_text=text, fields=dict(_DAWN_REPORT),
        observation=obs)


def file_true_bearing_correction(state, original):
    """事件 2：基准点变化——真方位 028°、175 海里（勘误协议，原文保留）。"""
    from src.cognition.scenarios.coral_may7 import _file_and_transmit as _ft
    text = ("CORRECTION: REFER TRUE BEARING 028 DISTANCE 175 NM, "
            "SAME FORCE ENEMY COURSE 006 SPEED 15")
    return _ft(
        state, sender_id="sbd_scout_pilot", call_sign=original.sender_call_sign,
        kind="correction", raw_text=text, fields=dict(_BEARING_CORRECTION),
        priority=WorkPriority.CORRECTION, supersedes_message_id=original.id)


def promote_fitch_otc(state):
    """事件 3：09:08 Fitch 被指定为 Officer in Tactical Command（入档可查）。"""
    state.clock.game_time = state.clock.game_time.replace(hour=9, minute=8)
    entry = intel._audit(state, actor_id="fletcher", action="otc_change",
                         target_id="fitch",
                         reason="Fitch 于 09:08 被指定为战术指挥官（OTC）",
                         details={"at": state.clock.game_time.isoformat()})
    return entry


# ── 5/8 候选脚本（方位修正前/后两版；测试替代 LLM）──

class CoralMay8Generators:
    """同一场面、两个证据阶段：候选预测随参谋对证据的读数更新。"""

    def for_actor(self, actor_id, evidence_ids, phase="post"):
        ev = list(evidence_ids)
        pos = (-12.9, 157.0) if phase == "post" else (-13.5, 155.8)
        if actor_id == "tf17_intel":
            return [
                {"text": ("敌主力位于真方位 028 方向约 175 海里，正以 15 节西行。"
                 if phase == "post" else
                 "敌主力位于 006 方向约 120 海里，正以 15 节西行。"),
                 "predicted_class": "CV", "predicted_count_range": (2, 2),
                 "predicted_position": pos,
                 "predicted_course_range": (0, 20), "predicted_speed_range": (12, 18),
                 "supporting_evidence_ids": list(ev),
                 "assumptions": ["观测单位识别可靠"],
                 "recommendation": "接触已较可靠，可及早放飞攻击队。",
                 "change_my_mind": ["勘误或第二来源否定该方位时重新研判"]},
                {"text": "报告基于单一观测，方位基准此前已出过错。",
                 "supporting_evidence_ids": [],
                 "recommendation": "在放飞前要求再确认一次方位。",
                 "change_my_mind": ["基准点变化被证实后恢复判断"]},
            ]
        if actor_id == "fitch":
            return [
                {"text": ("敌编队已修正至真方位 028、175 海里，航向 006、航速 15 节；攻击窗口就在上午，应立即放飞。"
                 if phase == "post" else
                 "敌编队航向 006、航速 15 节，上午有窗口；建议一小时里放飞。"),
                 "predicted_class": "CV", "predicted_count_range": (2, 2),
                 "predicted_position": pos,
                 "predicted_course_range": (0, 20), "predicted_speed_range": (12, 18),
                 "supporting_evidence_ids": list(ev),
                 "recommendation": "立即组织最大编队攻击，护航机同步起飞。",
                 "change_my_mind": ["敌位置修正超出攻击半径时改判"]},
            ]
        if actor_id == "tf17_ops":
            return [
                {"text": "两份方位相互矛盾，舰队宜保持现有航向并加强 CAP。",
                 "supporting_evidence_ids": [],
                 "recommendation": "在方位统一前不全员出击，分批梯次准备。",
                 "change_my_mind": ["方位修正与第二来源一致时支持放飞"]},
                {"text": "若确认敌在 028 方向，建议保持甲板待命以备反方向接触。",
                 "predicted_class": "CV", "predicted_count_range": (2, 2),
                 "predicted_position": pos if phase == "post" else (-13.5, 155.8),
                 "supporting_evidence_ids": list(ev),
                 "recommendation": "谨慎支持放飞一半攻击队。",
                 "change_my_mind": ["敌 CAP 状况明朗后调整"]},
            ]
        raise KeyError(f"5/8 脚本无此角色候选: {actor_id}")


def staff_judgment_one(state, actor_id, question, generators=None,
                       task=None, phase="post"):
    actor = get_actor(actor_id)
    views = cognition.actor_evidence_views(state, actor)
    evidence_ids = [v.evidence_id for v in views]
    raw = (generators.for_actor(actor_id, evidence_ids, phase=phase)
           if generators else [])
    memories = recall_relevant_memories(state, actor_id, evidence_ids=evidence_ids)
    ctx = JudgmentContext(
        actor=actor, evidence=views, memories=memories,
        now=state.clock.game_time, duty_boundary=list(actor.duty_boundary),
    )
    if task is None:
        task = JudgmentTask(
            task_type="assess", domain=actor.domain, actor_id=actor_id,
            question=question, evidence_ids=evidence_ids, source="commander",
            created_at=state.clock.game_time)
        state.judgment_tasks.append(task)
    engine = RuleJudgmentEngine(state, _Adapter(raw))
    result = engine.assess(task, ctx)
    audit = next((a for a in state.judgment_audits if a.result_id == result.id), None)
    report = render_report(actor, task, result, _hyps_public(audit), client=None)
    state.judgment_reports[result.id] = report
    return {"task": task, "result": result, "report": report,
            "hypotheses": _hyps_public(audit), "audit": audit}


class _Adapter:
    def __init__(self, raw):
        self._raw = raw or []

    def generate(self, task, context):
        return self._raw


def staff_judgments_contact(state, generators=None, phase="post"):
    """三名参谋对 5/8 接触报告的独立判断（先按 S2 链呈报证据）。"""
    brief_new_evidence(state)
    outcomes = {}
    for actor_id in _OFFICERS:
        outcomes[actor_id] = staff_judgment_one(
            state, actor_id, CONTACT_QUESTION, generators=generators, phase=phase)
    return outcomes


def reassess_all(state, first_outcomes, generators=None):
    """基准点修正后全员修订研判（记忆锚定仍在）。"""
    revised = {}
    for actor_id, outcome in first_outcomes.items():
        old_result = outcome["result"]
        old_task = next(t for t in state.judgment_tasks if t.id == old_result.task_id)
        rev_task = JudgmentTask(
            task_type="assess", domain=old_task.domain, actor_id=actor_id,
            question=old_task.question,
            evidence_ids=sorted({e for e in old_task.evidence_ids}
                                | {v.evidence_id
                                   for v in cognition.actor_evidence_views(
                                       state, get_actor(actor_id))}),
            context_version=old_task.context_version + 1,
            source="revision", supersedes_task_id=old_task.id,
            revision_reason="基准点变化：真方位修正 028°/175 海里",
            created_at=state.clock.game_time,
        )
        state.judgment_tasks.append(rev_task)
        revised[actor_id] = staff_judgment_one(
            state, actor_id, old_task.question, generators=generators,
            task=rev_task, phase="post")
    return revised


def revision_comparison(state):
    """玩家比较视图：每名参谋 修正前→修正后 是否改变、为什么（自然语言）。"""
    out = []
    for actor_id in _OFFICERS:
        results = [r for r in state.judgment_results if r.actor_id == actor_id]
        if len(results) < 2:
            continue
        before, after = results[-2], results[-1]
        old_mem = next(m for m in state.judgment_memories
                       if m.result_id == before.id)
        audits = {a.result_id: a for a in state.judgment_audits}

        def _chosen_text(result):
            audit = audits.get(result.id)
            hyp = next((h for h in (audit.hypotheses if audit else [])
                        if h.get("id") == result.chosen_hypothesis_id), None)
            return hyp.get("text", "") if hyp else ""

        before_text, after_text = _chosen_text(before), _chosen_text(after)
        changed = (before.chosen_hypothesis_id != after.chosen_hypothesis_id
                   or before_text != after_text)
        reason = next(
            (t.revision_reason for t in state.judgment_tasks
             if t.id == after.task_id), "")
        out.append({
            "actor_id": actor_id,
            "before_result_id": before.id,
            "after_result_id": after.id,
            "before_chosen_text": before_text,
            "after_chosen_text": after_text,
            "before_confidence": before.confidence_band,
            "after_confidence": after.confidence_band,
            "changed": changed,
            "revision_reason": reason or (old_mem.revision_reason or ""),
        })
    return out
