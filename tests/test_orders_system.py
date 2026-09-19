"""S5 指挥、授权与执行系统测试（S5.0–S5.6，红灯先行）。

覆盖计划 §十五：Order schema/类型化参数/intent 必填/状态机/岗位路由/冲突检查/
不静默覆盖/取消与 superseded_by/部分完成落 result/reported_status 分离；
集成：SET_COURSE 全链/LAUNCH_SCOUT 全链/S2 丢包不 ACTIVE/手动重发不自动建单/
NL 只产草稿/玩家不可见隐藏执行状态/LOG 审计回放。
"""
from datetime import datetime, timedelta

import pytest

from src.orders import service as orders
from src.orders.models import (
    AuthorityMode,
    OrderEventType,
    OrderStatus,
    OrderType,
)
from src.state import GameClock, GameState
from src.staff.roster import load_run_roster


def _state():
    from pathlib import Path
    from src.initial_state import build_initial_state
    return build_initial_state(Path("theaters/coral-sea/scenario.json"))


def _roster():
    return load_run_roster("coral-sea")


def _tick(s, minutes=15, roster=None):
    """管线语义：先推时钟（advance_clock）再执行 orders 步骤。"""
    s.clock.game_time += timedelta(minutes=minutes)
    return orders.process_orders_step(s, minutes, roster=roster or _roster())


def _course_draft(state, course=125, tf="Task Force 17 (TG 17.5)"):
    return orders.create_draft(
        state, order_type=OrderType.SET_COURSE,
        target_refs=[tf], parameters={"course": course},
        commander_intent_text="抢占东偏南阵位，保持对乔马德方向的拦截角。",
        authority_mode=AuthorityMode.EXACT, priority="urgent")


# ── S5.0 契约 ──


def test_order_requires_intent_text():
    with pytest.raises(ValueError):
        orders.create_draft(
            state=_state(), order_type=OrderType.SET_COURSE,
            target_refs=["TF17"], parameters={"course": 90},
            commander_intent_text="   ", authority_mode=AuthorityMode.EXACT)


def test_order_only_supports_exact_and_intent():
    assert set(AuthorityMode) == {AuthorityMode.EXACT, AuthorityMode.INTENT}


def test_order_typed_parameters_validated():
    s = _state()
    with pytest.raises(ValueError):
        orders.create_draft(
            state=s, order_type=OrderType.SET_COURSE, target_refs=["TF17"],
            parameters={"course": 400}, commander_intent_text="转向",
            authority_mode=AuthorityMode.EXACT)
    with pytest.raises(ValueError):
        orders.create_draft(
            state=s, order_type=OrderType.LAUNCH_SCOUT, target_refs=["TF17"],
            parameters={"search_objective": "x"}, commander_intent_text="侦察",
            authority_mode=AuthorityMode.INTENT)
    with pytest.raises(ValueError):
        orders.create_draft(
            state=s, order_type="BOMBARD_SHORE", target_refs=["TF17"],
            parameters={}, commander_intent_text="炮击",
            authority_mode=AuthorityMode.EXACT)


def test_intent_text_immutable_after_issue():
    s = _state()
    o = _course_draft(s)
    original = o.commander_intent_text
    orders.issue_order(s, _roster(), o.id)
    with pytest.raises(ValueError):
        orders.update_draft(s, o.id, commander_intent_text="改主意")
    assert o.commander_intent_text == original  # 原文不可改写


def test_state_machine_legal_and_illegal_transitions():
    s = _state()
    o = _course_draft(s)
    assert o.status == OrderStatus.DRAFT
    orders.issue_order(s, _roster(), o.id)
    assert o.status == OrderStatus.ISSUED
    with pytest.raises(ValueError):
        orders.update_draft(s, o.id, parameters={"course": 200})  # ISSUED 不可原地改
    # EXACT：ISSUED →（送达）ACTIVE；不允许跳过
    with pytest.raises(ValueError):
        orders.activate_order(s, o)
    _tick(s)
    assert o.status == OrderStatus.ACTIVE   # 送达即 ACTIVE（EXACT）


