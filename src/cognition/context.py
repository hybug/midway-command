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


def _identity_signal_from_classification(text: str) -> float:
    """证据识别文本 → 识别信号（float 刻度；与 evidence_fit._CLASS_IDENTITY_SIGNAL 同族）。"""
    t = (text or "").lower()
    if "cv" in t or "航母" in text or "carrier" in t:
        # 轻航母/护航航母识别弱于正规航母
        return 0.8 if ("轻" in text or "cvl" in t) else 1.0
    if "战列" in text or "bb" in t:
        return 0.9
    if "巡洋" in text or "ca" in t or "cl" in t:
        return 0.4
    if "运输" in text or "transport" in t:
        return 0.2
    if "未识别" in text or "unknown" in t:
        return 0.0
    return 0.3


def _view_from_evidence(ev: Evidence) -> EvidenceView:
    """规则侧装配投影（字段集与 intel.evidence_view 一致，无真值）。

    dimensions 额外携带证据的失真报告值（bearing/distance/count/位置/航向航速/
    identity_signal）——evidence_fit 的评分输入；全部来自玩家所见同一失真值，
    非规则侧真值。
    """
    reported = ev.reported or {}
    dims: dict[str, float] = {
        "identity_precision": ev.identity_precision,
        "position_precision": ev.position_precision,
        "count_precision": ev.count_precision,
        "identity_signal": _identity_signal_from_classification(
            str(reported.get("classification", "")) or ev.summary),
    }
    for key in ("bearing", "distance_nm", "count", "course", "speed"):
        val = reported.get(key)
        if isinstance(val, (int, float)):
            dims[f"reported_{key}"] = float(val)
    if ev.lat is not None and ev.lon is not None:
        dims["reported_lat"] = float(ev.lat)
        dims["reported_lon"] = float(ev.lon)
    return EvidenceView(
        evidence_id=ev.id,
        message_id=ev.message_id,
        source_type=ev.source_type.value,
        source_label=ev.source_id,
        observed_at=ev.observed_at,
        received_at=ev.received_at,
        source_reliability=ev.source_reliability,
        summary=ev.summary,
        dimensions=dims,
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
