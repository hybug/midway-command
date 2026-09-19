"""S4 服务层：指挥链上呈（ChainReport）与主动提醒（CommanderNotice）。

纪律（计划 §六/§七）：
- 所有正式报告保留原始来源；上呈批注不改写原文。
- 下级参谋不能通过 LLM 绕过链条建立 CommanderNotice（can_initiate 白名单）。
- 同一 actor 同时只一个 open notice；同一 topic 未解决不重复创建；暂缓进冷却；
  同一事项可升级一次优先级。
- 本层不读取 actual_enemy，不改变判断正确率，不修改舰队状态（D7/S4 边界）。
"""
from datetime import timedelta

from src.intel import service as intel
from src.staff.models import (
    ChainReport,
    ChainReportState,
    CommanderNotice,
    NoticePriority,
    NoticeReason,
    NoticeState,
)
from src.staff.roster import RunRoster

DEFER_COOLDOWN_MIN = 60          # 暂缓冷却（游戏分钟；设计值 ESTIMATED）

_NOTICE_ACTIONS = {"acknowledge", "defer", "dismiss", "close"}


# ── 指挥链上呈 ──


def _resolve_route(roster: RunRoster, origin_actor_id: str,
                   origin_role: str | None) -> list[str]:
    """role 链 BFS 到 COMMANDER；route = 沿途 actor_id（不含 origin）。"""
    role_of = roster.role_of_actor.get(origin_actor_id, origin_role or "")
    links = roster.chain_of_command
    adjacency: dict[str, str] = {l["from_role"]: l["to_role"] for l in links}
    route: list[str] = []
    cur = role_of
    seen = set()
    while cur and cur != "COMMANDER" and cur not in seen:
        seen.add(cur)
        nxt = adjacency.get(cur)
        if nxt is None:
            break
        actor = roster.actor_for_role(nxt)
        if nxt != "COMMANDER" and not actor:
            break
        route.append(actor or roster.commander_id)
        cur = nxt
    if not route:
        route = [roster.commander_id]
    return route


def file_chain_report(state, roster: RunRoster, *, origin_actor_id: str,
                      origin_role: str | None = None, source_type: str,
                      source_id: str, summary: str, priority: str = "routine",
                      route: list[str] | None = None) -> ChainReport:
    """下级/专业岗位提交正式报告：按职责与指挥关系逐级上呈。"""
    if route is None:
        route = _resolve_route(roster, origin_actor_id, origin_role)
    report = ChainReport(
        id=intel.next_id(state, "CRP"),
        origin_actor_id=origin_actor_id,
        origin_role=origin_role or roster.role_of_actor.get(origin_actor_id, ""),
        current_holder_id=origin_actor_id,
        next_holder_id=route[0],
        route=list(route),
        source_type=source_type,
        source_id=source_id,
        summary=summary,
        priority=priority,
        at=intel.now(state),
        history=[{"at": intel.now(state).isoformat(),
                  "event": "filed", "holder": origin_actor_id}],
    )
    state.staff_chain_reports.append(report)
    intel._audit(state, actor_id=origin_actor_id, action="chain_report_filed",
                 target_id=report.id, reason=summary[:60],
                 details={"source": source_id, "route": list(route)})
    return report


def process_staff_step(state, minutes: int, roster: RunRoster | None = None) -> list[str]:
    """Pipeline 步骤：链上报告每 tick 前进一跳；到 COMMANDER 即送达。

    roster 可选：提供时，加急报告送达会触发核心参谋 REPORT_ESCALATION 提醒。
    """
    from src.staff import hooks
    notes: list[str] = []
    for report in state.staff_chain_reports:
        if report.state != ChainReportState.IN_CHAIN:
            continue
        holder = report.next_holder_id
        report.current_holder_id = holder
        report.history.append({"at": intel.now(state).isoformat(),
                               "event": "held", "holder": holder})
        if holder == report.route[-1]:
            report.state = ChainReportState.DELIVERED
            report.delivered_at = intel.now(state)
            report.next_holder_id = holder
            report.history.append({"at": intel.now(state).isoformat(),
                                   "event": "delivered", "holder": holder})
            intel._audit(state, actor_id=holder, action="chain_delivered",
                         target_id=report.id, reason="报告送达指挥官")
            notes.append(f"报告 {report.id} 已上呈指挥官")
            if roster is not None and report.priority in ("urgent", "flash"):
                hooks.on_chain_report_delivered(state, roster, report)
        else:
            idx = report.route.index(holder)
            report.next_holder_id = report.route[idx + 1]
    return notes


def delivered_reports(state) -> list[ChainReport]:
    """指挥官可见面：只有已送达的报告（§六/§十一 未送达不暴露）。"""
    return [r for r in state.staff_chain_reports
            if r.state == ChainReportState.DELIVERED]


def annotate_chain_report(state, roster: RunRoster, report: ChainReport, *,
                          by: str, note: str) -> None:
    """持有人批注：只追加，不改写原文（§六）。"""
    if report.state != ChainReportState.IN_CHAIN:
        raise ValueError("仅链上报告可批注")
    if by != report.current_holder_id:
        raise PermissionError("只有当前持有人可批注")
    report.annotations.append({
        "by": by, "note": note, "at": intel.now(state).isoformat()})
    intel._audit(state, actor_id=by, action="chain_annotate",
                 target_id=report.id, reason=note[:60])


# ── 主动提醒 ──


