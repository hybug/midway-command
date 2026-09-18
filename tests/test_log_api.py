"""S8 UI.5 LOG 接口测试（红灯先行）：统一时间线 + 认知/事实误差分离复盘。

验收（s8-ui-ux-system-plan.md Phase UI.5 / M8.6）：
- TIMELINE：电报/判断/批准/命令/OTC/S4 冲突统一时间线（旧判断不被覆盖）
- ORDERS：命令链（谁批准/驳回、何时、对什么）
- AFTER ACTION：证据—判断—决议因果链 + 认知错误 vs 事实误差 分离
- 真值字符串不进任何 LOG 下发负载（D11：只出误差结论，不出真值）
"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import server as server_module
from src.cognition.scenarios.coral_may7 import (
    TRUE_COVER_GROUP,
    CoralMay7Generators,
    build_coral_may7_state,
    brief_new_evidence,
    commander_feedback,
    file_misima_contact,
    staff_judgments_misima,
)
from src.cognition.errors import after_action_error_report
from src.intel.flow import process_intel
from src.intel.plots import decide
from src.state import GameClock, GameState, Position

NOW = datetime(1942, 5, 7, 10, 0, tzinfo=timezone.utc)


def _populated_state():
    s = build_coral_may7_state(4)
    msg = file_misima_contact(s)
    s.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(s)
    brief_new_evidence(s)
    outcomes = staff_judgments_misima(s, generators=CoralMay7Generators())
    proposal = s.plot_proposals[0]
    decide(s, proposal, action="approve", by="player", comment="按此标图")
    commander_feedback(s, "tf17_intel", outcomes["tf17_intel"]["result"].id,
                       "approve", note="判断采纳")
    return s, outcomes


def test_timeline_aggregates_all_event_kinds():
    s, _ = _populated_state()
    server_module.game_state = s
    client = TestClient(server_module.app)
    events = client.get("/log/timeline").json()["events"]
    kinds = {e["kind"] for e in events}
    assert {"message", "judgment", "plot_decision", "commander_feedback"} <= kinds
    # 时间升序（统一时间线）
    times = [e["at"] for e in events if e["at"]]
    assert times == sorted(times)
    # 旧判断不被覆盖：所有结果都在时间线
    assert {e["ref_id"] for e in events if e["kind"] == "judgment"} \
        == {r.id for r in s.judgment_results}


def test_after_action_separates_cognition_and_factual_errors():
    s, outcomes = _populated_state()
    server_module.game_state = s
    client = TestClient(server_module.app)
    data = client.get("/log/after-action").json()
    assert data["chains"]                                  # 标图链保留
    report = data["error_report"]
    by_actor = {r["actor_id"]: r for r in report}
    assert "tf17_intel" in by_actor
    row = by_actor["tf17_intel"]
    assert {"cognitive_error_type", "cognitive_error_severity",
            "factual_error_type", "factual_error_severity"} <= set(row)
    # 真值字符串不进 LOG 负载（D11：只出误差结论）
    import json
    blob = json.dumps(data, ensure_ascii=False).lower()
    for banned in ("shokaku", "zuikaku", "cv_a", "cv_b", "actual_enemy",
                   "internal_truth_ref"):
        assert banned not in blob, f"LOG 下发泄露真值 {banned}"


def test_timeline_includes_otc_and_s4_conflict_events():
    from src.cognition.scenarios.coral_may8 import promote_fitch_otc
    s, _ = _populated_state()
    promote_fitch_otc(s)
    server_module.game_state = s
    client = TestClient(server_module.app)
    events = client.get("/log/timeline").json()["events"]
    otc = [e for e in events if e["kind"] == "otc_change"]
    assert otc and otc[0]["ref_id"] == "fitch"
    # S4 冲突事件（v0 桩：无引擎时为空，但字段契约在）
    assert "s4_events" in client.get("/log/timeline").json()
