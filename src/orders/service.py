"""S5 服务层：Order 契约、校验路由、冲突检查、S2 传达、Pipeline 生效。

边界（计划 §十二）：
- 命令端点不直接改舰队状态——所有效果经 process_orders_step（Pipeline）生效（D9/D10）。
- S2 独占送达/延迟/丢失；S5 无确认超时、无自动重发（D11）。
- 自然语言只产草稿；LLM 建议不执行（D5）。
- 修改与取消形成新记录；已发生效果不可回滚（D13/D14）。
"""
import re
from datetime import timedelta

from src.intel import service as intel
from src.intel.contracts import CommCondition, WorkPriority
from src.intel.models import MessageEnvelope
from src.intel.rng import RNGService
from src.orders.models import (
    AuthorityMode,
    Order,
    OrderEvent,
    OrderEventType,
    OrderStatus,
    OrderType,
)
from src.staff.roster import RunRoster

# 旗舰↔责任岗位通信（v0 统一口径；同舰/异舰细分留待 S6）
_ORDER_COMM_DISTANCE_NM = 120
_ORDER_COMM_DELAY_MIN = 10      # TBS 传达延迟（设计值 ESTIMATED；丢失由通信检定决定）
_PLAN_DEFAULT_AIRCRAFT = 4


class OrderConflict(Exception):
    """生效前冲突：携带在位 Order，由 UI 展示新旧参数供指挥官决断（§九）。"""

    def __init__(self, active_order: Order, message: str = ""):
        self.active_order = active_order
        super().__init__(message or f"与在位命令 {active_order.id} 冲突")


# ── 校验 ──


def _validate_parameters(order_type: OrderType, parameters: dict) -> dict:
    if order_type == OrderType.SET_COURSE:
        course = parameters.get("course")
        if not isinstance(course, int) or not 0 <= course <= 359:
            raise ValueError("SET_COURSE 需要 0-359 整数航向。")
        return {"course": course}
    if order_type == OrderType.LAUNCH_SCOUT:
        missing = [k for k in ("search_objective", "search_area", "max_range_nm")
                   if k not in parameters]
        if missing:
            raise ValueError(f"LAUNCH_SCOUT 缺少参数：{missing}")
        try:
            max_range = int(parameters["max_range_nm"])
        except (TypeError, ValueError):
            raise ValueError("max_range_nm 必须是整数海里。")
        if max_range <= 0:
            raise ValueError("max_range_nm 必须为正。")
        out = dict(parameters)
        out["max_range_nm"] = max_range
        out.setdefault("time_window", "")
        out.setdefault("constraints", [])
        return out
    raise ValueError(f"未知 Order 类型 {order_type}")


def get_order(state, order_id: str) -> Order:
    for o in state.orders:
        if o.id == order_id:
            return o
    raise KeyError(f"Order {order_id} 不存在")


def _event(state, order: Order, event_type: OrderEventType, actor_id: str,
           summary: str = "", source_ref: str = "") -> None:
    state.order_events.append(OrderEvent(
        id=intel.next_id(state, "OEV"),
        order_id=order.id,
        at=intel.now(state),
        actor_id=actor_id,
        event_type=event_type,
        summary=summary,
        source_ref=source_ref,
    ))
    order.updated_at = intel.now(state)


# ── S5.0/S5.1 创建与签发 ──


def create_draft(state, *, order_type, target_refs: list[str], parameters: dict,
                 commander_intent_text: str, authority_mode,
                 priority: str = "routine", source_refs: list[str] | None = None) -> Order:
    if not isinstance(order_type, OrderType):
        try:
            order_type = OrderType(order_type)
        except ValueError:
            raise ValueError(f"非法 Order 类型 {order_type!r}（v0 仅 SET_COURSE/LAUNCH_SCOUT）")
    if not (commander_intent_text or "").strip():
        raise ValueError("commander_intent_text 必填（一等输入，原文不可改写）。")
    authority_mode = AuthorityMode(authority_mode)
    parameters = _validate_parameters(order_type, parameters)
    order = Order(
        id=intel.next_id(state, "ORD"),
        order_type=order_type,
        target_refs=list(target_refs),
        parameters=parameters,
        commander_intent_text=commander_intent_text.strip(),
        authority_mode=authority_mode,
        priority=priority,
        source_refs=list(source_refs or []),
        created_at=intel.now(state),
        updated_at=intel.now(state),
    )
    state.orders.append(order)
    _event(state, order, OrderEventType.ORDER_CREATED, "fletcher",
           summary=f"{order_type.value} 草稿创建")
    return order


