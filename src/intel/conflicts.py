"""S2.5 冲突、陈旧与勘误（§M2.5/§7.2/§7.3/§7.4）。

纪律：
- 多份矛盾报告并存（D9）：冲突只登记与呈报，不静默合并/裁决。
- 接触衰老/失联/重新接触由参谋显式执行并审计。
- 勘误到达才改旧电文状态；原电文与新证据全部保留。
- 误报否定是指挥官决议：参谋只能提案（§7.4）。
"""
import math
from datetime import datetime, timedelta
from typing import Optional

from src.intel.contracts import (
    ActorRole,
    ApprovalStatus,
    ContactStatus,
    EvidenceStatus,
    MessageStatus,
    SourceType,
    WorkPriority,
    approval_transitions,
    evidence_transitions,
    message_transitions,
    require_transition,
)
from src.intel import service as intel
from src.intel import plots as plotsvc
from src.intel.models import (
    CommanderDecision,
    EvidenceConflict,
    MessageEnvelope,
    StatusChange,
)

# 冲突判定阈值（S2 常量；S3 校准时可调）
BEARING_CONFLICT_DEG = 30.0
DISTANCE_CONFLICT_NM = 60.0
COUNT_CONFLICT_DELTA = 2


# ── 多证据冲突 ──

def detect_conflicts(state, evidence_ids: list[str], *, by: str,
                     role: ActorRole = ActorRole.INTEL_OFFICER) -> list[EvidenceConflict]:
    """成对检测证据冲突（方位/距离/数量），登记为冲突记录——不裁决。

    只比较当前角色权限内的证据；已登记过的证据对不重复登记。
    """
    evs = [e for e in state.evidence
           if e.id in evidence_ids and e.status == EvidenceStatus.ACTIVE
           and role in e.access_policy]
    seen_pairs = {frozenset(c.evidence_ids) for c in state.evidence_conflicts}
    conflicts = []
    for i in range(len(evs)):
        for j in range(i + 1, len(evs)):
            a, b = evs[i], evs[j]
            pair = frozenset((a.id, b.id))
            if pair in seen_pairs:
                continue
            kind, severity, note = _compare(a, b)
            if kind is None:
                continue
            conflict = EvidenceConflict(
                id=intel.next_id(state, "CFL"),
                at=intel.now(state),
                kind=kind,
                evidence_ids=[a.id, b.id],
                severity=severity,
                note=note,
                status="open",
            )
            state.evidence_conflicts.append(conflict)
            intel._audit(state, actor_id=by, action="conflict_detect",
                         target_id=conflict.id, reason=note,
                         evidence_ids=[a.id, b.id])
            # S4 确定性触发：冲突登记 → 作战参谋 RISK_WARNING 提醒
            from src.staff.roster import get_active_roster
            from src.staff import hooks as staff_hooks
            _s4_roster = get_active_roster()
            if _s4_roster is not None:
                staff_hooks.on_conflict_open(state, _s4_roster, conflict)
            conflicts.append(conflict)
    return conflicts


def _compare(a, b):
    """比较两条证据，返回 (kind, severity, note) 或 (None, 0, '')。"""
    if a.lat is not None and b.lat is not None:
        dist = math.hypot(
            (a.lat - b.lat) * 60.0,
            ((a.lon - b.lon) * 60.0 * math.cos(math.radians(a.lat))),
        )
        if dist > DISTANCE_CONFLICT_NM:
            return ("position", min(1.0, dist / 200.0),
                    f"位置差 {dist:.0f} 海里（{a.source_id} vs {b.source_id}）")
    ra, rb = a.reported or {}, b.reported or {}
    if ra.get("bearing") is not None and rb.get("bearing") is not None:
        d = abs((ra["bearing"] - rb["bearing"] + 180) % 360 - 180)
        if d > BEARING_CONFLICT_DEG:
            return ("bearing", min(1.0, d / 90.0),
                    f"方位差 {d:.0f}°（{a.source_id} vs {b.source_id}）")
    if ra.get("count") is not None and rb.get("count") is not None:
        if abs(ra["count"] - rb["count"]) >= COUNT_CONFLICT_DELTA:
            return ("count", 0.5,
                    f"数量差 {abs(ra['count'] - rb['count'])}（{a.source_id} vs {b.source_id}）")
    return (None, 0.0, "")


