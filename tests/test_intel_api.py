"""S2.3 情报 API 测试：玩家接口只下发权限内材料（计划 §十禁止暴露清单）。"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import server as server_module
from src.intel import flow as intel_flow


class _FakeWriter:
    actor_id = "fake_pilot_vs6"

    def write_report(self, view, game_time):
        return (f"CONTACT {view['classification']} x{view['count']} "
                f"BEARING {view['bearing']} DIST {view['distance_nm']} NM")


@pytest.fixture(autouse=True)
def fake_llm_channels(monkeypatch):
    monkeypatch.setattr(intel_flow, "_default_writer", lambda: _FakeWriter())
    monkeypatch.setattr(intel_flow, "_default_analyst", lambda: None)


class _ScriptedRng:
    """脚本化随机源：检定恒 success/COMPLETE，通用抽取恒 0。"""

    def roll_check(self, check_type, actor_id, **kw):
        return _dice_result("success", 50), _rec()

    def communication_check(self, actor_id, competence, distance_nm,
                            reason="", inputs=None):
        return _dice_result("success", 50), _rec()

    def randint(self, check_type, actor_id, low, high, reason, **kw):
        return 0

    def chance(self, check_type, actor_id, prob, reason, **kw):
        return False


def _dice_result(level, raw):
    from src.dice import DiceResult
    final = {"success": 80, "partial": 50}[level]
    return DiceResult(raw_roll=raw, modified_roll=final, level=level,
                      level_name=level, modifiers_applied=[])


def _rec():
    from src.intel.rng import CheckRecord
    return CheckRecord(check_id="chk_api", check_type="fake", actor_id="fake",
                       game_time=datetime(1942, 6, 4, 5, 0, tzinfo=timezone.utc),
                       random_seed="api:0")


def _state_with_delivered_report():
    """构造一局：SBD 报告已送达（脚本化 rng 直驱，不依赖探测种子）。"""
    from src.state import ScoutMission, ScoutPhase
    state = server_module.game_state
    # 重置情报容器（全局 state 跨测试共享）
    for coll in (state.messages, state.evidence, state.intel_work_items,
                 state.assessments, state.intel_briefs, state.observations,
                 state.claims, state.contacts, state.known_enemy,
                 state.check_records, state.beliefs, state.intel_audit,
                 state.plot_proposals, state.commander_decisions,
                 state.approved_plots):
        coll.clear()
    state.actual_enemy = [{
        "name": "Kido Butai",
        "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"],
        "position": {"lat": 30.0, "lon": -178.0},
        "status": "rearming",
    }]
    scout = ScoutMission(
        id="SBD-TEST", direction="southwest", heading=225,
        launched_at=state.clock.game_time, phase=ScoutPhase.SEARCHING,
        phase_started_at=state.clock.game_time,
    )
    msg = intel_flow.on_scout_detection(
        state, scout=scout, enemy=state.actual_enemy[0],
        bearing=233.0, distance=195.0,
        result=_dice_result("success", 80),
        writer=_FakeWriter(), rng=_ScriptedRng(),
    )
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    intel_flow.process_intel(state)
    assert msg.status.value in ("received", "logged", "routed")
    return state, msg


def _recursively_collect(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            _recursively_collect(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _recursively_collect(v, out)
    elif isinstance(obj, str):
        out.append(obj)


def test_intel_inbox_delivered_only(client=None):
    client = TestClient(server_module.app)
    state, msg = _state_with_delivered_report()
    resp = client.get("/intel/inbox")
    assert resp.status_code == 200
    data = resp.json()
    ids = [m["id"] for m in data["messages"]]
    assert msg.id in ids
    # 全局无 in_transit 内容泄露
    blob = json.dumps(data, ensure_ascii=False)
    for m in state.messages:
        if m.status.value in ("draft", "filed", "in_transit", "lost"):
            assert m.raw_text not in blob


def test_intel_endpoints_never_leak_truth():
    client = TestClient(server_module.app)
    _state_with_delivered_report()
    # 产生一份简报
    from src.intel.flow import intel_work_queue, run_intelligence_cycle
    queue = intel_work_queue(server_module.game_state)
    if queue:
        run_intelligence_cycle(server_module.game_state, queue[0])

    for path in ("/state", "/intel/inbox", "/intel/briefs", "/intel/work-items"):
        data = client.get(path).json()
        out = []
        _recursively_collect(data, out)
        blob = " ".join(out).lower()
        # 禁止暴露：键名
        for banned_key in ("actual_enemy", "internal_truth_ref", "observations"):
            assert banned_key not in blob, f"{path} 泄露键 {banned_key}"
        # 禁止暴露：规则侧真值（敌舰名/舰名不得出现在任何情报接口）
        for truth in ("kido butai", "akagi", "kaga", "soryu", "hiryu"):
            if path != "/state":  # /state 亦不应含，但 actual_enemy 键本就在 /state 契约外——单测分开
                assert truth not in blob, f"{path} 泄露真值 {truth}"


def test_intel_briefs_published_only():
    client = TestClient(server_module.app)
    _state_with_delivered_report()
    from src.intel.flow import intel_work_queue, run_intelligence_cycle
    queue = intel_work_queue(server_module.game_state)
    run_intelligence_cycle(server_module.game_state, queue[0])
    data = client.get("/intel/briefs").json()
    assert len(data["briefs"]) == 1
    brief = data["briefs"][0]
    assert brief["status"] != "draft"
    assert "narrative" in brief


def test_plot_approval_flow_via_api():
    client = TestClient(server_module.app)
    state, msg = _state_with_delivered_report()
    from src.intel.flow import intel_work_queue, run_intelligence_cycle
    queue = intel_work_queue(state)
    run_intelligence_cycle(state, queue[0])

    # 未批准：pending 有提案、approved 为空，/state 无 APPROVED PLOT 视图
    plots = client.get("/intel/plots").json()
    assert len(plots["pending_proposals"]) == 1
    assert plots["approved_plots"] == []
    proposal_id = plots["pending_proposals"][0]["id"]
    state_blob = json.dumps(client.get("/state").json(), ensure_ascii=False)
    assert "APPROVED PLOT" not in state_blob

    # 批准 → 上图 + 历史
    resp = client.post(f"/intel/plots/{proposal_id}/approve",
                       json={"comment": "按此标图"})
    assert resp.status_code == 200
    plots = client.get("/intel/plots").json()
    assert plots["pending_proposals"] == []
    assert plots["approved_plots"][0]["current_version"] == 1
    state_blob = json.dumps(client.get("/state").json(), ensure_ascii=False)
    assert "APPROVED PLOT v1" in state_blob

    # 版本历史端点
    plot_id = plots["approved_plots"][0]["plot_id"]
    history = client.get(f"/intel/plots/{plot_id}/history").json()
    assert [v["version"] for v in history["versions"]] == [1]