def update_draft(state, order_id: str, *, parameters: dict | None = None,
                 commander_intent_text: str | None = None,
                 target_refs: list[str] | None = None,
                 priority: str | None = None) -> Order:
    order = get_order(state, order_id)
    if order.status != OrderStatus.DRAFT:
        raise ValueError("仅 DRAFT 可编辑（ISSUED 后不可原地修改）。")
    if commander_intent_text is not None:
        if not commander_intent_text.strip():
            raise ValueError("commander_intent_text 不能为空。")
        order.commander_intent_text = commander_intent_text.strip()
    if parameters is not None:
        order.parameters = _validate_parameters(order.order_type, parameters)
    if target_refs is not None:
        order.target_refs = list(target_refs)
    if priority is not None:
        order.priority = priority
    order.updated_at = intel.now(state)
    return order


def _resolve_responsibility(roster: RunRoster, order: Order) -> tuple[str, str]:
    role_key = "NAVIGATOR" if order.order_type == OrderType.SET_COURSE else "AIR_OFFICER"
    bound_role = roster.order_routing.get(role_key)
    if not bound_role:
        raise ValueError(f"scenario roster 未配置 {role_key} 责任岗位——Order 不能签发。")
    actor = roster.role_bindings.get(bound_role) or bound_role
    if not actor:
        raise ValueError(f"{role_key} 责任岗位无现任者——Order 不能签发。")
    return role_key, actor


def _find_conflict(state, order: Order) -> Order | None:
    """同一实体、同一控制维度的在位命令（ISSUED/ACTIVE）即冲突（§九）。"""
    for other in state.orders:
        if other.id == order.id or other.order_type != order.order_type:
            continue
        if other.status not in (OrderStatus.ISSUED, OrderStatus.ACTIVE):
            continue
        if set(other.target_refs) & set(order.target_refs):
            return other
    return None


def issue_order(state, roster: RunRoster, order_id: str,
                supersede_ids: list[str] | None = None,
                force_loss: bool = False) -> Order:
    """签发：岗位路由 → 冲突检查 → S2 发报（延迟/丢失由检定决定）。"""
    order = get_order(state, order_id)
    if order.status != OrderStatus.DRAFT:
        raise ValueError(f"Order 状态 {order.status.value} 不可签发。")
    role, actor = _resolve_responsibility(roster, order)
    order.responsible_role, order.responsible_actor_id = role, actor

    conflict = _find_conflict(state, order)
    if conflict is not None:
        if not supersede_ids or conflict.id not in supersede_ids:
            raise OrderConflict(
                conflict,
                f"与在位命令 {conflict.id}（{conflict.order_type.value} "
                f"{conflict.parameters}）冲突——FLASH 不可绕过冲突检查。")

    for sid in supersede_ids or []:
        old = get_order(state, sid)
        if old.status not in (OrderStatus.ISSUED, OrderStatus.ACTIVE):
            raise ValueError(f"被替代命令 {sid} 状态 {old.status.value} 不可替代。")
        old.status = OrderStatus.CANCELLED
        old.result = {"outcome": "cancelled", "effects": [], "deviations": [],
                      "summary": f"被 {order.id} 替代", "superseded_by": order.id}
        _event(state, old, OrderEventType.ORDER_CANCELLED, "fletcher",
               summary=f"被新命令 {order.id} 替代")

    # S2 发报：检定延迟与丢失（骰子在案；无确认超时、无自动重发）
    rng = RNGService(state)
    comm, _rec = rng.communication_check(
        actor_id=f"{order.id} 旗语/电台", competence=5,
        distance_nm=_ORDER_COMM_DISTANCE_NM,
        reason=f"{order.id} 命令传达通信检定")
    delay = _ORDER_COMM_DELAY_MIN
    msg = MessageEnvelope(
        sender_id="fletcher",
        sender_call_sign="CTF-17 FLAG",
        recipient_ids=[order.responsible_actor_id],
        priority=WorkPriority(order.priority) if order.priority in (
            "routine", "urgent", "flash") else WorkPriority.ROUTINE,
        message_kind="order",
        observed_at=intel.now(state),
        raw_text=f"ORDER {order.id} {order.order_type.value} "
                 f"{order.parameters} INTENT: {order.commander_intent_text}",
    )
    intel.file_message(state, msg, by="fletcher", reason=f"签发 {order.id}")
    intel.mark_in_transit(state, msg, by="TBS 通信链")
    msg.transit_eta = intel.now(state) + timedelta(minutes=delay)
    msg.condition = CommCondition.COMPLETE
    order.delivery_message_id = msg.id
    order.delivery_eta = msg.transit_eta
    order.delivery_will_lose = bool(force_loss or comm.raw_roll <= 3)
    order.status = OrderStatus.ISSUED
    order.reported_status = "issued"
    _event(state, order, OrderEventType.ORDER_ISSUED, "fletcher",
           summary=f"下达 {order.order_type.value} → {role}({actor})",
           source_ref=msg.id)
    return order


