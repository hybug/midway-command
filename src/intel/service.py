"""S2 情报服务层（Phase S2.2）。

所有情报域状态转换经过本层（权限控制与纪律守卫发生在状态转换层，
不依赖 prompt 提醒——计划 §八）。原始记录一律追加、不覆盖。
"""
from datetime import datetime
from typing import Optional

from src.intel.contracts import (
    ActorRole,
    CommCondition,
    ContactStatus,
    EvidenceStatus,
    MessageStatus,
    SourceType,
    WorkPriority,
    approval_transitions,
    contact_transitions,
    evidence_transitions,
    message_transitions,
    require_transition,
)
from src.intel.judgment import EvidenceView
from src.intel.models import (
    BeliefState,
    ContactHypothesis,
    Evidence,
    IntelAuditEntry,
    MessageEnvelope,
    NPCClaim,
    StatusChange,
)

_PLAYER_READABLE_MESSAGE_STATUSES = frozenset({
    MessageStatus.RECEIVED, MessageStatus.LOGGED, MessageStatus.ROUTED,
    MessageStatus.PROCESSED, MessageStatus.ARCHIVED, MessageStatus.CORRECTED,
})


# ── ID 与时间 ──

def now(state) -> datetime:
    return state.clock.game_time


def next_id(state, prefix: str) -> str:
    """域内顺序 id（MSG/EV/CT/CL/WU/BR/AS/BRF/PP/AP…）。"""
    n = state.intel_id_counters.get(prefix, 0) + 1
    state.intel_id_counters[prefix] = n
    return f"{prefix}-{n:06d}"


def _audit(state, *, actor_id: str, action: str, target_id: str = "",
           reason: str = "", evidence_ids: Optional[list[str]] = None,
           details: Optional[dict] = None) -> IntelAuditEntry:
    entry = IntelAuditEntry(
        id=next_id(state, "AUD"),
        at=now(state),
        actor_id=actor_id,
        action=action,
        target_id=target_id,
        reason=reason,
        evidence_ids=evidence_ids or [],
        details=details or {},
    )
    state.intel_audit.append(entry)
    return entry


# ── 消息：状态机推进（追加式）──

def _transition_message(state, msg: MessageEnvelope, to_status: MessageStatus,
                        by: str, reason: str = "") -> None:
    require_transition(message_transitions(), msg.status, to_status)
    msg.status_history.append(StatusChange(
        at=now(state), from_status=msg.status.value,
        to_status=to_status.value, by=by, reason=reason,
    ))
    msg.status = to_status


def file_message(state, envelope: MessageEnvelope, by: str,
                 reason: str = "电文拍发") -> MessageEnvelope:
    """起草电文落档（DRAFT → FILED）。落档后 raw_text 不可覆盖。"""
    envelope.id = next_id(state, "MSG")
    if envelope.filed_at is None:
        envelope.filed_at = now(state)
    state.messages.append(envelope)
    _transition_message(state, envelope, MessageStatus.FILED, by, reason)
    return envelope


def mark_in_transit(state, msg: MessageEnvelope, by: str,
                    reason: str = "进入通信链") -> None:
    _transition_message(state, msg, MessageStatus.IN_TRANSIT, by, reason)


def receive_message(state, msg: MessageEnvelope, by: str,
                    condition: CommCondition = CommCondition.COMPLETE,
                    received_at: Optional[datetime] = None) -> None:
    """旗舰收报（IN_TRANSIT → RECEIVED）。玩家可读起点。"""
    _transition_message(state, msg, MessageStatus.RECEIVED, by, "旗舰收报")
    msg.received_at = received_at or now(state)
    msg.condition = condition


def log_message(state, msg: MessageEnvelope, by: str,
                reason: str = "收报室登记") -> None:
    _transition_message(state, msg, MessageStatus.LOGGED, by, reason)


def route_message(state, msg: MessageEnvelope, by: str,
                  route_to: str | list[str],
                  reason: str = "分发参谋") -> None:
    _transition_message(state, msg, MessageStatus.ROUTED, by, reason)
    targets = [route_to] if isinstance(route_to, str) else list(route_to)
    for t in targets:
        if t not in msg.routed_to:
            msg.routed_to.append(t)


def process_message(state, msg: MessageEnvelope, by: str,
                    reason: str = "参谋处理完毕") -> None:
    _transition_message(state, msg, MessageStatus.PROCESSED, by, reason)


def archive_message(state, msg: MessageEnvelope, by: str,
                    reason: str = "归档") -> None:
    _transition_message(state, msg, MessageStatus.ARCHIVED, by, reason)


def lose_message(state, msg: MessageEnvelope, by: str, reason: str) -> None:
    """传输丢失：内容永不进入收报室（D1）。"""
    _transition_message(state, msg, MessageStatus.LOST, by, reason)


