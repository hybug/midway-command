"""珊瑚海 1942-05-07 米西马方向纵切（Phase S3.6，计划 §十）。

历史事件链（一手史料见 docs/design/S3_COGNITION_SYSTEM.md §四）：
1. 向西北搜索的侦察机报告米西马岛以北「两艘航母四艘巡洋舰」（contact pad
   使用错误——规则侧真值是祥凤掩护群，玩家/参谋永远只见失真报告值）。
2. 三名参谋独立判断该报告是否支持立即全力攻击（职责边界各异）。
3. 侦察机返舰后勘误（contact pad 错误）+ 陆军飞机报告米西马附近航母群。
4. 各参谋按记忆锚定与新证据坚持或修订；指挥官比较后反馈。
5. 战后复盘区分「认知错误」（相对证据兼容集）与「事实误差」（相对真实结果）。

纪律：
- 全部电文经 S2 统一协议（拍发→通信检定→收报→证据→工作项→简报），无旁路。
- actual_enemy 真值只在规则侧与战后复盘入参出现（D11）。
- 判断经 RuleJudgmentEngine（恰好一次 JUDGMENT_CHECK，稳定键防重骰）。
"""
from datetime import timedelta

from src.cognition import context as cognition
from src.cognition.candidates import normalize_candidates
from src.cognition.memory import recall_relevant_memories, record_commander_feedback
from src.cognition.models import ActorProfile, JudgmentContext, JudgmentTask
from src.cognition.persona import render_report
from src.cognition.roster import get_actor
from src.cognition.rule_engine import RuleJudgmentEngine
from src.intel import service as intel
from src.intel.contracts import SourceType, WorkPriority
from src.intel.models import MessageEnvelope, SourceObservation
from src.intel.rng import RNGService
from src.intel.flow import intel_work_queue, run_intelligence_cycle
from src.scouting import _bearing_distance_to_position, compute_report_delay

# 战术问题（计划 §十 第一纵切判断问题）
MISIMA_QUESTION = "这份米西马方向接触报告是否足以支持立即放飞全力攻击？"

# 规则侧真值（永不下发；仅供战后复盘比对，D11）
TRUE_COVER_GROUP = {
    "classification": "CVL",       # 祥凤（轻航母）
    "count": 1,
    "position": (-10.9, 152.9),    # 米西马近海路易西亚德方向
}

# 报告值（失真后，contact pad 错误的产物；所有参谋/玩家只见这些）
_PAD_ERROR_REPORT = {
    "bearing": 315, "distance_nm": 200, "count": 2,
    "classification": "CV", "quality": "standard", "sensor": "carrier_scout",
}
_CORRECTION_REPORT = {
    "bearing": 315, "distance_nm": 200, "count": 0,
    "classification": "大型船只（未识别）", "quality": "low",
    "sensor": "carrier_scout",
}
_ARMY_REPORT = {
    "bearing": 330, "distance_nm": 330, "count": 1,
    "classification": "CV", "quality": "standard", "sensor": "patrol_air",
}

_OFFICERS = ("tf17_intel", "fitch", "tf17_ops")


def build_coral_may7_state(seed=42):
    """珊瑚海 5/7 清晨开局：TF17（约克城）+TF11（列克星敦），规则侧真值入档。"""
    from src.state import Carrier, GameClock, GameState, Position, TaskForce
    from datetime import datetime, timezone
    yor = TaskForce(name="TF17", course=315, speed=27, carriers=[
        Carrier(name="USS Yorktown (CV-5)",
                position=Position(lat=-15.5, lon=155.6), cap_strength=12),
    ])
    lex = TaskForce(name="TF11", course=315, speed=27, carriers=[
        Carrier(name="USS Lexington (CV-2)",
                position=Position(lat=-15.7, lon=155.4), cap_strength=12),
    ])
    state = GameState(
        clock=GameClock(game_time=datetime(1942, 5, 7, 0, 30, tzinfo=timezone.utc)),
        task_forces=[yor, lex],
    )
    state.rng_seed = seed
    # 规则侧真值（D11：永不进入 prompt/玩家 API/前端）
    state.actual_enemy = [
        {"name": "MO_MAIN", "carriers": ["CV_A", "CV_B"],
         "position": {"lat": -12.0, "lon": 157.0}, "status": "moving"},
        {"name": "MO_COVER", "carriers": ["CVL_A"],
         "position": {"lat": TRUE_COVER_GROUP["position"][0],
                      "lon": TRUE_COVER_GROUP["position"][1]}, "status": "covering"},
    ]
    return state