# ── S5.3/S5.4 Pipeline 生效（唯一状态变更执行点）──


def process_orders_step(state, minutes: int, roster: RunRoster | None = None) -> list[str]:
    notes: list[str] = []
    now = intel.now(state)
    for order in list(state.orders):
        if order.status == OrderStatus.ISSUED and order.delivery_eta \
                and now >= order.delivery_eta:
            notes.extend(_on_delivery(state, order, roster))
        if order.status == OrderStatus.ACTIVE:
            notes.extend(_execute_active(state, order))
        if order.report_message_id:
            notes.extend(_maybe_deliver_report(state, order))
    return notes


def _on_delivery(state, order: Order, roster) -> list[str]:
    msg = next(m for m in state.messages if m.id == order.delivery_message_id)
    if order.delivery_will_lose:
        intel.lose_message(state, msg, by="TBS 通信链",
                           reason="通信检定大失败——命令电文丢失")
        order.delivery_eta = None   # 传达终局：无自动重发（玩家可手动重发=新 Order）
        return [f"⚠ 命令 {order.id} 电文丢失（未送达）"]
    if msg.status.value not in ("in_transit", "filed"):
        order.delivery_eta = None
        return []
    intel.receive_message(state, msg, by=order.responsible_actor_id or "责任岗位",
                          condition=msg.condition)
    order.delivery_eta = None
    order.delivery_confirmed = True
    _event(state, order, OrderEventType.ORDER_DELIVERED,
           order.responsible_actor_id or "", source_ref=msg.id)
    if order.authority_mode == AuthorityMode.EXACT:
        activate_order(state, order)
        return [f"命令 {order.id} 已送达并生效"]
    # INTENT：责任参谋生成执行方案，待指挥官批准
    order.status = OrderStatus.PENDING_APPROVAL
    order.reported_status = "pending_approval"
    if order.order_type == OrderType.LAUNCH_SCOUT:
        order.plan = _generate_scout_plan(state, order)
        _event(state, order, OrderEventType.ORDER_ALTERNATIVE_PROPOSED,
               order.responsible_actor_id or "",
               summary=f"执行方案：{order.plan}")
    return [f"命令 {order.id} 已送达，待批准"]