def test_responsible_role_routing_from_roster():
    roster = _roster()
    s = _state()
    o = _course_draft(s)
    orders.issue_order(s, roster, o.id)
    assert o.responsible_role == "NAVIGATOR"
    assert o.responsible_actor_id == "tf17_ops"   # roster.order_routing: NAVIGATOR→STAFF_OPS
    scout = orders.create_draft(
        state=s, order_type=OrderType.LAUNCH_SCOUT, target_refs=["Task Force 17 (TG 17.5)"],
        parameters={"search_objective": "确认米西马方向接触",
                     "search_area": "NW 200nm", "max_range_nm": 200,
                     "time_window": "上午", "constraints": ["避开锋面"]},
        commander_intent_text="在上午窗口内确认敌航母编队位置。",
        authority_mode=AuthorityMode.INTENT)
    orders.issue_order(s, roster, scout.id)
    assert scout.responsible_role == "AIR_OFFICER"
    assert scout.responsible_actor_id == "fitch"


def test_no_responsible_role_order_cannot_activate():
    s = _state()
    roster = _roster()
    roster.order_routing.clear.__self__  # 占位防误改；直接构造缺路由场景
    o = orders.create_draft(
        state=s, order_type=OrderType.SET_COURSE, target_refs=["TF11 (TG 17.8)"],
        parameters={"course": 90}, commander_intent_text="t",
        authority_mode=AuthorityMode.EXACT)
    orders.issue_order(s, roster, o.id)
    # 路由在签发时已定；构造空路由的签发路径（用无路由 roster 副本）
    from dataclasses import replace as dc_replace
    empty = dc_replace(roster, order_routing={})
    o2 = orders.create_draft(
        state=s, order_type=OrderType.SET_COURSE, target_refs=["TF11 (TG 17.8)"],
        parameters={"course": 90}, commander_intent_text="t2",
        authority_mode=AuthorityMode.EXACT)
    with pytest.raises(ValueError):
        orders.issue_order(s, empty, o2.id)
    assert o2.status == OrderStatus.DRAFT


# ── S5.1 冲突检查 ──


def test_conflict_not_silently_overwritten_and_supersede_works():
    s = _state()
    roster = _roster()
    o1 = _course_draft(s, course=125)
    orders.issue_order(s, roster, o1.id)
    _tick(s, roster=roster)   # o1 → ACTIVE
    o2 = _course_draft(s, course=200)
    with pytest.raises(orders.OrderConflict) as exc:
        orders.issue_order(s, roster, o2.id)
    assert exc.value.active_order.id == o1.id          # 冲突提示旧 Order
    assert o1.status == OrderStatus.ACTIVE             # 未被静默覆盖
    # 显式替代：旧单取消并记录 superseded_by；新单可签发（FLASH 也不绕过检查）
    orders.issue_order(s, roster, o2.id, supersede_ids=[o1.id])
    assert o1.status == OrderStatus.CANCELLED
    assert o1.result["superseded_by"] == o2.id
    assert o2.status == OrderStatus.ISSUED
    o3 = _course_draft(s, course=210)
    o3.priority = "flash"
    with pytest.raises(orders.OrderConflict):
        orders.issue_order(s, roster, o3.id)           # 冲突检查不可被 FLASH 绕过


def test_cancel_and_superseded_history_preserved():
    s = _state()
    roster = _roster()
    o1 = _course_draft(s, course=125)
    orders.issue_order(s, roster, o1.id)
    o2 = _course_draft(s, course=200)
    orders.issue_order(s, roster, o2.id, supersede_ids=[o1.id])
    orders.cancel_order(s, o2)
    assert o2.status == OrderStatus.CANCELLED
    # 旧 Order 历史完整保留（事件追加制）
    kinds = [e.event_type for e in orders.order_events(s, o1.id)]
    assert OrderEventType.ORDER_CREATED in kinds
    assert OrderEventType.ORDER_ISSUED in kinds
    assert OrderEventType.ORDER_CANCELLED in kinds


def test_cancel_too_late_rejected_effects_not_rolled_back():
    s = _state()
    roster = _roster()
    o = _course_draft(s, course=125)
    orders.issue_order(s, roster, o.id)
    _tick(s, roster=roster)   # ACTIVE
    _tick(s, roster=roster)   # 执行完成
    assert o.status == OrderStatus.COMPLETED
    with pytest.raises(ValueError):
        orders.cancel_order(s, o)
    tf = next(t for t in s.task_forces if t.name == "Task Force 17 (TG 17.5)")
    assert tf.course == 125                            # 已发生效果不回滚


def test_partial_completion_lands_in_result_not_new_status():
    s = _state()
    result = orders.complete_order(
        s, _course_draft(s), outcome="partial",
        summary="仅完成部分：3/4 架可用",
        deviations=["可用机不足，缩减编队"])
    order = result
    assert order.status == OrderStatus.COMPLETED
    assert order.result["outcome"] == "partial"
    assert not any(m.value == "PARTIAL" for m in OrderStatus)


