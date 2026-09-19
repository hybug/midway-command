"""S4 确定性业务触发器（计划 §七：提醒必须来自固定理由，不随机生成）。

挂钩点：
- run_intelligence_cycle（简报呈报）→ NEW_EVIDENCE（情报参谋）+ DECISION_REQUIRED（标图待批）
- plots.decide approve → OPPORTUNITY（航空指挥官）
- detect_conflicts → RISK_WARNING（作战参谋）
- 链上加急报告送达 → REPORT_ESCALATION（作战参谋）
- S5 Order 澄清请求 → CLARIFICATION_NEEDED

全部钩子在 roster 未激活（midway 占位）或角色缺失时静默跳过；
不读取 actual_enemy，不触碰判断与舰队状态（S4 边界）。
"""
import logging

from src.staff import service as staff
from src.staff.models import NoticePriority, NoticeReason

logger = logging.getLogger("midway.staff")

_PRIORITY_MAP = {"flash": NoticePriority.FLASH, "urgent": NoticePriority.URGENT}


def _actor_for(roster, role: str) -> str | None:
    actor = roster.actor_for_role(role)
    return actor


def _safe(state, roster, actor_id: str, **kwargs):
    try:
        return staff.raise_notice(state, roster, actor_id=actor_id, **kwargs)
    except PermissionError:
        return None


def on_brief_submitted(state, roster, brief) -> None:
    """简报呈报 → 情报参谋 NEW_EVIDENCE。"""
    if not roster.active:
        return
    actor = _actor_for(roster, "STAFF_INTEL")
    if actor:
        _safe(state, roster, actor, topic=f"新证据简报 {brief.id}",
              reason=NoticeReason.NEW_EVIDENCE,
              priority=_PRIORITY_MAP.get(brief.priority.value, NoticePriority.ROUTINE),
              source_type="brief", source_id=brief.id)


def on_plot_proposed(state, roster, proposal) -> None:
    """标图提案待批 → 情报参谋 DECISION_REQUIRED。"""
    if not roster.active:
        return
    actor = _actor_for(roster, "STAFF_INTEL")
    if actor:
        _safe(state, roster, actor, topic=f"标图提案待批 {proposal.plot_id} v{proposal.version}",
              reason=NoticeReason.DECISION_REQUIRED, priority=NoticePriority.URGENT,
              source_type="plot", source_id=proposal.id)


def on_plot_approved(state, roster, proposal) -> None:
    """批准上图 → 航空指挥官 OPPORTUNITY。"""
    if not roster.active:
        return
    actor = _actor_for(roster, "CTG_AIR")
    if actor:
        _safe(state, roster, actor, topic=f"已批准标图 {proposal.plot_id}——攻击窗口评估",
              reason=NoticeReason.OPPORTUNITY, priority=NoticePriority.URGENT,
              source_type="plot", source_id=proposal.id)


def on_conflict_open(state, roster, conflict) -> None:
    """证据冲突登记 → 作战参谋 RISK_WARNING。"""
    if not roster.active:
        return
    actor = _actor_for(roster, "STAFF_OPS")
    if actor:
        _safe(state, roster, actor, topic=f"证据冲突 {conflict.id}（{conflict.kind}）",
              reason=NoticeReason.RISK_WARNING, priority=NoticePriority.ROUTINE,
              source_type="conflict", source_id=conflict.id)


def on_chain_report_delivered(state, roster, report) -> None:
    """加急下级报告送达 → 作战参谋 REPORT_ESCALATION。"""
    if not roster.active:
        return
    actor = _actor_for(roster, "STAFF_OPS")
    if actor:
        _safe(state, roster, actor, topic=f"加急报告 {report.id} 已上呈",
              reason=NoticeReason.REPORT_ESCALATION, priority=NoticePriority.URGENT,
              source_type="report", source_id=report.id)


def on_order_clarification(state, roster, order, actor_id: str) -> None:
    """Order 存在关键歧义 → 责任参谋 CLARIFICATION_NEEDED（S5 挂钩）。"""
    if not roster.active:
        return
    _safe(state, roster, actor_id, topic=f"Order {order.id} 意图歧义",
          reason=NoticeReason.CLARIFICATION_NEEDED, priority=NoticePriority.URGENT,
          source_type="order", source_id=order.id)