def activate_order(state, order: Order) -> None:
    if not order.delivery_confirmed:
        raise ValueError("命令尚未经 S2 送达——不能跳过传达直接生效（D11）。")
    if order.status not in (OrderStatus.ISSUED, OrderStatus.PENDING_APPROVAL):
        raise ValueError(f"Order 状态 {order.status.value} 不可激活。")
    order.status = OrderStatus.ACTIVE
    order.reported_status = "awaiting_report"
    order.activated_at = intel.now(state)
    _event(state, order, OrderEventType.ORDER_ACTIVATED,
           order.responsible_actor_id or "")


def approve_order(state, order: Order, by: str = "fletcher") -> None:
    if order.status != OrderStatus.PENDING_APPROVAL:
        raise ValueError(f"Order 状态 {order.status.value} 无待批方案。")
    if order.authority_mode != AuthorityMode.INTENT:
        raise ValueError("EXACT 命令无批准环节。")
    _event(state, order, OrderEventType.ORDER_APPROVED, by, summary="批准执行方案")
    activate_order(state, order)


def _generate_scout_plan(state, order: Order) -> dict:
    """责任参谋（AIR_OFFICER）确定性方案：选机、扇区、燃油可行域。"""
    carrier = state.task_forces[0].carriers[0]
    from src.state import AircraftStatus, AircraftType
    available = len([a for a in carrier.aircraft
                     if a.type == AircraftType.SBD and a.status == AircraftStatus.READY])
    count = min(_PLAN_DEFAULT_AIRCRAFT, available)
    area = (order.parameters.get("search_area") or "")
    direction = _parse_direction(area)
    shortfall = available < _PLAN_DEFAULT_AIRCRAFT
    return {
        "aircraft_count": count,
        "direction": direction,
        "max_range_nm": order.parameters.get("max_range_nm", 200),
        "source_carrier": carrier.name,
        "altitude_ft": 1500,
        "shortfall": shortfall,
    }


_DIRECTION_WORDS = [
    ("northwest", ("northwest", "西北")),
    ("northeast", ("northeast", "东北")),
    ("southwest", ("southwest", "西南")),
    ("southeast", ("southeast", "东南")),
    ("north", ("north", "北")), ("south", ("south", "南")),
    ("east", ("east", "东")), ("west", ("west", "西")),
]


def _parse_direction(text: str, default: str = "north") -> str:
    low = (text or "").lower()
    for key, words in _DIRECTION_WORDS:
        if any(w in low for w in words):
            return key
    return default


def _execute_active(state, order: Order) -> list[str]:
    """S6 执行位：SET_COURSE 转向 / LAUNCH_SCOUT 放飞。效果只在此发生，
    且必须晚于激活的 tick（送达与执行分 tick，命令端点永不变更舰队）。"""
    if order.activated_at is None or order.activated_at >= intel.now(state):
        return []
    if order.order_type == OrderType.SET_COURSE:
        course = order.parameters["course"]
        applied = 0
        for tf in state.task_forces:
            if tf.name in order.target_refs:
                tf.course = course
                applied += 1
        if not applied:
            return _fail_order(state, order, f"目标 {order.target_refs} 不存在")
        return [_complete_order(state, order, "success",
                                f"航向已调整为 {course:03d}°")]
    if order.order_type == OrderType.LAUNCH_SCOUT:
        if order.authority_mode == AuthorityMode.INTENT and order.plan is None:
            return []   # 未批准不执行（理论不可达：INTENT 未到 ACTIVE）
        plan = order.plan or {}
        from src.tools import handle_execute_action
        result = handle_execute_action(state, "launch_scout", {
            "direction": plan.get("direction", "north"),
            "count": plan.get("aircraft_count", _PLAN_DEFAULT_AIRCRAFT),
            "pattern": "sector",
        })
        if result.startswith("Error"):
            return _fail_order(state, order, result)
        outcome = "partial" if plan.get("shortfall") else "success"
        deviations = ["可用机不足，方案缩减编队"] if plan.get("shortfall") else []
        return [_complete_order(state, order, outcome, result,
                                deviations=deviations)]
    return []


