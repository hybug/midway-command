"""S2.3 舰载侦察机纵切编排（探测 → 报告 → 通信 → 收报 → 研判 → 简报）。

流程（计划 §7.1 步骤 4-15）：
1. 探测检定成功（scouting 管线调用 on_scout_detection）
2. 观察质量检定 → 失真参数带 → SourceObservation（规则侧）
3. 报告 NPC 按人物风格撰写电文（writer；无 LLM 降级为机械拍发并标注）
4. 通信检定 → 到达延迟与完整性（COMPLETE/PARTIAL/GARBLED/LOST）
5. process_intel（管线步骤）：到达 → 旗舰收报 → 通信官登记路由 →
   证据登记 → 工作项入队
6. run_intelligence_cycle：情报参谋（工作项驱动）→ JUDGMENT_CHECK →
   JudgmentPolicy + 分析器 → NPCAssessment + NPCClaim + IntelBrief

纪律：
- 未送达电文内容不进任何玩家视图（D1）；LOST 永不送达。
- 所有检定走 RNGService 并落 CheckRecord（D10）。
- 判断必须由工作项 + 参谋策略/分析器产生（D12/D15）。
"""
import logging
from datetime import timedelta
from typing import Optional

from src.intel.contracts import (
    ActorRole,
    ApprovalStatus,
    CheckType,
    CommCondition,
    ContactStatus,
    MessageStatus,
    SourceType,
    WorkItemStatus,
    WorkPriority,
    approval_transitions,
    require_transition,
    work_item_transitions,
)
from src.intel.models import (
    IntelBrief,
    IntelWorkItem,
    MessageEnvelope,
    NPCAssessment,
    SourceObservation,
)
from src.intel.policy import (
    DEFAULT_ACTOR,
    DEFAULT_POLICY,
    roll_judgment_dice,
)
from src.intel.rng import RNGService
from src.intel import service as intel
from src.npc_config import NPC_REGISTRY, UNIT_REGISTRY
from src.scouting import compute_report_delay, distort_bearing, distort_count, distort_distance

logger = logging.getLogger("midway.intel.flow")

# 观察质量带 → 失真参数（quality_band: (bearing_err, dist_pct, identity_precision)）
_QUALITY_BANDS = {
    "high": (2, 0.05, 0.9),
    "standard": (5, 0.10, 0.7),
    "low": (8, 0.15, 0.4),
}


def _default_writer():
    """报告 NPC；无 API key 时返回 None（降级为机械拍发）。"""
    try:
        from src.agents.pilot import PilotReportNPC
        return PilotReportNPC()
    except Exception:
        return None


def _default_analyst():
    try:
        from src.agents.intel_analyst import IntelOfficerAnalyst
        return IntelOfficerAnalyst()
    except Exception:
        return None


# ── 步骤 4-9：探测成功 → 观测 → 报告 → 拍发 ──