def resolve_conflict(state, conflict: EvidenceConflict, *, by: str,
                     resolution_evidence_id: str, note: str) -> None:
    """冲突裁决（参谋显式动作；记录采信哪条证据）。"""
    conflict.status = "resolved"
    conflict.resolved_by_evidence_id = resolution_evidence_id
    conflict.note = f"{conflict.note}；裁决：{note}"
    intel._audit(state, actor_id=by, action="conflict_resolve",
                 target_id=conflict.id, reason=note,
                 evidence_ids=[resolution_evidence_id])


def corroborate(state, evidence_a, evidence_b, *, by: str, note: str) -> None:
    """相互印证（追加到双方 corroboration；不合并、不修改原字段）。"""
    if evidence_b.id not in evidence_a.corroboration:
        evidence_a.corroboration.append(evidence_b.id)
    if evidence_a.id not in evidence_b.corroboration:
        evidence_b.corroboration.append(evidence_a.id)
    intel._audit(state, actor_id=by, action="corroborate",
                 target_id=f"{evidence_a.id}+{evidence_b.id}", reason=note,
                 evidence_ids=[evidence_a.id, evidence_b.id])


# ── 接触衰老 / 失联 / 重新接触 ──

def age_contacts(state, *, by: str, stale_after_min: float = 90.0,
                 lost_after_min: float = 240.0,
                 belief=None) -> list[str]:
    """参谋态势整理：显式衰老/失联（有审计；绝不静默）。

    只作用于该参谋（belief.actor_id）名下的接触。
    """
    from src.intel.models import BeliefState
    if belief is None:
        belief = intel.belief_for(state, by)
    changed = []
    now = intel.now(state)
    for contact in intel.contacts_of(state, belief):
        last = contact.last_seen_at
        if last is None:
            continue
        age_min = (now - last).total_seconds() / 60.0
        try:
            if age_min >= lost_after_min and contact.status in (
                    ContactStatus.STALE, ContactStatus.TENTATIVE, ContactStatus.PLOTTED):
                intel.transition_contact(state, contact,
                                         to_status=ContactStatus.LOST,
                                         by=by, reason=f"失联 {age_min:.0f} 分钟",
                                         evidence_ids=contact.evidence_ids)
                changed.append(contact.id)
            elif age_min >= stale_after_min and contact.status in (
                    ContactStatus.TENTATIVE, ContactStatus.PLOTTED):
                intel.transition_contact(state, contact,
                                         to_status=ContactStatus.STALE,
                                         by=by, reason=f"陈旧 {age_min:.0f} 分钟",
                                         evidence_ids=contact.evidence_ids)
                changed.append(contact.id)
        except ValueError:
            continue  # 非法转换（如已 REJECTED）跳过
    return changed


def reactivate_contact(state, contact, *, by: str, note: str) -> None:
    """重新接触（STALE/LOST → TENTATIVE；参谋显式动作）。"""
    intel.transition_contact(state, contact, to_status=ContactStatus.TENTATIVE,
                             by=by, reason=note,
                             evidence_ids=contact.evidence_ids)


# ── 勘误到达处理 ──