# ── S5.3 SET_COURSE 纵切 ──


def test_set_course_full_chain():
    s = _state()
    roster = _roster()
    tf = next(t for t in s.task_forces if t.name == "Task Force 17 (TG 17.5)")
    old_course = tf.course
    o = _course_draft(s, course=125)
    orders.issue_order(s, roster, o.id)
    # 命令端点不得直接改舰队状态：签发后航向未变（D9）
    assert tf.course == old_course
    _tick(s, roster=roster)   # 送达 → ACTIVE
    assert tf.course == old_course                     # 仍未变——执行在 Pipeline
    _tick(s, roster=roster)   # Pipeline 执行转向 → COMPLETED
    assert tf.course == 125
    assert o.status == OrderStatus.COMPLETED
    assert o.result["outcome"] == "success"
    # 报告经 S2 回传后才对玩家可见（见 reported_status 测试）


# ── S5.4 LAUNCH_SCOUT 纵切 ──


def test_launch_scout_full_chain_intent_flow():
    s = _state()
    roster = _roster()
    o = orders.create_draft(
        state=s, order_type=OrderType.LAUNCH_SCOUT,
        target_refs=["Task Force 17 (TG 17.5)"],
        parameters={"search_objective": "确认米西马方向接触",
                     "search_area": "NW 200nm", "max_range_nm": 200,
                     "time_window": "上午", "constraints": ["避开锋面"]},
        commander_intent_text="在上午窗口内确认敌航母编队位置。",
        authority_mode=AuthorityMode.INTENT)
    orders.issue_order(s, roster, o.id)
    assert o.status == OrderStatus.ISSUED
    _tick(s, roster=roster)   # 送达 → PENDING_APPROVAL + 方案
    assert o.status == OrderStatus.PENDING_APPROVAL
    assert o.plan and o.plan["aircraft_count"] > 0     # 责任参谋生成方案
    orders.approve_order(s, o, by="fletcher")          # 指挥官批准 → ACTIVE
    assert o.status == OrderStatus.ACTIVE
    carriers = [c for tf in s.task_forces for c in tf.carriers]
    before = sum(len([a for a in c.aircraft if a.status.value == "in_flight"])
                 for c in carriers)
    _tick(s, roster=roster)   # S6 执行：放飞
    after = sum(len([a for a in c.aircraft if a.status.value == "in_flight"])
                for c in carriers)
    assert after > before
    assert o.status == OrderStatus.COMPLETED


def test_launch_scout_shortfall_is_partial():
    """可用机不足 → 方案缩减编队 → 完成时 outcome=partial。"""
    s = _state()
    roster = _roster()
    # 榨干约克城首舰可用的 SBD 到只剩 1 架
    carrier = s.task_forces[0].carriers[0]
    ready = [a for a in carrier.aircraft
             if a.type.value == "SBD" and a.status.value == "ready"]
    for a in ready[1:]:
        a.status = a.status.__class__("maintenance")
    o = orders.create_draft(
        state=s, order_type=OrderType.LAUNCH_SCOUT,
        target_refs=["Task Force 17 (TG 17.5)"],
        parameters={"search_objective": "x", "search_area": "N",
                     "max_range_nm": 200, "time_window": "am", "constraints": []},
        commander_intent_text="侦察", authority_mode=AuthorityMode.INTENT)
    orders.issue_order(s, roster, o.id)
    _tick(s, roster=roster)
    assert o.plan["shortfall"] is True                 # 方案阶段即标注缩减
    orders.approve_order(s, o, by="fletcher")
    _tick(s, roster=roster)
    assert o.status == OrderStatus.COMPLETED
    assert o.result["outcome"] == "partial"


# ── S2 通信边界 ──


def test_comm_loss_order_never_activates_and_manual_resend_is_new_order():
    s = _state()
    roster = _roster()
    o = _course_draft(s, course=125)
    orders.issue_order(s, roster, o.id, force_loss=True)   # 测试注入：S2 检定丢失
    assert o.status == OrderStatus.ISSUED                  # 停在 ISSUED
    for _ in range(6):
        _tick(s, roster=roster)
    assert o.status == OrderStatus.ISSUED                  # 永不 ACTIVE
    assert o.reported_status == "issued"                   # 玩家看到的是已签发/未确认
    # 无自动重发；玩家手动重发 = 新 Order（旧单取消）
    o2 = _course_draft(s, course=125)
    orders.issue_order(s, roster, o2.id, supersede_ids=[o.id], force_loss=False)
    assert o2.id != o.id
    assert o.status == OrderStatus.CANCELLED
    _tick(s, roster=roster)
    assert o2.status == OrderStatus.ACTIVE