def _file_and_transmit(state, *, sender_id, call_sign, kind, raw_text, fields,
                       observation=None, priority=WorkPriority.FLASH,
                       supersedes_message_id=None):
    """按 S2 统一协议拍发：落档 → 通信链 → 通信检定（延迟/丢失）→ ETA。"""
    msg = MessageEnvelope(
        sender_id=sender_id, sender_call_sign=call_sign,
        recipient_ids=["TF17 FLAG"], priority=priority, message_kind=kind,
        observed_at=state.clock.game_time, raw_text=raw_text,
        fields=dict(fields), observation_id=observation.id if observation else None,
        supersedes_message_id=supersedes_message_id,
    )
    intel.file_message(state, msg, by=sender_id, reason="纵切电文拍发")
    intel.mark_in_transit(state, msg, by="TBS 通信链", reason="发往旗舰")
    rng = RNGService(state)
    comm, _rec = rng.communication_check(
        actor_id=f"{call_sign} 电台", competence=6,
        distance_nm=float(fields.get("distance_nm", 150)),
        reason=f"{call_sign} 通信检定")
    delay = compute_report_delay(float(fields.get("distance_nm", 150)), rng=rng)
    msg.transit_eta = state.clock.game_time + timedelta(minutes=delay)
    if comm.raw_roll <= 3:
        intel.lose_message(state, msg, by="TBS 通信链", reason="通信检定大失败——电文丢失")
    else:
        from src.intel.contracts import CommCondition
        if comm.level == "critical_failure":
            msg.condition = CommCondition.GARBLED
        elif comm.level == "partial":
            msg.condition = CommCondition.PARTIAL
        else:
            msg.condition = CommCondition.COMPLETE
    return msg


def file_misima_contact(state):
    """事件 1：米西马方向接触报告（contact pad 错误的失真报告值）。"""
    obs = SourceObservation(
        id=intel.next_id(state, "OBS"),
        source_id="VS-5-2B", source_type=SourceType.CARRIER_SCOUT,
        observer_actor_id="sbd_scout_pilot",
        observed_at=state.clock.game_time,
        bearing_true=315.0, distance_nm_true=200.0,
        target_name_true="", carrier_count_true=1,     # 真值：1 轻航母掩护群
        quality_band="standard", internal_truth_ref="MO_COVER",
    )
    state.observations.append(obs)
    text = ("TWO CARRIERS FOUR CRUISERS BEARING 315 DIST 200 NM "
            "POSITION NORTH OF MISIMA")
    return _file_and_transmit(
        state, sender_id="sbd_scout_pilot", call_sign="VS-5-2B",
        kind="scout_report", raw_text=text, fields=dict(_PAD_ERROR_REPORT),
        observation=obs)


def file_pad_error_correction(state, original):
    """事件 3a：返舰后发现 contact pad 使用错误——勘误电报（原电文保留）。"""
    text = ("CORRECTION TO MY EARLIER REPORT: CONTACT PAD ERROR - "
            "CANNOT CONFIRM CARRIERS, ONLY LARGE VESSELS SIGHTED")
    return _file_and_transmit(
        state, sender_id="sbd_scout_pilot", call_sign=original.sender_call_sign,
        kind="correction", raw_text=text, fields=dict(_CORRECTION_REPORT),
        priority=WorkPriority.CORRECTION, supersedes_message_id=original.id)


def file_army_air_report(state):
    """事件 3b：陆军飞机报告米西马附近航母群（新证据，非勘误）。"""
    text = ("ARMY AIRCRAFT REPORTS ONE CARRIER FOUR CRUISERS "
            "MISIMA AREA BEARING 330 DIST 330 NM")
    return _file_and_transmit(
        state, sender_id="army_recon", call_sign="ARMY-RECON",
        kind="scout_report", raw_text=text, fields=dict(_ARMY_REPORT))


def brief_new_evidence(state):
    """情报参谋按 S2 链研判全部待处理工作项并呈报（新证据对班子可见的分发事件）。"""
    for item in intel_work_queue(state):
        if item.status == "assigned":
            run_intelligence_cycle(state, item)


# ── 候选脚本（计划 §十 三候选；测试/降级环境替代 LLM 生成）──

_H1 = {"text": "发现日军主力航母群，应立即全力攻击。",
       "predicted_class": "CV", "predicted_count_range": (2, 4),
       "predicted_position": (-13.1, 153.2),
       "predicted_course_range": (110, 160), "predicted_speed_range": (16, 22),
       "assumptions": ["侦察识别正确", "基准点无误"]}
_H2 = {"text": "发现的是莫尔兹比港掩护群，甚至包括轻航母。",
       "predicted_class": "CVL", "predicted_count_range": (1, 3),
       "predicted_position": (-10.7, 152.8),
       "assumptions": ["日军会以掩护群先行"]}
_H3 = {"text": "标图、基准点或通信发生错误，当前报告不可靠。",
       "assumptions": ["单机远程识别与手绘基准易出错"]}