def apply_correction_on_arrival(state, correction: MessageEnvelope) -> list:
    """勘误电报到达（§7.3）：旧电文→CORRECTED、旧证据→SUPERSEDED、
    新证据登记、CORRECTION 工作项入队。全部追加、可复盘。
    """
    out = []
    intel.receive_message(state, correction, by="TF16 通信室",
                          condition=correction.condition)
    intel.log_message(state, correction, by="radio_officer")
    intel.route_message(state, correction, by="radio_officer",
                        route_to="intel_officer")

    old_msg_id = correction.supersedes_message_id
    old_msg = next((m for m in state.messages if m.id == old_msg_id), None)
    if old_msg is not None and old_msg.status not in (
            MessageStatus.CORRECTED, MessageStatus.LOST):
        require_transition(message_transitions(), old_msg.status,
                           MessageStatus.CORRECTED)
        old_msg.status_history.append(StatusChange(
            at=intel.now(state), from_status=old_msg.status.value,
            to_status=MessageStatus.CORRECTED.value,
            by=f"勘误 {correction.id}", reason="被勘误电报更正",
        ))
        old_msg.status = MessageStatus.CORRECTED

    # 旧证据替代（不可变账本：旧记录保留只翻状态）
    old_ev = next((e for e in state.evidence if e.message_id == old_msg_id
                   and e.status == EvidenceStatus.ACTIVE), None)
    # 证据位置 = 勘误报告要素推算的失真位置（与玩家所见一致）
    position = None
    fields = correction.fields or {}
    if fields.get("bearing") is not None and fields.get("distance_nm"):
        from src.scouting import _bearing_distance_to_position
        tf = state.task_forces[0]
        fleet_pos = (tf.carriers[0].position.lat, tf.carriers[0].position.lon)
        position = _bearing_distance_to_position(
            fleet_pos, float(fields["bearing"]), float(fields["distance_nm"]))
    precision = {"high": 0.9, "standard": 0.7, "low": 0.4}.get(
        str(fields.get("quality", "")), 0.5)
    new_ev = intel.register_evidence(
        state,
        message=correction,
        source_id=correction.sender_call_sign or correction.sender_id,
        source_type=old_ev.source_type if old_ev else SourceType.CARRIER_SCOUT,
        access_roles=[ActorRole.INTEL_OFFICER, ActorRole.CHIEF_OF_STAFF],
        summary=f"[勘误] {correction.raw_text}",
        position=position,
        reported=dict(fields),
        observed_at=correction.observed_at,
        source_reliability=(old_ev.source_reliability if old_ev else 0.6),
        # S3.7 修复：勘误电文的质量带同样决定识别/位置/数量精度
        # （与 flow._receive_report 的 quality 映射一致）
        identity_precision=precision,
        position_precision=precision,
        count_precision=precision,
    )
    if old_ev is not None:
        new_ev.supersedes_evidence_id = old_ev.id
        require_transition(evidence_transitions(), old_ev.status,
                           EvidenceStatus.SUPERSEDED)
        old_ev.status = EvidenceStatus.SUPERSEDED

    item = intel_next_work_item(state, correction, new_ev)
    intel._audit(state, actor_id="radio_officer", action="correction_apply",
                 target_id=correction.id,
                 reason=f"勘误替代 {old_msg_id}",
                 evidence_ids=[e.id for e in (old_ev, new_ev) if e])
    out.append(new_ev)
    out.append(item)
    return out


def intel_next_work_item(state, message, evidence,
                         priority: WorkPriority = WorkPriority.CORRECTION):
    """工作项创建（CORRECTION 优先级）。"""
    from src.intel.flow import create_work_item
    return create_work_item(state, message=message, evidence=evidence,
                            priority=priority)


# ── 误报否定（§7.4：参谋提案 + 指挥官批准）──

def propose_contact_rejection(state, contact, *, by: str, reason: str,
                              evidence=None):
    """参谋提出误报否定建议 → REJECTION 提案（method=rejection，PROPOSED）。

    挂接该接触既有标图链（supersedes 最新版本）——批准后同链正式标图撤下。
    """
    chain = [p for p in state.plot_proposals if p.contact_id == contact.id]
    supersedes = max(chain, key=lambda p: p.version) if chain else None
    proposal = plotsvc.create_plot_proposal(
        state,
        author_actor_id=by,
        contact=contact,
        evidence=evidence,
        change_summary=f"建议判定误报并撤下图标：{reason}",
        method="rejection",
        assumptions=[f"否定理由：{reason}"],
        supersedes=supersedes,
    )
    proposal.based_on_evidence_ids = list(contact.evidence_ids)
    intel._audit(state, actor_id=by, action="rejection_propose",
                 target_id=contact.id, reason=reason,
                 details={"proposal": proposal.id})
    return proposal


def apply_rejection_approval(state, proposal, decision: CommanderDecision) -> None:
    """指挥官批准误报否定：接触→REJECTED、正式标图撤下（superseded）、
    证据→REJECTED。原版本与理由全部保留（§7.4）。"""
    from src.intel.models import ApprovedPlot
    contact = plotsvc._contact_by_id(state, proposal.contact_id) \
        if proposal.contact_id else None
    if contact is not None:
        intel.transition_contact(
            state, contact, to_status=ContactStatus.REJECTED,
            by="player", reason=f"批准误报否定 {proposal.id}",
            evidence_ids=proposal.based_on_evidence_ids,
            approved=True, decision_id=decision.id,
        )
    # 正式标图撤下（保留历史）
    for plot in state.approved_plots:
        if plot.plot_id == proposal.plot_id and plot.state == "active":
            plot.state = "superseded"
    # 关联证据否定
    for ev in state.evidence:
        if ev.id in proposal.based_on_evidence_ids and ev.status == EvidenceStatus.ACTIVE:
            intel.reject_evidence(state, ev, by="player",
                                  reason=f"误报否定 {proposal.id}")