def on_scout_detection(state, *, scout, enemy, bearing: float, distance: float,
                       result, writer=None, rng=None) -> MessageEnvelope:
    """探测检定成功后调用：产生观测、撰写电文、拍发进通信链。

    返回 FILED→IN_TRANSIT 的电文（内容此后对玩家不可见，直到到达）。
    rng 参数供测试注入脚本化随机源；缺省用 state 绑定的 RNGService。
    """
    rng = rng or RNGService(state)
    unit = UNIT_REGISTRY["sbd_scout_section"]

    # 观察质量检定（决定失真带与识别精度）
    quality, q_rec = rng.roll_check(
        check_type=CheckType.OBSERVATION_QUALITY_CHECK,
        actor_id=unit.name,
        npc_modifier=unit.competence * 2,
        situational_mods={"距离因子": -5 if distance > 150 else 5},
        reason=f"{scout.id} 观察质量检定",
        inputs={"distance_nm": round(distance, 1)},
    )
    if quality.is_critical():
        band = "high"
    elif quality.is_success():
        band = "standard"
    else:
        band = "low"
    bearing_err, dist_pct, ident = _QUALITY_BANDS[band]

    # 规则侧观测（真值入档，永不外发）
    obs = SourceObservation(
        id=intel.next_id(state, "OBS"),
        source_id=scout.id,
        source_type=SourceType.CARRIER_SCOUT,
        observer_actor_id=unit.name,
        observed_at=state.clock.game_time,
        bearing_true=bearing,
        distance_nm_true=distance,
        target_name_true=enemy.get("name", "unknown"),
        carrier_count_true=len(enemy.get("carriers", [])),
        quality_band=band,
        quality_check_id=q_rec.check_id,
        internal_truth_ref=enemy.get("name", "unknown"),
    )
    state.observations.append(obs)

    # 失真后的报告值（NPC 只见这些）
    reported_bearing = distort_bearing(bearing, max_error=bearing_err, rng=rng)
    reported_distance = distort_distance(distance, max_error_pct=dist_pct, rng=rng)
    reported_count = real_count = len(enemy.get("carriers", []))
    if band != "high":
        reported_count = distort_count(real_count, undercount_prob=0.4, rng=rng)
    classification = "CV" if band != "low" else "大型船只（未识别）"
    if band == "low" and ident < 0.5:
        classification = "大型船只（未识别）"

    view = {
        "bearing": int(reported_bearing),
        "distance_nm": int(reported_distance),
        "count": reported_count,
        "quality": band,
        "classification": classification,
    }

    # 报告 NPC 撰写（D16）；无 LLM 降级为机械拍发（显式标注，非玩法路径）
    generated_by = None
    if writer is None:
        writer = _default_writer()
    if writer is not None:
        try:
            raw_text = writer.write_report(
                view, game_time=state.clock.game_time.strftime("%H:%M")
            )
            generated_by = getattr(writer, "actor_id", "pilot")
        except Exception as e:
            logger.warning("pilot writer failed (%s); fallback to mechanical", e)
            writer = None
    if writer is None:
        raw_text = (
            f"{scout.id} REPORT: {classification} {reported_count} "
            f"BEARING {int(reported_bearing)} DEG DIST {int(reported_distance)} NM "
            f"({band.upper()} IDENT)"
        )

    priority = WorkPriority.URGENT if real_count >= 2 else WorkPriority.ROUTINE
    msg = MessageEnvelope(
        sender_id=getattr(writer, "actor_id", scout.id) if writer else scout.id,
        sender_call_sign=scout.id,
        recipient_ids=["TF16 FLAG"],
        priority=priority,
        message_kind="scout_report",
        observed_at=obs.observed_at,
        raw_text=raw_text,
        fields=dict(view),
        generated_by_npc=generated_by,
        observation_id=obs.id,
    )
    intel.file_message(state, msg, by=msg.sender_id, reason="侦察接触报告拍发")
    intel.mark_in_transit(state, msg, by="TBS 通信链", reason="报告发往旗舰")

    # 通信检定（延迟 + 完整性；全部落记录）
    comm, c_rec = rng.communication_check(
        actor_id=f"{scout.id} 电台",
        competence=unit.competence,
        distance_nm=distance,
        reason=f"{scout.id} 通信检定",
        inputs={"priority": priority.value, "quality_check": q_rec.check_id},
    )
    delay = compute_report_delay(distance, rng=rng)
    eta = state.clock.game_time + timedelta(minutes=delay)
    msg.transit_eta = eta

    if comm.raw_roll <= 3:
        # 传输完全丢失：内容永不到达（D1 防泄漏的通信侧）
        intel.lose_message(state, msg, by="TBS 通信链",
                           reason="通信检定大失败——电文丢失")
        return msg

    if comm.level == "critical_failure":
        msg.condition = CommCondition.GARBLED
    elif comm.level == "partial":
        msg.condition = CommCondition.PARTIAL
    else:
        msg.condition = CommCondition.COMPLETE

    logger.info("[INTEL] %s filed, eta %s, cond=%s (comm=%s)",
                msg.id, eta.strftime("%H:%M"), msg.condition.value, comm)
    return msg


# ── 步骤 10-12：到达 → 收报 → 登记路由 → 工作项 ──