def _fail_order(state, order: Order, reason: str) -> list[str]:
    order.status = OrderStatus.FAILED
    order.result = {"outcome": "failed", "effects": [], "deviations": [],
                    "summary": reason, "reported_at": None}
    _event(state, order, OrderEventType.ORDER_FAILED,
           order.responsible_actor_id or "", summary=reason[:80])
    _file_order_report(state, order)
    return [f"命令 {order.id} 执行失败：{reason[:40]}"]


def _complete_order(state, order: Order, outcome: str, summary: str,
                    deviations: list[str] | None = None) -> str:
    order.status = OrderStatus.COMPLETED
    order.result = {"outcome": outcome, "effects": [summary],
                    "deviations": list(deviations or []),
                    "summary": summary, "reported_at": None}
    _event(state, order, OrderEventType.ORDER_COMPLETED,
           order.responsible_actor_id or "", summary=summary[:80])
    _file_order_report(state, order)
    return f"命令 {order.id} 执行完成（{outcome}）"


def complete_order(state, order: Order, *, outcome: str, summary: str,
                   deviations: list[str] | None = None) -> Order:
    """结果回写入口（部分完成不新增状态——status=COMPLETED + result.outcome）。"""
    _complete_order(state, order, outcome, summary, deviations)
    return order


def _file_order_report(state, order: Order) -> None:
    """S2 报告回传：执行结果经通信链延迟送达后才成为指挥官已知事实（D16）。"""
    delay = _ORDER_COMM_DELAY_MIN
    msg = MessageEnvelope(
        sender_id=order.responsible_actor_id or "责任岗位",
        sender_call_sign=f"ORDER {order.id} 执行报告",
        recipient_ids=["fletcher"],
        priority=WorkPriority.URGENT if order.priority == "flash" else WorkPriority.ROUTINE,
        message_kind="report",
        observed_at=intel.now(state),
        raw_text=f"RE {order.id}: {order.result['summary']}",
    )
    intel.file_message(state, msg, by=order.responsible_actor_id or "",
                       reason=f"Order {order.id} 执行报告")
    intel.mark_in_transit(state, msg, by="TBS 通信链")
    msg.transit_eta = intel.now(state) + timedelta(minutes=delay)
    msg.condition = CommCondition.COMPLETE
    order.report_message_id = msg.id


def _maybe_deliver_report(state, order: Order) -> list[str]:
    msg = next((m for m in state.messages if m.id == order.report_message_id), None)
    if msg is None or msg.status.value != "in_transit":
        return []
    if intel.now(state) < (msg.transit_eta or intel.now(state)):
        return []
    intel.receive_message(state, msg, by="fletcher", condition=msg.condition)
    if order.result is not None and order.result.get("reported_at") is None:
        order.result["reported_at"] = intel.now(state).isoformat()
    order.reported_status = order.status.value   # 报告送达 → 指挥官已知
    return [f"命令 {order.id} 执行报告已送达"]


# ── 取消与替代（S5.5）──


def cancel_order(state, order: Order, by: str = "fletcher",
                 reason: str = "") -> None:
    if order.status in (OrderStatus.COMPLETED, OrderStatus.FAILED,
                        OrderStatus.CANCELLED):
        raise ValueError("取消太迟：效果已发生且不可回滚（用新 Order 修改）。")
    if order.result is None or "superseded_by" not in (order.result or {}):
        order.result = {"outcome": "cancelled", "effects": [], "deviations": [],
                        "summary": reason or "指挥官取消", "superseded_by": None}
    order.status = OrderStatus.CANCELLED
    order.reported_status = "cancelled"
    _event(state, order, OrderEventType.ORDER_CANCELLED, by,
           summary=reason or "指挥官取消")


def supersede_order(state, roster: RunRoster, old: Order, new: Order,
                    by: str = "fletcher") -> None:
    """以新 Order 替代旧 Order（等价 issue 时传 supersede_ids）。"""
    issue_order(state, roster, new.id, supersede_ids=[old.id])


# ── S5.2 自然语言草稿 ──