def raise_notice(state, roster: RunRoster, *, actor_id: str, topic: str,
                 reason: NoticeReason | str, priority: NoticePriority | str,
                 source_type: str, source_id: str) -> CommanderNotice | None:
    """名单内人员主动提醒：固定理由 + 去重 + 冷却 + 单次升级。

    返回 None 表示被规则拦截（同 actor 已有 open / 冷却期内）。
    """
    reason = NoticeReason(reason)
    priority = NoticePriority(priority)
    channel = roster.channel(actor_id)
    if channel is None or not channel.can_initiate:
        raise PermissionError(f"{actor_id} 不在直接沟通名单或无主动职权（D3/D5）")

    same_topic = None
    has_open = False
    for n in state.staff_notices:
        if n.actor_id != actor_id:
            continue
        if n.state == NoticeState.OPEN:
            has_open = True
            if n.topic == topic:
                same_topic = n
        elif n.state == NoticeState.DEFERRED and n.topic == topic:
            if n.cooldown_until and intel.now(state) < n.cooldown_until:
                return None   # 冷却期内不重建
    if same_topic is not None:
        # 同主题：允许单次升级优先级，不重复创建（§七）
        rank = {NoticePriority.ROUTINE: 0, NoticePriority.URGENT: 1,
                NoticePriority.FLASH: 2}
        if not same_topic.escalated and rank[priority] > rank[same_topic.priority]:
            same_topic.priority = priority
            same_topic.escalated = True
            same_topic.source_type, same_topic.source_id = source_type, source_id
            intel._audit(state, actor_id=actor_id, action="staff_notice_escalate",
                         target_id=same_topic.id, reason=f"升级至 {priority.value}")
        return same_topic
    if has_open:
        return None   # 同一 actor 同时只保留一个未处理事项（D6）
    notice = CommanderNotice(
        id=intel.next_id(state, "NOT"),
        actor_id=actor_id,
        topic=topic,
        priority=priority,
        source_type=source_type,
        source_id=source_id,
        notice_reason=reason,
        created_at=intel.now(state),
    )
    state.staff_notices.append(notice)
    intel._audit(state, actor_id=actor_id, action="staff_notice_raised",
                 target_id=notice.id, reason=f"{reason.value}: {topic[:40]}",
                 details={"priority": priority.value, "source": source_id})
    return notice


def dismiss_notice(state, roster: RunRoster, notice: CommanderNotice, *,
                   action: str, by: str) -> CommanderNotice:
    """接见（acknowledge）/ 暂缓（defer）/ 忽略（dismiss）/ 关闭（close）。

    只改变沟通状态——不改判断、不改舰队（§八）。全部留档。
    """
    if action not in _NOTICE_ACTIONS:
        raise ValueError(f"非法通知动作 {action!r}，允许：{sorted(_NOTICE_ACTIONS)}")
    if notice.state in (NoticeState.RESOLVED, NoticeState.EXPIRED):
        raise ValueError("通知已关闭")
    transitions = {
        "acknowledge": NoticeState.ACKNOWLEDGED,
        "defer": NoticeState.DEFERRED,
        "dismiss": NoticeState.RESOLVED,
        "close": NoticeState.RESOLVED,
    }
    notice.state = transitions[action]
    if action == "defer":
        notice.cooldown_until = intel.now(state) + timedelta(minutes=DEFER_COOLDOWN_MIN)
    notice.handled_by.append({
        "by": by, "action": action, "at": intel.now(state).isoformat()})
    intel._audit(state, actor_id=by, action=f"staff_notice_{action}",
                 target_id=notice.id, reason=f"{by} {action} {notice.topic[:40]}")
    return notice


def open_notices(state) -> list[CommanderNotice]:
    """指挥官未处理（open）通知。"""
    return [n for n in state.staff_notices if n.state == NoticeState.OPEN]


def visit_events(state) -> list[dict]:
    """STAFF_VISIT 事件源形状（S8 NotificationCenter 消费）。"""
    return [{"actor_id": n.actor_id, "topic": n.topic,
             "at": n.created_at.isoformat(), "notice_id": n.id,
             "priority": n.priority.value}
            for n in open_notices(state)]


# ── 极简档案（S4.4）──


def dossier_summary(state, roster: RunRoster, actor_id: str) -> dict:
    """只含四字段：身份 / 状态 / 当前关注 / 最近两次互动。"""
    channel = roster.channel(actor_id)
    notice_for = [n for n in state.staff_notices if n.actor_id == actor_id]
    latest = notice_for[-1] if notice_for else None
    status_line = "在舱待命"
    if latest and latest.state == NoticeState.OPEN:
        status_line = f"请求入舱：{latest.topic[:24]}"
    elif latest and latest.state == NoticeState.ACKNOWLEDGED:
        status_line = "接见中/事项处理中"
    elif latest and latest.state == NoticeState.DEFERRED:
        status_line = "事项暂缓（冷却）"
    recent: list[dict] = []
    for n in reversed(notice_for):
        recent.append({"at": n.created_at.isoformat(), "kind": "notice",
                       "note": f"{n.notice_reason.value}：{n.topic[:30]}"})
    for e in reversed(state.intel_audit):
        if len(recent) >= 2:
            break
        if e.actor_id == actor_id and e.action.startswith("chain_"):
            recent.append({"at": e.at.isoformat(), "kind": "chain",
                           "note": e.reason[:30]})
    return {
        "actor_id": actor_id,
        "status_line": status_line,
        "current_focus": latest.topic[:40] if latest else "—",
        "recent": recent[:2],
    }
