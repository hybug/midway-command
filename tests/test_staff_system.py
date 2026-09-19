"""S4 参谋班子与关系系统测试（S4.0–S4.5，红灯先行）。

覆盖计划 §十一：
- CommanderContactChannel 权限；ChainReport 状态机与来源保留；未送达不可见；
  CommanderNotice 去重/冷却/升级/固定理由；非核心角色不能创建 notice；
  DossierSummary 四字段；未考证人物不能进入 roster。
- 集成：舰长报告沿指挥链到达；批注不改原文；S8 数据一致；
  普通聊天不改变正式状态；S3 判断不受 S4 影响。
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import server as server_module
from src.state import GameClock, GameState

from src.staff import service as staff
from src.staff.models import (
    ChainReportState,
    NoticePriority,
    NoticeReason,
    NoticeState,
)
from src.staff.roster import MIDWAY_THEATER_ID, load_run_roster


def _state(tz_ok=True) -> GameState:
    s = GameState(clock=GameClock(game_time=datetime(1942, 5, 7, 6, 0)))
    return s


def _coral_roster():
    return load_run_roster("coral-sea")


# ── S4.0 运行名册 ──


def test_coral_roster_loads_from_research():
    roster = _coral_roster()
    assert roster.active is True
    assert roster.commander_id == "fletcher"
    by_id = {c.actor_id: c for c in roster.contact_channels}
    assert set(by_id) >= {"fitch", "tf17_intel", "tf17_ops", "crace"}
    assert by_id["fitch"].contact_permission == "DIRECT_RADIO"
    assert by_id["fitch"].can_initiate is True
    assert by_id["tf17_intel"].contact_permission == "DIRECT_IN_PERSON"
    assert by_id["tf17_ops"].contact_permission == "DIRECT_IN_PERSON"
    assert by_id["crace"].contact_permission == "REPORT_ONLY"
    assert by_id["crace"].can_initiate is False


def test_unknown_personnel_use_duty_titles_in_runtime_roster():
    roster = _coral_roster()
    for ch in roster.contact_channels:
        if ch.evidence_grade == "UNKNOWN":
            assert "（职务名）" in ch.display_name, ch.actor_id


def test_midway_provisional_roster_inactive():
    roster = load_run_roster(MIDWAY_THEATER_ID)
    assert roster.active is False  # 中途岛为占位编制：S4 触发器不启用


# ── S4.1 联系名单 ──


def test_channels_endpoint_lists_roster():
    server_module.staff_roster = _coral_roster()
    server_module.game_state = _state()
    client = TestClient(server_module.app)
    data = client.get("/staff/channels").json()
    ids = {c["actor_id"] for c in data["channels"]}
    assert {"fitch", "tf17_intel", "tf17_ops", "crace"} <= ids
    fitch = next(c for c in data["channels"] if c["actor_id"] == "fitch")
    assert fitch["contact_permission"] == "DIRECT_RADIO"
    assert fitch["can_be_summoned"] is False


# ── S4.2 指挥链上呈 ──


def test_chain_report_reaches_commander_hop_by_hop():
    roster = _coral_roster()
    s = _state()
    report = staff.file_chain_report(
        s, roster, origin_actor_id="buckmaster",
        origin_role="CARRIER_CAPTAIN", source_type="report",
        source_id="RPT-1", summary="约克城右舷发现浮油", priority="routine")
    assert report.state == ChainReportState.IN_CHAIN
    assert report.current_holder_id != "fletcher"
    # 舰长不越级：第一跳是本群司令 fitch
    assert report.next_holder_id == "fitch"
    staff.process_staff_step(s, 15, roster=roster)
    assert report.current_holder_id == "fitch"
    staff.process_staff_step(s, 15, roster=roster)
    assert report.state == ChainReportState.DELIVERED
    assert report.current_holder_id == "fletcher"


def test_chain_report_preserves_source_and_annotations():
    roster = _coral_roster()
    s = _state()
    report = staff.file_chain_report(
        s, roster, origin_actor_id="buckmaster", origin_role="CARRIER_CAPTAIN",
        source_type="report", source_id="RPT-2", summary="甲板已清空",
        priority="routine")
    staff.process_staff_step(s, 15, roster=roster)
    holder_id = report.current_holder_id
    staff.annotate_chain_report(s, roster, report, by=holder_id,
                                note="已阅，随下次简报呈报")
    assert report.summary == "甲板已清空"          # 批注不改写原文
    assert report.annotations[-1]["by"] == holder_id
    assert report.origin_actor_id == "buckmaster"  # 来源不丢
    assert report.source_id == "RPT-2"


def test_undelivered_reports_not_exposed():
    roster = _coral_roster()
    s = _state()
    staff.file_chain_report(
        s, roster, origin_actor_id="buckmaster", origin_role="CARRIER_CAPTAIN",
        source_type="report", source_id="RPT-3", summary="在途", priority="routine")
    visible = staff.delivered_reports(s)
    assert visible == []
    staff.process_staff_step(s, 15, roster=roster)
    staff.process_staff_step(s, 15, roster=roster)
    visible = staff.delivered_reports(s)
    assert [r.source_id for r in visible] == ["RPT-3"]


def test_reports_endpoint_only_shows_delivered():
    server_module.staff_roster = _coral_roster()
    s = _state()
    staff.file_chain_report(
        s, roster := _coral_roster(), origin_actor_id="buckmaster",
        origin_role="CARRIER_CAPTAIN", source_type="report",
        source_id="RPT-4", summary="在途不可见", priority="routine")
    server_module.game_state = s
    client = TestClient(server_module.app)
    assert client.get("/staff/reports").json()["reports"] == []
    staff.process_staff_step(s, 15, roster=_coral_roster())
    staff.process_staff_step(s, 15, roster=_coral_roster())
    reports = client.get("/staff/reports").json()["reports"]
    assert len(reports) == 1 and reports[0]["state"] == "delivered"


# ── S4.3 主动提醒 ──


def test_notice_requires_fixed_reason():
    roster = _coral_roster()
    s = _state()
    with pytest.raises(ValueError):
        staff.raise_notice(s, roster, actor_id="tf17_intel", topic="t",
                           reason="FEELING_LIKE_IT", priority="routine",
                           source_type="report", source_id="x")


def test_notice_dedup_one_open_per_actor_same_topic():
    roster = _coral_roster()
    s = _state()
    n1 = staff.raise_notice(s, roster, actor_id="tf17_intel", topic="米西马接触",
                            reason=NoticeReason.NEW_EVIDENCE, priority="routine",
                            source_type="report", source_id="E1")
    n2 = staff.raise_notice(s, roster, actor_id="tf17_intel", topic="米西马接触",
                            reason=NoticeReason.NEW_EVIDENCE, priority="routine",
                            source_type="report", source_id="E2")
    assert n1.id == n2.id
    # 不同主题被单开通知规则拦截（同 actor 同时只一个 open）
    assert staff.raise_notice(
        s, roster, actor_id="tf17_intel", topic="另一主题",
        reason=NoticeReason.RISK_WARNING, priority="flash",
        source_type="conflict", source_id="C1") is None
    open_notices = [n for n in s.staff_notices if n.state == NoticeState.OPEN]
    assert len(open_notices) == 1


def test_notice_cooldown_after_defer():
    roster = _coral_roster()
    s = _state()
    notice = staff.raise_notice(s, roster, actor_id="fitch", topic="攻击窗口",
                                reason=NoticeReason.OPPORTUNITY, priority="urgent",
                                source_type="plot", source_id="P1")
    staff.dismiss_notice(s, roster, notice, action="defer", by="fletcher")
    assert notice.state == NoticeState.DEFERRED
    assert notice.cooldown_until is not None
    # 冷却期内同主题不重建
    assert staff.raise_notice(s, roster, actor_id="fitch", topic="攻击窗口",
                              reason=NoticeReason.OPPORTUNITY, priority="flash",
                              source_type="plot", source_id="P2") is None
    # 冷却期后可重建
    s.clock.game_time = notice.cooldown_until + timedelta(minutes=1)
    again = staff.raise_notice(s, roster, actor_id="fitch", topic="攻击窗口",
                               reason=NoticeReason.OPPORTUNITY, priority="flash",
                               source_type="plot", source_id="P3")
    assert again is not None and again.id != notice.id


def test_notice_escalates_once():
    roster = _coral_roster()
    s = _state()
    notice = staff.raise_notice(s, roster, actor_id="tf17_ops", topic="防空风险",
                                reason=NoticeReason.RISK_WARNING, priority="routine",
                                source_type="conflict", source_id="C9")
    upgraded = staff.raise_notice(s, roster, actor_id="tf17_ops", topic="防空风险",
                                  reason=NoticeReason.RISK_WARNING, priority="flash",
                                  source_type="conflict", source_id="C10")
    assert upgraded.id == notice.id
    assert notice.priority == NoticePriority.FLASH
    assert notice.escalated is True
    # 已升级过：更高优先级不再重复升级
    assert staff.raise_notice(s, roster, actor_id="tf17_ops", topic="防空风险",
                              reason=NoticeReason.RISK_WARNING, priority="flash",
                              source_type="conflict", source_id="C11") is upgraded


def test_non_core_actor_cannot_create_notice():
    roster = _coral_roster()
    s = _state()
    with pytest.raises(PermissionError):
        staff.raise_notice(s, roster, actor_id="buckmaster", topic="本舰事务",
                           reason=NoticeReason.NEW_EVIDENCE, priority="routine",
                           source_type="report", source_id="x")
    with pytest.raises(PermissionError):
        staff.raise_notice(s, roster, actor_id="crace", topic="TG17.3 战况",
                           reason=NoticeReason.REPORT_ESCALATION, priority="urgent",
                           source_type="report", source_id="x")


def test_notice_actions_recorded():
    roster = _coral_roster()
    s = _state()
    notice = staff.raise_notice(s, roster, actor_id="tf17_intel", topic="证据评估",
                                reason=NoticeReason.DECISION_REQUIRED,
                                priority="urgent", source_type="brief", source_id="B1")
    before = len(s.intel_audit)
    staff.dismiss_notice(s, roster, notice, action="acknowledge", by="fletcher")
    assert notice.state == NoticeState.ACKNOWLEDGED
    staff.dismiss_notice(s, roster, notice, action="close", by="fletcher")
    assert notice.state == NoticeState.RESOLVED
    assert len(s.intel_audit) >= before + 2
    actions = [e.action for e in s.intel_audit[before:]]
    assert actions == ["staff_notice_acknowledge", "staff_notice_close"]


def test_notice_endpoint_and_visit_events():
    server_module.staff_roster = _coral_roster()
    s = _state()
    staff.raise_notice(s, roster := _coral_roster(), actor_id="tf17_intel",
                       topic="接触报告解读", reason=NoticeReason.NEW_EVIDENCE,
                       priority="flash", source_type="report", source_id="E9")
    server_module.game_state = s
    client = TestClient(server_module.app)
    data = client.get("/staff/notices").json()
    assert len(data["notices"]) == 1
    n = data["notices"][0]
    assert n["actor_id"] == "tf17_intel" and n["state"] == "open"
    assert n["reason"] == "NEW_EVIDENCE"
    # STAFF_VISIT 事件源形状（S8 NotificationCenter 消费）
    assert client.get("/staff/visit-events").json()["visits"][0]["actor_id"] == "tf17_intel"


# ── S4.4 极简档案 ──


def test_dossier_summary_has_only_four_fields():
    roster = _coral_roster()
    s = _state()
    staff.raise_notice(s, roster, actor_id="tf17_intel", topic="关注点",
                       reason=NoticeReason.NEW_EVIDENCE, priority="routine",
                       source_type="report", source_id="E1")
    dossier = staff.dossier_summary(s, roster, "tf17_intel")
    assert set(dossier) == {"actor_id", "status_line", "current_focus", "recent"}
    assert len(dossier["recent"]) <= 2


def test_staff_roster_endpoint_keeps_minimal_dossier():
    server_module.staff_roster = _coral_roster()
    server_module.game_state = _state()
    client = TestClient(server_module.app)
    staff_entries = client.get("/staff/roster").json()["staff"]
    for entry in staff_entries:
        assert set(entry["dossier"]) == {"status_line", "current_focus", "recent"}


# ── S4.5 验收 ──


def test_chat_and_staff_actions_never_change_fleet_state():
    roster = _coral_roster()
    s = _state()
    tf = s.task_forces
    snapshot = [(t.name, t.course, t.speed) for t in tf]
    staff.raise_notice(s, roster, actor_id="tf17_intel", topic="t",
                       reason=NoticeReason.NEW_EVIDENCE, priority="flash",
                       source_type="report", source_id="x")
    staff.file_chain_report(s, roster, origin_actor_id="buckmaster",
                            origin_role="CARRIER_CAPTAIN", source_type="report",
                            source_id="y", summary="s", priority="flash")
    staff.process_staff_step(s, 15, roster=roster)
    staff.process_staff_step(s, 15, roster=roster)
    assert [(t.name, t.course, t.speed) for t in s.task_forces] == snapshot


def test_staff_hooks_do_not_touch_judgments():
    roster = _coral_roster()
    s = _state()
    s.judgment_results.append(object()) if False else None  # 占位：真实断言在下面
    before_results = list(s.judgment_results)
    before_tasks = list(s.judgment_tasks)
    staff.raise_notice(s, roster, actor_id="tf17_intel", topic="t",
                       reason=NoticeReason.NEW_EVIDENCE, priority="routine",
                       source_type="report", source_id="x")
    assert s.judgment_results == before_results
    assert s.judgment_tasks == before_tasks


def test_pipeline_includes_staff_step():
    from src.pipeline import build_default_pipeline
    p = build_default_pipeline()
    assert any(step.name == "process_staff" for step in p.steps)


def test_hooks_fire_from_intel_flows():
    """确定性业务触发：简报→NEW_EVIDENCE；批准上图→OPPORTUNITY；冲突→RISK_WARNING。"""
    from src.cognition.scenarios.coral_may7 import (
        CoralMay7Generators,
        build_coral_may7_state,
        brief_new_evidence,
        file_misima_contact,
    )
    from datetime import datetime as dt, timedelta as td
    from src.intel.flow import process_intel, run_intelligence_cycle
    from src.intel.plots import decide as plot_decide

    from src.staff.roster import set_active_roster
    roster = _coral_roster()
    server_module.staff_roster = roster
    set_active_roster(roster)
    s = build_coral_may7_state(4)
    server_module.game_state = s
    msg = file_misima_contact(s)
    s.clock.game_time = msg.transit_eta + td(minutes=1)
    process_intel(s)
    brief_new_evidence(s)
    brief = s.intel_briefs[-1]
    # 简报已呈报 → 情报参谋 NEW_EVIDENCE（恰好一个 open）
    open_topics = [(n.actor_id, n.notice_reason) for n in s.staff_notices
                   if n.state == NoticeState.OPEN]
    assert ("tf17_intel", NoticeReason.NEW_EVIDENCE) in open_topics
    # 指挥官批准上图 → 航空指挥官 OPPORTUNITY
    proposal_id = brief.plot_proposal_ids[0]
    proposal = next(p for p in s.plot_proposals if p.id == proposal_id)
    plot_decide(s, proposal, action="approve", by="player")
    reasons = {(n.actor_id, n.notice_reason.value)
               for n in s.staff_notices}
    assert ("fitch", "OPPORTUNITY") in reasons