def correct_message(state, old: MessageEnvelope, raw_text: str, by: str,
                    reason: str = "勘误") -> MessageEnvelope:
    """勘误电报（D4）：新建电文引用旧电文；旧电文标记 CORRECTED，原文不动。"""
    require_transition(message_transitions(), old.status, MessageStatus.CORRECTED)
    correction = MessageEnvelope(
        sender_id=by,
        sender_call_sign=old.sender_call_sign,
        recipient_ids=list(old.recipient_ids),
        priority=WorkPriority.CORRECTION,
        message_kind="correction",
        observed_at=old.observed_at,
        filed_at=now(state),
        supersedes_message_id=old.id,
        raw_text=raw_text,
        generated_by_npc=old.generated_by_npc,
        observation_id=old.observation_id,
    )
    file_message(state, correction, by=by, reason=f"勘误 {old.id}：{reason}")
    _transition_message(state, old, MessageStatus.CORRECTED, by,
                        f"被勘误电文 {correction.id} 更正")
    return correction


def player_inbox(state) -> list[MessageEnvelope]:
    """旗舰收报室（D1）：只含真正送达的电文（RECEIVED 及之后；LOST 永不出现）。"""
    return [m for m in state.messages if m.status in _PLAYER_READABLE_MESSAGE_STATUSES]


# ── 证据账本 ──

def register_evidence(
    state,
    message: MessageEnvelope,
    source_id: str,
    source_type: SourceType,
    access_roles: list[ActorRole],
    summary: str,
    position=None,
    reported: Optional[dict] = None,
    observed_at: Optional[datetime] = None,
    source_reliability: float = 0.6,
    identity_precision: float = 0.5,
    position_precision: float = 0.5,
    count_precision: float = 0.5,
    claim_scope: str = "contact",
) -> Evidence:
    """收报登记为证据（不可变账本；权限在 access_policy 内裁定）。

    position 为任意带 .lat/.lon 的位置对象（失真后的报告位置，非真值）。
    """
    ev = Evidence(
        id=next_id(state, "EV"),
        message_id=message.id,
        source_id=source_id,
        source_type=source_type,
        claim_scope=claim_scope,
        observed_at=observed_at or message.observed_at,
        received_at=message.received_at or now(state),
        source_reliability=source_reliability,
        identity_precision=identity_precision,
        position_precision=position_precision,
        count_precision=count_precision,
        freshness_at=message.received_at or now(state),
        access_policy=list(access_roles),
        summary=summary,
        lat=position.lat if position is not None else None,
        lon=position.lon if position is not None else None,
        reported=reported or {},
    )
    state.evidence.append(ev)
    return ev


def supersede_evidence(state, old: Evidence, by: str, summary: str,
                       position=None, reported: Optional[dict] = None) -> Evidence:
    """证据替代：新建证据引用旧证据，旧证据原地不动只翻状态。"""
    require_transition(evidence_transitions(), old.status, EvidenceStatus.SUPERSEDED)
    new = old.model_copy(deep=True)
    old.status = EvidenceStatus.SUPERSEDED  # 原记录字段不动，只翻状态（不可变账本）
    new.id = next_id(state, "EV")
    new.supersedes_evidence_id = old.id
    new.status = EvidenceStatus.ACTIVE
    new.summary = summary
    if position is not None:
        new.lat, new.lon = position.lat, position.lon
    new.reported = reported or old.reported
    new.received_at = now(state)
    new.freshness_at = now(state)
    new.corroboration = list(old.corroboration)
    state.evidence.append(new)
    _audit(state, actor_id=by, action="evidence_supersede",
           target_id=f"{old.id}->{new.id}", reason=summary,
           evidence_ids=[old.id, new.id])
    return new


def reject_evidence(state, old: Evidence, by: str, reason: str) -> None:
    """证据否定（误报），原记录保留。"""
    require_transition(evidence_transitions(), old.status, EvidenceStatus.REJECTED)
    old.status = EvidenceStatus.REJECTED  # 字段不动，只翻状态（不可变账本）
    _audit(state, actor_id=by, action="evidence_reject",
           target_id=old.id, reason=reason, evidence_ids=[old.id])


def validate_time_chain(ev: Evidence, raise_on_violation: bool = False) -> bool:
    """时间链一致性（D11）：observed_at ≤ received_at。"""
    ok = True
    if ev.observed_at is not None and ev.received_at is not None:
        ok = ev.observed_at <= ev.received_at
    if not ok and raise_on_violation:
        raise ValueError(f"时间链违例：observed_at 晚于 received_at（{ev.id}）")
    return ok


def evidence_view(ev: Evidence, role: ActorRole) -> EvidenceView:
    """权限转换：Evidence → EvidenceView（NPC 唯一读取通道）。"""
    if role not in ev.access_policy:
        raise PermissionError(f"角色 {role.value} 无权读取证据 {ev.id}")
    return EvidenceView(
        evidence_id=ev.id,
        message_id=ev.message_id,
        source_type=ev.source_type.value,
        source_label=ev.source_id,
        observed_at=ev.observed_at,
        received_at=ev.received_at,
        source_reliability=ev.source_reliability,
        summary=ev.summary,
        dimensions={
            "identity_precision": ev.identity_precision,
            "position_precision": ev.position_precision,
            "count_precision": ev.count_precision,
        },
    )


