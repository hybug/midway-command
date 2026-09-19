"""作战标图审批（Phase S2.4，§M2.6/§7.2）。

纪律：
- 未批准提案不进正式海图（D13）：ApprovedPlot 是海图敌情唯一输入。
- 已批准标图不可覆盖（D14）：新证据只能产生同链新版本提案并再次审批；
  批准新版时旧版 plot 置 superseded、历史全部保留。
- 全程可追溯：批注/决议/审计均为追加记录。
"""
import math
from datetime import datetime
from typing import Optional

from src.intel.contracts import (
    ActorRole,
    ApprovalStatus,
    ContactStatus,
    approval_transitions,
    require_transition,
)
from src.intel import service as intel
from src.intel.models import (
    ApprovedPlot,
    CommanderDecision,
    PlotGeometry,
    PlotProposal,
)


def _fleet_position(state) -> tuple:
    tf = state.task_forces[0]
    return (tf.carriers[0].position.lat, tf.carriers[0].position.lon)


def _bearing_between(a: tuple, b: tuple) -> float:
    from src.scouting import calculate_bearing
    return calculate_bearing(a, b)


def _distance_between(a: tuple, b: tuple) -> float:
    from src.scouting import calculate_distance_nm
    return calculate_distance_nm(a, b)


def create_plot_proposal(
    state,
    *,
    author_actor_id: str,
    assessment=None,
    contact=None,
    evidence=None,
    change_summary: str = "初版标图",
    assumptions: Optional[list[str]] = None,
    method: str = "bearing_distance",
    supersedes: Optional[PlotProposal] = None,
) -> PlotProposal:
    """由判断书/接触假设产生标图提案（§7.1 步骤16）。

    supersedes 提供时进入同一 plot_id 修订链（version+1，D14：
    新证据不静默覆盖已批准标图——新版必须重新审批）。
    """
    if supersedes is not None:
        plot_id = supersedes.plot_id
        version = supersedes.version + 1
    else:
        plot_id = intel.next_id(state, "PLOT")
        version = 1

    geometry = None
    confidence = dict(assessment.confidence_dimensions) if assessment else {}
    if contact is not None:
        fleet = _fleet_position(state)
        cpos = (contact.current_lat, contact.current_lon)
        if cpos[0] is not None:
            geometry = PlotGeometry(
                lat=contact.current_lat,
                lon=contact.current_lon,
                uncertainty_radius_nm=contact.uncertainty_radius_nm,
                bearing_line_deg=round(_bearing_between(fleet, cpos), 1),
                bearing_from_lat=fleet[0],
                bearing_from_lon=fleet[1],
                bearing_from_label=state.task_forces[0].name,
                distance_nm=round(_distance_between(fleet, cpos), 1),
                course_estimate=contact.course_estimate,
                speed_estimate=contact.speed_estimate,
            )
    elif evidence is not None and evidence.lat is not None:
        fleet = _fleet_position(state)
        epos = (evidence.lat, evidence.lon)
        geometry = PlotGeometry(
            lat=evidence.lat,
            lon=evidence.lon,
            bearing_line_deg=round(_bearing_between(fleet, epos), 1),
            bearing_from_lat=fleet[0],
            bearing_from_lon=fleet[1],
            bearing_from_label=state.task_forces[0].name,
            distance_nm=round(_distance_between(fleet, epos), 1),
        )

    proposal = PlotProposal(
        id=intel.next_id(state, "PP"),
        plot_id=plot_id,
        version=version,
        author_actor_id=author_actor_id,
        created_at=intel.now(state),
        based_on_evidence_ids=list(assessment.based_on_evidence_ids) if assessment else
        ([evidence.id] if evidence else []),
        assessment_ids=[assessment.id] if assessment else [],
        geometry=geometry,
        method=method,
        assumptions=assumptions or [],
        confidence=confidence,
        change_summary=change_summary,
        supersedes_version=supersedes.version if supersedes else None,
        contact_id=contact.id if contact is not None else None,
    )
    # DRAFT → PROPOSED（呈报指挥官）
    require_transition(approval_transitions(), ApprovalStatus.DRAFT,
                       ApprovalStatus.PROPOSED)
    proposal.status = ApprovalStatus.PROPOSED.value
    state.plot_proposals.append(proposal)
    intel._audit(state, actor_id=author_actor_id, action="plot_propose",
                 target_id=proposal.id,
                 reason=change_summary,
                 evidence_ids=proposal.based_on_evidence_ids,
                 details={"plot_id": plot_id, "version": version})
    return proposal