def test_delivery_goes_through_s2_message():
    s = _state()
    roster = _roster()
    o = _course_draft(s)
    orders.issue_order(s, roster, o.id)
    assert o.delivery_message_id
    msg = next(m for m in s.messages if m.id == o.delivery_message_id)
    assert msg.message_kind == "order"                     # 命令走 S2 通信链
    assert msg.status.value in ("filed", "in_transit")


# ── S5.2 自然语言草稿 ──


def test_nl_draft_never_executes_and_single_action_split():
    s = _state()
    drafts = orders.draft_from_text(
        s, "航向 095，另外派 4 架侦察机向西北搜索 200 海里确认接触。")
    assert all(d.status == OrderStatus.DRAFT for d in drafts)
    assert len(drafts) == 2                                # 多动作拆分为多个待确认草稿
    assert {d.order_type for d in drafts} == {OrderType.SET_COURSE,
                                              OrderType.LAUNCH_SCOUT}
    course = next(d for d in drafts if d.order_type == OrderType.SET_COURSE)
    assert course.parameters["course"] == 95
    assert course.commander_intent_text                    # 原文保留为 intent
    # 未确认签发前，舰队状态不变
    tf = s.task_forces[0]
    before = tf.course
    _tick(s)
    assert tf.course == before


def test_nl_unparsable_leaves_fields_unknown_not_guessed():
    s = _state()
    drafts = orders.draft_from_text(s, "看着办。")
    assert drafts == []                                    # 无法确定的字段不猜


# ── S5.6 玩家可见状态与审计 ──


def test_reported_status_separated_from_internal_status():
    s = _state()
    roster = _roster()
    o = _course_draft(s, course=125)
    orders.issue_order(s, roster, o.id)
    assert o.reported_status == "issued"
    _tick(s, roster=roster)
    assert o.status == OrderStatus.ACTIVE
    assert o.reported_status == "awaiting_report"          # 玩家不可见隐藏执行状态
    _tick(s, roster=roster)
    assert o.status == OrderStatus.COMPLETED
    assert o.reported_status == "awaiting_report"          # 报告未送达前仍隐藏
    _tick(s, 30, roster=roster)       # 报告经 S2 延迟送达
    assert o.reported_status == "completed"
    view = orders.player_view(s)[o.id]
    assert view["status_visible"] in ("issued", "pending_approval", "draft",
                                      "cancelled", "awaiting_report",
                                      "completed", "failed")


def test_audit_events_allow_full_replay():
    s = _state()
    roster = _roster()
    o = _course_draft(s, course=125)
    orders.issue_order(s, roster, o.id)
    _tick(s, roster=roster)
    _tick(s, roster=roster)
    events = orders.order_events(s, o.id)
    kinds = [e.event_type for e in events]
    assert kinds[:3] == [OrderEventType.ORDER_CREATED, OrderEventType.ORDER_ISSUED,
                         OrderEventType.ORDER_DELIVERED]
    assert OrderEventType.ORDER_ACTIVATED in kinds
    assert OrderEventType.ORDER_COMPLETED in kinds
    # 审计能回答：谁下令、为何下令、谁负责、何时送达、最终结果
    audit = orders.order_audit(s, o.id)
    assert audit["order"]["commander_intent_text"]
    assert audit["order"]["responsible_actor_id"]
    assert audit["delivery"]["message_id"] == o.delivery_message_id


def test_cost_policy_placeholder_only():
    s = _state()
    o = _course_draft(s)
    assert o.cost_policy is None                           # AP 专项未定：仅占位


def test_pipeline_has_orders_step():
    from src.pipeline import build_default_pipeline
    assert any(step.name == "process_orders" for step in build_default_pipeline().steps)


# ── S5.6 API 层 ──