def visible_evidence(state, role: ActorRole,
                     include_inactive: bool = False) -> list[Evidence]:
    """角色可见证据集（权限内；默认只含现行有效证据）。"""
    out = []
    for ev in state.evidence:
        if role not in ev.access_policy:
            continue
        if not include_inactive and ev.status != EvidenceStatus.ACTIVE:
            continue
        out.append(ev)
    return out


# ── 信念与接触假设（按角色隔离）──

def belief_for(state, actor_id: str) -> BeliefState:
    for b in state.beliefs:
        if b.actor_id == actor_id:
            return b
    b = BeliefState(actor_id=actor_id, last_updated_at=now(state))
    state.beliefs.append(b)
    return b


def contacts_of(state, belief: BeliefState) -> list[ContactHypothesis]:
    by_id = {c.id: c for c in state.contacts}
    return [by_id[cid] for cid in belief.contacts if cid in by_id]


def add_contact(state, belief: BeliefState, *, classification: str,
                position=None,
                evidence_ids: list[str], first_seen_at: datetime,
                last_seen_at: datetime, by: str, reason: str,
                status: ContactStatus = ContactStatus.BEARING_ONLY,
                confidence_dimensions: Optional[dict] = None,
                created_from_assessment_id: Optional[str] = None) -> ContactHypothesis:
    """新接触假设（初始状态限 BEARING_ONLY/TENTATIVE）。"""
    if status not in (ContactStatus.BEARING_ONLY, ContactStatus.TENTATIVE):
        raise ValueError(f"接触初始状态非法: {status}")
    lat = position.lat if position is not None else None
    lon = position.lon if position is not None else None
    c = ContactHypothesis(
        id=next_id(state, "CT"),
        actor_id=belief.actor_id,
        classification=classification,
        status=status,
        observed_lat=lat,
        observed_lon=lon,
        current_lat=lat,
        current_lon=lon,
        evidence_ids=list(evidence_ids),
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        confidence_dimensions=confidence_dimensions or {},
        created_from_assessment_id=created_from_assessment_id,
    )
    state.contacts.append(c)
    belief.contacts.append(c.id)
    for eid in evidence_ids:
        if eid not in belief.known_evidence_ids:
            belief.known_evidence_ids.append(eid)
    belief.last_updated_at = now(state)
    belief.version += 1
    _audit(state, actor_id=by, action="contact_add", target_id=c.id,
           reason=reason, evidence_ids=evidence_ids,
           details={"classification": classification})
    return c


def transition_contact(state, contact: ContactHypothesis, *, to_status: ContactStatus,
                       by: str, reason: str, evidence_ids: Optional[list[str]] = None,
                       approved: bool = False, decision_id: str = "") -> None:
    """接触状态推进。

    PLOTTED 需指挥官批准（approved=True + decision_id）——D13 在转换层强制，
    参谋不能直接把假设画上正式海图。
    """
    require_transition(contact_transitions(), contact.status, to_status)
    if to_status == ContactStatus.PLOTTED and not approved:
        raise ValueError("接触上图需指挥官批准（ApprovedPlot 决议）")
    contact.status = to_status
    _audit(state, actor_id=by, action="contact_status", target_id=contact.id,
           reason=reason, evidence_ids=evidence_ids or [],
           details={"to": to_status.value, "decision_id": decision_id})


def record_association_candidate(state, contact: ContactHypothesis, *,
                                 candidate_id: str, by: str, reason: str) -> None:
    """登记候选关联——只记录，不静默合并（D9/M2.5）。"""
    if candidate_id not in contact.association_candidates:
        contact.association_candidates.append(candidate_id)
    _audit(state, actor_id=by, action="association", target_id=contact.id,
           reason=reason, details={"candidate": candidate_id})


# ── NPCClaim 审计 ──

def record_claim(state, *, assessment_id: str, actor_id: str, claim_type: str,
                 text: str, based_on_evidence_ids: Optional[list[str]] = None,
                 tool_call_ids: Optional[list[str]] = None,
                 confidence_dimensions: Optional[dict] = None,
                 created_at: Optional[datetime] = None,
                 supersedes_claim_id: Optional[str] = None) -> NPCClaim:
    claim = NPCClaim(
        id=next_id(state, "CL"),
        assessment_id=assessment_id,
        actor_id=actor_id,
        created_at=created_at or now(state),
        claim_type=claim_type,
        text=text,
        based_on_evidence_ids=based_on_evidence_ids or [],
        tool_call_ids=tool_call_ids or [],
        confidence_dimensions=confidence_dimensions or {},
        supersedes_claim_id=supersedes_claim_id,
    )
    state.claims.append(claim)
    return claim


# ── known_enemy 兼容读取层（§十一迁移）──

def known_enemy_compat_view(state) -> list:
    """旧 known_enemy 消费方的兼容视图。

    S2.4 起：已批准标图存在时由 ApprovedPlot 派生玩家敌情公共视图；
    在此之前直通 legacy known_enemy（迁移期兼容，不破坏现有 UI/测试）。
    """
    approved = getattr(state, "approved_plots", [])
    if approved:
        from src.intel.plots import approved_enemy_view  # S2.4 提供派生层
        return approved_enemy_view(state)
    return list(state.known_enemy)
