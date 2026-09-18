"""判断上下文装配（Phase S3.0：角色证据权限的执行点）。

装配函数是「NPC 只能读取按角色裁剪的证据」（D6）的结构性保证：
进入 prompt 的证据集只由本层产出——
- tf17_intel：S2 账本中 INTEL_OFFICER 权限内的现行有效证据；
- fitch / tf17_ops：只读已呈报简报（非 DRAFT）引用的证据与已批准标图
  提案引用的证据（呈报=分发事件，权限在分发层成立，不靠 prompt 提醒）；
- 任何角色不产出 actual_enemy / internal_truth_ref（EvidenceView 无真值字段）。
"""
from src.cognition.models import ActorProfile, JudgmentContext, JudgmentMemory
from src.intel import service as intel
from src.intel.contracts import ActorRole, ApprovalStatus, EvidenceStatus
from src.intel.judgment import EvidenceView
from src.intel.models import Evidence


def _view_from_evidence(ev: Evidence) -> EvidenceView:
    """规则侧装配投影（字段集与 intel.evidence_view 一致，无真值）。"""
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


def _briefed_evidence_ids(state) -> set[str]:
    """已呈报简报（非 DRAFT）引用的证据（呈报=对参谋班子可见的分发事件）。"""
    out: set[str] = set()
    for b in state.intel_briefs:
        if b.status == ApprovalStatus.DRAFT.value:
            continue
        out.update(b.new_evidence_ids)
        for a in state.assessments:
            if a.id in b.changed_judgments:
                out.update(a.based_on_evidence_ids)
    return out


def _approved_plot_evidence_ids(state) -> set[str]:
    """已批准标图提案引用的证据（含同链全部版本；批准历史保留）。"""
    out: set[str] = set()
    approved_ids = {p.plot_id for p in state.approved_plots}
    for p in state.plot_proposals:
        if p.plot_id in approved_ids:
            out.update(p.based_on_evidence_ids)
    return out


def actor_evidence_views(state, actor: ActorProfile) -> list[EvidenceView]:
    """按角色权限装配 EvidenceView 序列（D6 的结构性执行点）。"""
    from src.cognition.roster import get_permission
    perm = get_permission(actor.actor_id)
    by_id = {e.id: e for e in state.evidence}
    allowed: set[str] = set()
    for role_value in perm.get("raw_evidence_roles", []):
        role = ActorRole(role_value)
        allowed.update(e.id for e in intel.visible_evidence(state, role))
    via = perm.get("evidence_via", [])
    if "briefed" in via:
        allowed.update(_briefed_evidence_ids(state))
    if "approved_plots" in via:
        allowed.update(_approved_plot_evidence_ids(state))
    views = []
    for ev in state.evidence:
        if ev.id not in allowed or ev.status != EvidenceStatus.ACTIVE:
            continue
        views.append(_view_from_evidence(ev))
    return views


def build_context(state, actor: ActorProfile, *,
                  evidence: list[EvidenceView] | None = None,
                  memories: list[JudgmentMemory] | None = None,
                  duty_boundary: list[str] | None = None) -> JudgmentContext:
    """装配一次判断的 JudgmentContext（证据缺省按权限裁剪）。"""
    return JudgmentContext(
        actor=actor,
        evidence=actor_evidence_views(state, actor) if evidence is None else evidence,
        memories=memories or [],
        now=state.clock.game_time,
        duty_boundary=duty_boundary or [],
    )