def latest_revision_base(state) -> Optional[PlotProposal]:
    """修订基准：版本最高的非驳回提案（§7.2 新证据 → 新版修订提案）。

    REJECTED 链不延续——误报否定后必须另立新链。
    """
    best = None
    for p in state.plot_proposals:
        if p.status == ApprovalStatus.REJECTED.value:
            continue
        if best is None or p.version > best.version:
            best = p
    return best


def revise_plot_proposal(state, old: PlotProposal, *, author_actor_id: str,
                         change_summary: str, geometry: Optional[PlotGeometry] = None,
                         assessment=None) -> PlotProposal:
    """修订提案（REVISION_REQUESTED 回路 / 新证据修订）：同链新版本，重新审批。"""
    new = create_plot_proposal(
        state, author_actor_id=author_actor_id,
        assessment=assessment,
        contact=_contact_by_id(state, old.contact_id) if old.contact_id else None,
        change_summary=change_summary,
        supersedes=old,
    )
    if geometry is not None:
        new.geometry = geometry
    return new


def _contact_by_id(state, contact_id):
    for c in state.contacts:
        if c.id == contact_id:
            return c
    return None


def annotate_proposal(state, proposal: PlotProposal, *, by: str, stance: str,
                      note: str) -> dict:
    """参谋长批注（追加式；呈报意见不覆盖既有批注）。"""
    entry = {
        "at": intel.now(state).isoformat(),
        "by": by,
        "stance": stance,       # endorse / concern / object
        "note": note,
    }
    proposal.annotations.append(entry)
    intel._audit(state, actor_id=by, action="plot_annotate",
                 target_id=proposal.id, reason=f"{stance}: {note[:50]}")
    return entry


def decide(state, proposal: PlotProposal, *, action: str, by: str = "player",
           comment: str = "", items_approved: Optional[list[str]] = None) -> ApprovedPlot:
    """指挥官决议：approve / reject / defer / request_revision / partial_approve。"""
    status = ApprovalStatus(proposal.status)
    decision = CommanderDecision(
        id=intel.next_id(state, "DEC"),
        at=intel.now(state),
        plot_id=proposal.plot_id,
        proposal_id=proposal.id,
        action=action,
        items_approved=items_approved or [],
        comment=comment,
    )
    state.commander_decisions.append(decision)

    if action == "approve":
        require_transition(approval_transitions(), status, ApprovalStatus.APPROVED)
        proposal.status = ApprovalStatus.APPROVED.value
        if proposal.method == "rejection":
            # §7.4 误报否定批准：接触 REJECTED、正式标图撤下、证据否定
            from src.intel.conflicts import apply_rejection_approval
            apply_rejection_approval(state, proposal, decision)
            plot = _active_plot(state, proposal.plot_id)
        else:
            plot = _apply_approval(state, proposal, decision)
        intel._audit(state, actor_id=by, action="plot_approve",
                     target_id=proposal.id, reason=comment,
                     details={"decision": decision.id, "version": proposal.version})
        # S4 确定性触发：批准上图 → 航空指挥官 OPPORTUNITY 提醒
        from src.staff.roster import get_active_roster
        from src.staff import hooks as staff_hooks
        _s4_roster = get_active_roster()
        if _s4_roster is not None:
            staff_hooks.on_plot_approved(state, _s4_roster, proposal)

    elif action == "reject":
        require_transition(approval_transitions(), status, ApprovalStatus.REJECTED)
        proposal.status = ApprovalStatus.REJECTED.value
        plot = _active_plot(state, proposal.plot_id)  # 未上图则无
        intel._audit(state, actor_id=by, action="plot_reject",
                     target_id=proposal.id, reason=comment,
                     details={"decision": decision.id})

    elif action == "defer":
        require_transition(approval_transitions(), status, ApprovalStatus.DEFERRED)
        proposal.status = ApprovalStatus.DEFERRED.value
        plot = _active_plot(state, proposal.plot_id)
        intel._audit(state, actor_id=by, action="plot_defer",
                     target_id=proposal.id, reason=comment,
                     details={"decision": decision.id})

    elif action == "request_revision":
        require_transition(approval_transitions(), status,
                           ApprovalStatus.REVISION_REQUESTED)
        proposal.status = ApprovalStatus.REVISION_REQUESTED.value
        plot = _active_plot(state, proposal.plot_id)
        intel._audit(state, actor_id=by, action="plot_request_revision",
                     target_id=proposal.id, reason=comment,
                     details={"decision": decision.id})

    elif action == "partial_approve":
        require_transition(approval_transitions(), status,
                           ApprovalStatus.PARTIALLY_APPROVED)
        proposal.status = ApprovalStatus.PARTIALLY_APPROVED.value
        plot = _active_plot(state, proposal.plot_id)
        intel._audit(state, actor_id=by, action="plot_partial_approve",
                     target_id=proposal.id, reason=comment,
                     details={"decision": decision.id,
                              "items": items_approved or []})

    else:
        raise ValueError(f"未知决议动作: {action}")

    return plot