def process_intel(state, minutes: int = 15) -> list[str]:
    """管线步骤：传输中电文到达处理（替代旧 check_pending_reports 管线职责）。"""
    notes = []
    now = state.clock.game_time
    for msg in list(state.messages):
        if msg.status != MessageStatus.IN_TRANSIT:
            continue
        if msg.transit_eta is None or now < msg.transit_eta:
            continue
        if msg.condition == CommCondition.UNREADABLE or msg.status == MessageStatus.LOST:
            continue
        try:
            notes.extend(_receive_report(state, msg))
        except ValueError as e:
            logger.error("[INTEL] receive failed for %s: %s", msg.id, e)
    return notes


def _receive_report(state, msg: MessageEnvelope) -> list[str]:
    notes = []
    # S2.5：勘误电报到达 → 专用处理（旧电文 CORRECTED/旧证据替代/纠错工作项）
    if msg.message_kind == "correction":
        from src.intel.conflicts import apply_correction_on_arrival
        apply_correction_on_arrival(state, msg)
        notes.append(f"📡 勘误电报 {msg.id} 到达（更正 {msg.supersedes_message_id}），已转情报参谋")
        return notes
    intel.receive_message(state, msg, by="TF16 通信室", condition=msg.condition)
    # 通信官登记并路由（D3：通信官只登记转递，不分析）
    intel.log_message(state, msg, by="radio_officer")
    intel.route_message(state, msg, by="radio_officer", route_to="intel_officer")

    obs = _observation_by_id(state, msg.observation_id)
    # S2.6：来源类型随电文（传感器/友军转述走同一证据协议，来源差异可感知）
    sensor = msg.fields.get("sensor", "")
    valid_sensors = {s.value for s in SourceType}
    source_type = SourceType(sensor) if sensor in valid_sensors else SourceType.CARRIER_SCOUT
    base_reliability = 0.8 if msg.condition == CommCondition.COMPLETE else 0.5
    if msg.relay_chain:
        # 转述有损：每级转述折减（保留原发送者与转述链）
        from src.intel.sources import RELAY_RELIABILITY_FACTOR
        base_reliability *= RELAY_RELIABILITY_FACTOR ** len(msg.relay_chain)
    precision = {"high": 0.9, "standard": 0.7, "low": 0.4}.get(
        obs.quality_band if obs else "standard", 0.7)
    # 通信残缺降低识别精度（能区分通信损坏与参谋误判）
    if msg.condition == CommCondition.GARBLED:
        precision = max(0.1, precision - 0.3)
    reported = _reported_from_message(msg, obs)
    # 证据位置 = 报告要素推算的失真位置（与玩家所见一致，非真值）
    position = None
    if reported.get("bearing") is not None and reported.get("distance_nm"):
        from src.scouting import _bearing_distance_to_position
        from src.state import Position
        tf = state.task_forces[0]
        fleet_pos = (tf.carriers[0].position.lat, tf.carriers[0].position.lon)
        position = _bearing_distance_to_position(
            fleet_pos, float(reported["bearing"]), float(reported["distance_nm"]))
    ev = intel.register_evidence(
        state,
        message=msg,
        source_id=msg.origin_sender or msg.sender_call_sign or msg.sender_id,
        source_type=source_type,
        access_roles=[ActorRole.INTEL_OFFICER, ActorRole.CHIEF_OF_STAFF],
        summary=f"{msg.origin_sender or msg.sender_call_sign}: {msg.raw_text}",
        position=position,
        reported=reported,
        observed_at=msg.observed_at,
        source_reliability=base_reliability,
        identity_precision=precision,
        position_precision=precision,
        count_precision=precision,
    )
    item = create_work_item(
        state, message=msg, evidence=ev,
        priority=msg.priority,
    )
    # 兼容层：迁移期把到达报告写进 legacy known_enemy（S2.4 起由 ApprovedPlot 接管）
    _write_legacy_known_enemy(state, msg, obs)
    notes.append(
        f"📡 {msg.sender_call_sign} 报告到达（{msg.condition.value}），"
        f"已登记为 {ev.id} 并转情报参谋（{item.id}）"
    )
    logger.info("[INTEL] received %s -> %s (%s)", msg.id, ev.id, item.id)
    return notes