_COURSE_RE = re.compile(r"(?:航向|course)[^0-9]{0,4}(\d{1,3})", re.IGNORECASE)
_RANGE_RE = re.compile(r"(\d{2,4})\s*(?:海里|nm)", re.IGNORECASE)
_COUNT_RE = re.compile(r"(\d{1,2})\s*架")
_SCOUT_WORDS = ("侦察", "搜索", "scout", "patrol", "侦查")


def draft_from_text(state, text: str, *, author: str = "fletcher") -> list[Order]:
    """自然语言 → 可编辑草稿（不签发、不执行；无法确定的字段不猜）。"""
    drafts: list[Order] = []
    if not (text or "").strip():
        return []
    course_m = _COURSE_RE.search(text)
    has_scout = any(w in text.lower() for w in _SCOUT_WORDS)
    if course_m:
        course = int(course_m.group(1))
        if 0 <= course <= 359:
            drafts.append(create_draft(
                state, order_type=OrderType.SET_COURSE,
                target_refs=[state.task_forces[0].name],
                parameters={"course": course},
                commander_intent_text=text.strip(),
                authority_mode=AuthorityMode.EXACT))
    if has_scout:
        range_m = _RANGE_RE.search(text)
        count_m = _COUNT_RE.search(text)
        direction = _parse_direction(text, default="")
        if direction or range_m:
            drafts.append(create_draft(
                state, order_type=OrderType.LAUNCH_SCOUT,
                target_refs=[state.task_forces[0].name],
                parameters={
                    "search_objective": text.strip()[:60],
                    "search_area": f"{direction or '未指明'} {range_m.group(1) + 'nm' if range_m else ''}".strip(),
                    "max_range_nm": int(range_m.group(1)) if range_m else 200,
                    "time_window": "",
                    "constraints": [],
                },
                commander_intent_text=text.strip(),
                authority_mode=AuthorityMode.INTENT))
    return drafts


# ── 玩家可见状态与审计（S5.6）──

_PLAYER_VISIBLE = {"draft", "issued", "pending_approval", "cancelled",
                   "awaiting_report"}


def player_view(state) -> dict:
    """UI 使用的玩家视图：reported_status 与内部 status 分离（§十一）。"""
    out = {}
    for o in state.orders:
        visible = o.reported_status
        if visible == "active":
            visible = "awaiting_report"   # 内部执行态对玩家呈现为等待报告
        out[o.id] = {
            "order_id": o.id,
            "order_type": o.order_type.value,
            "status_visible": visible if visible in _PLAYER_VISIBLE | {"completed", "failed"} else "awaiting_report",
            "reported_status": o.reported_status,
            "intent": o.commander_intent_text,
            "priority": o.priority,
            "responsible_role": o.responsible_role,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
    return out


def order_events(state, order_id: str) -> list[OrderEvent]:
    return [e for e in state.order_events if e.order_id == order_id]


def order_audit(state, order_id: str) -> dict:
    """战后复盘视图：真实状态 + 全部事件 + 传达链（D17/§十三）。"""
    o = get_order(state, order_id)
    msg = next((m for m in state.messages if m.id == o.delivery_message_id), None)
    return {
        "order": {
            "id": o.id,
            "order_type": o.order_type.value,
            "target_refs": list(o.target_refs),
            "parameters": dict(o.parameters),
            "commander_intent_text": o.commander_intent_text,
            "authority_mode": o.authority_mode.value,
            "priority": o.priority,
            "responsible_role": o.responsible_role,
            "responsible_actor_id": o.responsible_actor_id,
            "status": o.status.value,
            "reported_status": o.reported_status,
            "result": o.result,
            "plan": o.plan,
            "cost_policy": o.cost_policy,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        },
        "events": [
            {"at": e.at.isoformat(), "actor": e.actor_id,
             "event_type": e.event_type.value, "summary": e.summary,
             "source_ref": e.source_ref}
            for e in order_events(state, order_id)
        ],
        "delivery": {
            "message_id": o.delivery_message_id,
            "eta": o.delivery_eta.isoformat() if o.delivery_eta else None,
            "lost": o.delivery_will_lose,
            "message_status": msg.status.value if msg else None,
        },
    }