class CoralMay7Generators:
    """三名参谋的候选脚本：同一场面下按职责生成不同候选集。"""

    def for_actor(self, actor_id, evidence_ids):
        ev = list(evidence_ids)
        if actor_id == "tf17_intel":
            return [
                {**_H1, "supporting_evidence_ids": list(ev),
                 "recommendation": "候选判断仅供比对，建议先由我确认可靠性。",
                 "change_my_mind": ["第二来源印证或勘误到达时重新研判"]},
                {**_H2, "supporting_evidence_ids": list(ev),
                 "recommendation": "若为掩护群，打击窗口仍在，先核实再放飞。",
                 "change_my_mind": ["陆军或岸基飞机报告米西马方向航母群时改判"]},
                {**_H3, "supporting_evidence_ids": [],
                 "recommendation": "证据单一且识别精度不足，建议暂缓全力攻击。",
                 "change_my_mind": ["收到可靠第二来源时恢复判断"]},
            ]
        if actor_id == "fitch":
            return [
                {**_H1, "supporting_evidence_ids": list(ev),
                 "recommendation": "若是主力，立即放飞全部攻击队抢占窗口。",
                 "change_my_mind": ["确认敌主力不在该方向时收拢攻击队"]},
                {**_H2, "supporting_evidence_ids": list(ev),
                 "predicted_count_range": (1, 2),
                 "recommendation": "轻航母掩护群也是高价值目标，可先制攻击。",
                 "change_my_mind": ["目标确认为误报时召回攻击队"]},
            ]
        if actor_id == "tf17_ops":
            return [
                {**_H3, "supporting_evidence_ids": [],
                 "recommendation": "舰队位置与油量不宜在情报未印证时全力出击，"
                                   "建议加强 CAP 并保持接近航向。",
                 "change_my_mind": ["多来源印证接触后支持放飞"]},
                {**_H1, "supporting_evidence_ids": list(ev),
                 "predicted_count_range": (2, 2),
                 "recommendation": "若确认主力，分批放飞并保持撤退航线。",
                 "change_my_mind": ["敌 CAP 压制过强时中止第二波"]},
            ]
        raise KeyError(f"纵切脚本无此角色候选: {actor_id}")


# ── 判断执行 ──

def staff_judgment_one(state, actor_id, domain, question, generators=None,
                       task=None):
    """一名参谋的一次判断：装配权限证据 → 引擎 → 人物化报告（降级显式标记）。"""
    actor = get_actor(actor_id)
    views = cognition.actor_evidence_views(state, actor)
    evidence_ids = [v.evidence_id for v in views]
    raw = (generators.for_actor(actor_id, evidence_ids) if generators else [])
    memories = recall_relevant_memories(state, actor_id, evidence_ids=evidence_ids)
    ctx = JudgmentContext(
        actor=actor, evidence=views, memories=memories,
        now=state.clock.game_time, duty_boundary=list(actor.duty_boundary),
    )
    if task is None:
        task = JudgmentTask(
            task_type="assess", domain=domain or actor.domain,
            actor_id=actor_id, question=question,
            evidence_ids=evidence_ids, source="commander",
            created_at=state.clock.game_time,
        )
        state.judgment_tasks.append(task)
    engine = RuleJudgmentEngine(state, _ScriptedAdapter(raw))
    result = engine.assess(task, ctx)
    audit = next((a for a in state.judgment_audits if a.result_id == result.id), None)
    hyps = _hyps_public(audit)
    report = render_report(actor, task, result, hyps, client=None)  # 无 LLM 降级
    state.judgment_reports[result.id] = report
    return {"task": task, "result": result, "report": report,
            "hypotheses": hyps, "audit": audit}


class _ScriptedAdapter:
    """把场景脚本候选接入引擎协议（generate → list[dict]）。"""

    def __init__(self, raw):
        self._raw = raw

    def generate(self, task, context):
        return self._raw


def _hyps_public(audit):
    if audit is None:
        return []
    return [
        {k: h.get(k) for k in ("id", "text", "predicted_class", "assumptions")}
        for h in audit.hypotheses
    ]


def staff_judgments_misima(state, generators=None):
    """事件 2：三名参谋独立判断同一战术问题（玩家可比较三份人物化建议）。"""
    brief_new_evidence(state)     # 先按 S2 链呈报证据（班子可见性前提）
    outcomes = {}
    for actor_id in _OFFICERS:
        outcomes[actor_id] = staff_judgment_one(
            state, actor_id, get_actor(actor_id).domain, MISIMA_QUESTION,
            generators=generators)
    return outcomes


def reassess(state, actor_id, rev_task, generators=None):
    """修订研判：新证据已呈报后，按修订任务重判（记忆锚定仍生效）。"""
    outcome = staff_judgment_one(state, actor_id, rev_task.domain,
                                 rev_task.question, generators=generators,
                                 task=rev_task)
    return outcome


def commander_feedback(state, actor_id, result_id, decision, note=""):
    """事件 4：指挥官比较三份建议后反馈（进记忆，不改写原结果，§8.3）。"""
    return record_commander_feedback(state, result_id, decision,
                                     by="fletcher", note=note)