def test_orders_api_end_to_end():
    from pathlib import Path
    from src.initial_state import build_initial_state
    import server as server_module
    from fastapi.testclient import TestClient

    server_module.game_state = build_initial_state(Path("theaters/coral-sea/scenario.json"))
    from src.staff.roster import set_active_roster
    roster = _roster()
    server_module.staff_roster = roster
    set_active_roster(roster)
    client = TestClient(server_module.app)

    catalog = client.get("/orders/catalog").json()["actions"]
    assert {a["action_type"] for a in catalog} == {"SET_COURSE", "LAUNCH_SCOUT"}

    # 表单创建 → 签发 → ADVANCE 推进（送达+执行）
    created = client.post("/orders", json={
        "order_type": "SET_COURSE",
        "target_refs": ["Task Force 17 (TG 17.5)"],
        "parameters": {"course": 125},
        "commander_intent_text": "抢占东南阵位。",
        "authority_mode": "exact", "priority": "urgent",
    })
    assert created.status_code == 200
    oid = created.json()["order"]["id"]
    assert created.json()["order"]["status"] == "draft"

    issue = client.post(f"/orders/{oid}/issue", json={"supersede_ids": []})
    assert issue.status_code == 200
    assert issue.json()["order"]["status"] == "issued"

    # 玩家视图：签发后可见 issued；内部执行态隐藏
    listing = client.get("/orders").json()["orders"]
    view = next(o for o in listing if o["order_id"] == oid)
    assert view["status_visible"] == "issued"

    # 冲突 → 409 带在位命令（在位=ISSUED/ACTIVE；FLASH 也不绕过）
    conflict = client.post("/orders", json={
        "order_type": "SET_COURSE",
        "target_refs": ["Task Force 17 (TG 17.5)"],
        "parameters": {"course": 210},
        "commander_intent_text": "改航向。",
        "authority_mode": "exact",
    })
    cid = conflict.json()["order"]["id"]
    resp = client.post(f"/orders/{cid}/issue", json={"supersede_ids": []})
    assert resp.status_code == 409
    assert resp.json()["detail"]["active_order"]["id"] == oid

    server_module.pipeline.execute(server_module.game_state, 15)   # 送达+激活
    server_module.pipeline.execute(server_module.game_state, 15)   # 执行
    tf = next(t for t in server_module.game_state.task_forces
              if t.name == "Task Force 17 (TG 17.5)")
    assert tf.course == 125
    audit = client.get(f"/orders/{oid}/audit").json()
    kinds = [e["event_type"] for e in audit["events"]]
    assert "ORDER_COMPLETED" in kinds

    # 自然语言 → 草稿（不执行）
    nl = client.post("/orders/draft", json={"text": "航向 075。"})
    assert nl.status_code == 200
    drafts = nl.json()["drafts"]
    assert drafts and drafts[0]["status"] == "draft"
    assert drafts[0]["parameters"]["course"] == 75
    tf2 = server_module.game_state.task_forces[0]
    assert tf2.course == 125                              # 草稿不执行


def test_orders_api_cancel_and_too_late():
    from pathlib import Path
    from src.initial_state import build_initial_state
    import server as server_module
    from fastapi.testclient import TestClient
    from src.staff.roster import set_active_roster

    server_module.game_state = build_initial_state(Path("theaters/coral-sea/scenario.json"))
    roster = _roster()
    server_module.staff_roster = roster
    set_active_roster(roster)
    client = TestClient(server_module.app)

    oid = client.post("/orders", json={
        "order_type": "SET_COURSE",
        "target_refs": ["Task Force 17 (TG 17.5)"],
        "parameters": {"course": 300},
        "commander_intent_text": "转向北。",
        "authority_mode": "exact",
    }).json()["order"]["id"]
    client.post(f"/orders/{oid}/issue", json={})
    cancelled = client.post(f"/orders/{oid}/cancel")
    assert cancelled.status_code == 200
    again = client.post(f"/orders/{oid}/cancel")
    assert again.status_code == 400                        # 重复取消拒绝


def test_same_seed_order_delivery_replay():
    """同种子回放：同一局面+同一种子 ⇒ 相同通信检定序列与相同的命令生命周期。"""
    from pathlib import Path
    from src.initial_state import build_initial_state

    def run_once():
        s = build_initial_state(Path("theaters/coral-sea/scenario.json"))
        s.clock.game_time = datetime(1942, 5, 8, 6, 0)
        roster = _roster()
        o = _course_draft(s, course=125)
        orders.issue_order(s, roster, o.id)
        trace = [(o.status.value, o.reported_status)]
        for _ in range(4):
            _tick(s, roster=roster)
            trace.append((o.status.value, o.reported_status))
        checks = [(c.check_type, c.random_seed, c.final_roll, c.degree)
                  for c in s.check_records
                  if c.check_type == "COMMUNICATION_CHECK"]
        return trace, checks, s.task_forces[0].course

    t1, c1, course1 = run_once()
    t2, c2, course2 = run_once()
    assert t1 == t2, "同种子下命令生命周期应逐 tick 一致"
    assert c1 == c2, "同种子下通信检定序列应逐字段一致（CheckRecord 可回放）"
    assert course1 == course2
    assert course1 == 125