def _observation_by_id(state, obs_id):
    if not obs_id:
        return None
    for o in state.observations:
        if o.id == obs_id:
            return o
    return None


def _reported_from_message(msg, obs) -> dict:
    """电文可见值（失真后的报告要素，非真值）。"""
    if msg.fields:
        return {
            "bearing": msg.fields.get("bearing"),
            "distance_nm": msg.fields.get("distance_nm"),
            "count": msg.fields.get("count"),
            "classification": msg.fields.get("classification", ""),
            "source_quality": msg.fields.get("quality", ""),
        }
    if obs:  # 旧电文无要素字段时退回观测（不含真值引用）
        return {"bearing": int(obs.bearing_true), "distance_nm": int(obs.distance_nm_true),
                "count": obs.carrier_count_true}
    return {"raw": msg.raw_text}


def _write_legacy_known_enemy(state, msg, obs) -> None:
    """迁移期兼容：S2.4 起 known_enemy 由 ApprovedPlot 派生，本写入退役。"""
    from src.scouting import _bearing_distance_to_position
    from src.state import EnemyKnown
    if not obs or not msg.fields:
        return
    tf = state.task_forces[0]
    fleet_pos = (tf.carriers[0].position.lat, tf.carriers[0].position.lon)
    bearing = float(msg.fields.get("bearing", obs.bearing_true))
    dist = float(msg.fields.get("distance_nm", obs.distance_nm_true))
    enemy_pos = _bearing_distance_to_position(fleet_pos, bearing, dist)
    state.known_enemy.append(EnemyKnown(
        position=enemy_pos,
        description=(
            f"{msg.sender_call_sign}: 敌航母约 {msg.fields.get('count', '?')} 艘"
            f" - 方位 {int(bearing)}° - 距离约 {int(dist)} 海里"
        ),
        confidence="high" if obs.quality_band == "high" else "medium",
        source=msg.sender_call_sign or msg.sender_id,
        reported_at=msg.received_at or state.clock.game_time,
    ))


# ── 工作队列 ──

_PRIORITY_ORDER = {
    WorkPriority.FLASH: 0, WorkPriority.URGENT: 1,
    WorkPriority.CORRECTION: 2, WorkPriority.ROUTINE: 3,
}
_OPEN_ITEM_STATUSES = frozenset({
    WorkItemStatus.QUEUED, WorkItemStatus.ASSIGNED,
    WorkItemStatus.IN_PROGRESS, WorkItemStatus.WAITING_FOR_EVIDENCE,
})


def create_work_item(state, *, message: MessageEnvelope, evidence,
                     priority: WorkPriority = WorkPriority.ROUTINE,
                     assigned_to: str = "intel_officer") -> IntelWorkItem:
    item = IntelWorkItem(
        id=intel.next_id(state, "WU"),
        priority=priority,
        status=WorkItemStatus.QUEUED.value,
        trigger_message_id=message.id,
        evidence_ids=[evidence.id],
        assigned_to=assigned_to,
        created_by="radio_officer",
        created_at=state.clock.game_time,
    )
    state.intel_work_items.append(item)
    intel._audit(state, actor_id="radio_officer", action="work_item_create",
                 target_id=item.id, reason="收报转递",
                 evidence_ids=[evidence.id])
    # QUEUED → ASSIGNED（自动分配给情报参谋；处理仍需参谋实际工作）
    item.status = WorkItemStatus.ASSIGNED.value
    return item


def intel_work_queue(state) -> list[IntelWorkItem]:
    """开放工作项按优先级排序（FLASH 打断例行）。"""
    open_items = [i for i in state.intel_work_items
                  if i.status in _OPEN_ITEM_STATUSES]
    return sorted(
        open_items,
        key=lambda i: (_PRIORITY_ORDER.get(i.priority, 9), i.created_at or now_min(state)),
    )


def now_min(state):
    return state.clock.game_time