def reopen_deferred(state, proposal: PlotProposal, *, by: str) -> None:
    """暂缓后重新呈报（DEFERRED → PROPOSED）。"""
    require_transition(approval_transitions(), ApprovalStatus(proposal.status),
                       ApprovalStatus.PROPOSED)
    proposal.status = ApprovalStatus.PROPOSED.value
    intel._audit(state, actor_id=by, action="plot_resubmit",
                 target_id=proposal.id, reason="暂缓后重新呈报")


# ── 批准生效 ──

def _active_plot(state, plot_id: str) -> Optional[ApprovedPlot]:
    for p in state.approved_plots:
        if p.plot_id == plot_id and p.state == "active":
            return p
    return None


def _apply_approval(state, proposal: PlotProposal,
                    decision: CommanderDecision) -> ApprovedPlot:
    """批准生效：创建/更新 ApprovedPlot；同链旧版置 superseded；接触上图联动。"""
    old_plot = _active_plot(state, proposal.plot_id)
    if old_plot is not None:
        old_plot.state = "superseded"   # 旧版本存档（保留全部历史）
        # 同链已批准的旧提案一并标记被替代
        for pp in state.plot_proposals:
            if (pp.plot_id == proposal.plot_id
                    and pp.id != proposal.id
                    and pp.status == ApprovalStatus.APPROVED.value):
                pp.status = ApprovalStatus.SUPERSEDED.value

    entry = {
        "version": proposal.version,
        "proposal_id": proposal.id,
        "geometry": proposal.geometry.model_dump() if proposal.geometry else None,
        "change_summary": proposal.change_summary,
        "approved_at": decision.at.isoformat() if decision.at else None,
        "decision_id": decision.id,
    }
    if old_plot is not None:
        old_plot.current_version = proposal.version
        old_plot.approved_at = decision.at
        old_plot.approved_by = "player"
        old_plot.decision_id = decision.id
        old_plot.state = "active"   # 同链新版本批准：该 plot 继续作为正式图层
        old_plot.history.append(entry)
        plot = old_plot
    else:
        plot = ApprovedPlot(
            plot_id=proposal.plot_id,
            current_version=proposal.version,
            approved_by="player",
            approved_at=decision.at,
            decision_id=decision.id,
            history=[entry],
        )
        state.approved_plots.append(plot)

    # 接触上图联动（转换层强制 approved=True）
    if proposal.contact_id:
        contact = _contact_by_id(state, proposal.contact_id)
        if contact is not None and contact.status != ContactStatus.PLOTTED:
            intel.transition_contact(
                state, contact, to_status=ContactStatus.PLOTTED,
                by="player", reason=f"批准 {proposal.id}",
                evidence_ids=proposal.based_on_evidence_ids,
                approved=True, decision_id=decision.id,
            )
    return plot


# ── 玩家敌情公共视图（§十一：/state.known_enemy = 已批准标图视图）──

def approved_enemy_view(state) -> list:
    """由活动 ApprovedPlot 派生玩家敌情视图（旧 EnemyKnown 结构兼容）。"""
    from src.state import EnemyKnown, Position

    out = []
    for plot in state.approved_plots:
        if plot.state != "active" or not plot.history:
            continue
        latest = plot.history[-1]
        geo = latest.get("geometry") or {}
        if geo.get("lat") is None:
            continue
        out.append(EnemyKnown(
            position=Position(lat=geo["lat"], lon=geo["lon"]),
            description=(
                f"APPROVED PLOT v{plot.current_version}: "
                f"{latest.get('change_summary', '')}"
                f"（置信度位置 {geo.get('uncertainty_radius_nm', '?')}nm）"
            ),
            confidence="approved",
            source=f"plot:{plot.plot_id}",   # 一键反查：完整标图链 id
            reported_at=plot.approved_at or intel.now(state),
        ))
    return out


def plot_chain_history(state, plot_id: str) -> list[dict]:
    """标图链全版本历史（版本比较/复盘用）。"""
    chain = [p for p in state.plot_proposals if p.plot_id == plot_id]
    chain.sort(key=lambda p: p.version)
    return [
        {
            "version": p.version,
            "proposal_id": p.id,
            "status": p.status,
            "change_summary": p.change_summary,
            "author": p.author_actor_id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "geometry": p.geometry.model_dump() if p.geometry else None,
            "annotations": p.annotations,
        }
        for p in chain
    ]