# ── 步骤 13-15：参谋研判 → 判断书 → 简报 ──

def run_intelligence_cycle(state, item: IntelWorkItem, *,
                           policy=None, analyst=None, rng: Optional[RNGService] = None,
                           actor_profile=None) -> IntelBrief:
    """情报参谋处理工作项：研判 → NPCAssessment + NPCClaim → IntelBrief。

    判断必须由本调用产生（有工作项、有骰子记录、有策略产物）；
    系统不会在无人调用时静默生成判断（D12/D15）。
    """
    require_transition(
        work_item_transitions(),
        WorkItemStatus(item.status), WorkItemStatus.IN_PROGRESS,
    )
    item.status = WorkItemStatus.IN_PROGRESS.value
    rng = rng or RNGService(state)
    policy = policy or DEFAULT_POLICY
    actor = actor_profile or DEFAULT_ACTOR
    officer = NPC_REGISTRY["intel_officer"]

    # 权限内证据视图
    views = []
    for ev in intel.visible_evidence(state, ActorRole.INTEL_OFFICER):
        if ev.id in item.evidence_ids:
            views.append(intel.evidence_view(ev, ActorRole.INTEL_OFFICER))

    # JUDGMENT_CHECK（骰子出偏差，参谋演绎——D10）
    situational = {}
    if len(views) <= 1:
        situational["单一来源"] = -5
    if any((v.dimensions.get("identity_precision", 1) < 0.5) for v in views):
        situational["低精度证据"] = -5
    result, j_rec = rng.roll_check(
        check_type=CheckType.JUDGMENT_CHECK,
        actor_id=actor.actor_id,
        npc_modifier=officer.competence * 2,
        situational_mods=situational,
        reason=f"{item.id} 情报研判",
        inputs={"evidence": [v.evidence_id for v in views]},
    )
    dice = roll_judgment_dice(rng, actor_id=actor.actor_id,
                              level=result.level, record_id=j_rec.check_id)

    # S2.5：证据冲突登记（参谋全部可见证据 + 既有接触链；只登记呈报，不裁决）
    conflict_ids: list[str] = []
    unresolved: list[str] = []
    from src.intel.conflicts import age_contacts, detect_conflicts
    evidence_scope = [e.id for e in intel.visible_evidence(
        state, ActorRole.INTEL_OFFICER)]
    for c in state.contacts:
        if c.actor_id == actor.actor_id:
            evidence_scope.extend(c.evidence_ids)
    conflicts_found = detect_conflicts(
        state, evidence_scope, by=actor.actor_id,
        role=ActorRole.INTEL_OFFICER,
    ) if len(evidence_scope) > 1 else []
    conflict_ids = [c.id for c in conflicts_found]
    aged = age_contacts(state, by=actor.actor_id)

    # 策略形成结构化判断（S3 接口；S2 内置机械实现/注入 LLM 分析器）
    draft = policy.assess(item, views, actor, dice)
    narrative = draft.notes
    if analyst is None:
        analyst = _default_analyst()
    if analyst is not None:
        try:
            payload = analyst.analyze(item, views, dice, actor.model_dump())
            narrative = payload.get("narrative", narrative)
        except Exception as e:
            logger.warning("analyst failed (%s); using policy draft notes", e)

    # 判断书落档（含审计链）
    assessment = NPCAssessment(
        id=intel.next_id(state, "AS"),
        author_actor_id=actor.actor_id,
        work_item_id=item.id,
        created_at=state.clock.game_time,
        based_on_evidence_ids=[v.evidence_id for v in views],
        facts_used=[v.summary for v in views],
        alternative_hypotheses=draft.alternative_hypotheses,
        confidence_dimensions=draft.confidence_dimensions,
        change_my_mind=draft.change_my_mind,
        recommended_action=draft.recommended_action,
        dice_record_ids=[j_rec.check_id, dice.record_id],
        conflict_ids=conflict_ids,
        narrative=narrative,
    )
    state.assessments.append(assessment)

    for claim in draft.claims:
        c = intel.record_claim(
            state,
            assessment_id=assessment.id,
            actor_id=actor.actor_id,
            claim_type=claim.get("claim_type", "judgment"),
            text=claim.get("text") or claim.get("summary", ""),
            based_on_evidence_ids=[claim.get("source_evidence_id", "")]
            if claim.get("source_evidence_id") else [],
            tool_call_ids=[dice.record_id],
            confidence_dimensions=assessment.confidence_dimensions,
        )
        assessment.claims.append(c.id)

    # 接触假设：参谋信念内建 TENTATIVE 接触（上图需指挥官批准，S2.4）
    contact_id = None
    if views:
        belief = intel.belief_for(state, actor.actor_id)
        ev0 = next(e for e in state.evidence if e.id == views[0].evidence_id)
        contact = intel.add_contact(
            state, belief,
            classification="CV" if views[0].dimensions.get("identity_precision", 0) >= 0.5 else "unknown",
            position=ev0,
            evidence_ids=[ev0.id],
            first_seen_at=ev0.observed_at or state.clock.game_time,
            last_seen_at=state.clock.game_time,
            by=actor.actor_id,
            reason=f"研判 {assessment.id}",
            status=ContactStatus.TENTATIVE,
            confidence_dimensions=assessment.confidence_dimensions,
            created_from_assessment_id=assessment.id,
        )
        contact_id = contact.id
        assessment.contact_id = contact_id

    # 简报（第一版：紧急单报；ROUTINE 留待批次合并）
    require_transition(approval_transitions(), ApprovalStatus.DRAFT,
                       ApprovalStatus.PROPOSED)
    brief = IntelBrief(
        id=intel.next_id(state, "BRF"),
        author_actor_id=actor.actor_id,
        created_at=state.clock.game_time,
        briefed_at=state.clock.game_time,
        priority=item.priority,
        new_evidence_ids=list(item.evidence_ids),
        changed_judgments=[assessment.id],
        unresolved_questions=[],
        status=ApprovalStatus.PROPOSED.value,
        narrative=narrative,
    )
    state.intel_briefs.append(brief)

    # 参谋主动更新建议（S2.5）：冲突/衰老显式写入简报未决问题
    for c in conflicts_found:
        brief.unresolved_questions.append(f"证据冲突 {c.id}：{c.note}")
    for cid in aged:
        brief.unresolved_questions.append(f"接触 {cid} 已陈旧/失联，需新证据确认")
    if conflicts_found and draft.recommended_action:
        assessment.recommended_action = (
            f"{draft.recommended_action}（注意：存在 {len(conflicts_found)} 处证据冲突，"
            "建议派第二来源印证）")

    # 简报产生标图提案（§7.1 步骤16；几何来自接触/证据，作者=情报参谋）
    if contact_id:
        from src.intel.plots import create_plot_proposal, latest_revision_base
        contact_obj = next(c for c in state.contacts if c.id == contact_id)
        base = latest_revision_base(state)
        if base is not None:
            # §7.2：新证据到达 → 形成同链新版修订提案（须重新审批，不静默上图）
            proposal = create_plot_proposal(
                state,
                author_actor_id=actor.actor_id,
                assessment=assessment,
                contact=contact_obj,
                change_summary=f"依据新证据修订 v{base.version} 标图",
                supersedes=base,
            )
        else:
            proposal = create_plot_proposal(
                state,
                author_actor_id=actor.actor_id,
                assessment=assessment,
                contact=contact_obj,
                change_summary="初版接触标图（依据最新研判）",
            )
        brief.plot_proposal_ids.append(proposal.id)

    item.status = WorkItemStatus.SUBMITTED.value
    item.submitted_at = state.clock.game_time
    item.outcome_assessment_id = assessment.id
    intel._audit(state, actor_id=actor.actor_id, action="assessment",
                 target_id=assessment.id, reason="研判提交",
                 evidence_ids=list(item.evidence_ids),
                 details={"brief": brief.id, "dice": j_rec.check_id})
    logger.info("[INTEL] cycle %s -> %s (%s)", item.id, assessment.id, brief.id)
    return brief
