"""S8 UI.6 S3/S4 联动接口测试：指挥官反馈端点 + 转述入口移除（AS.1/R3）。

验收：
- 玩家转述公开入口已删除（/staff/relay 与 /staff/relays 均 410）
- 指挥官反馈：经端点落记忆（不改写原结果，§8.3）
"""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import server as server_module
from src.cognition.scenarios.coral_may7 import (
    CoralMay7Generators,
    build_coral_may7_state,
    brief_new_evidence,
    file_misima_contact,
    staff_judgments_misima,
)
from src.intel.flow import process_intel
from src.state import GameClock, GameState


def _ready_state():
    s = build_coral_may7_state(4)
    msg = file_misima_contact(s)
    s.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(s)
    brief_new_evidence(s)
    outcomes = staff_judgments_misima(s, generators=CoralMay7Generators())
    return s, outcomes


def test_player_relay_removed_public_bypass():
    """AS.1/R3：玩家转述不再存在公开旁路（下级信息按指挥链上呈，S4）。"""
    s, outcomes = _ready_state()
    server_module.game_state = s
    client = TestClient(server_module.app)
    result_id = outcomes["tf17_intel"]["result"].id
    resp = client.post("/staff/relay", json={
        "from_result_id": result_id,
        "to_actor_id": "fitch",
        "note": "情报参谋认为证据可靠性存疑",
    })
    assert resp.status_code == 410
    assert client.get("/staff/relays").status_code == 410
    # 转述不产生任何审计条目（无 player_relay 动作）
    assert all(e.action != "player_relay" for e in s.intel_audit)


def test_feedback_endpoint_updates_memory_not_result():
    s, outcomes = _ready_state()
    server_module.game_state = s
    client = TestClient(server_module.app)
    result = outcomes["fitch"]["result"]
    before = result.model_dump()
    resp = client.post(f"/judgment/results/{result.id}/feedback", json={
        "decision": "approve", "note": "航空判断采纳"})
    assert resp.status_code == 200
    assert result.model_dump() == before
    mem = next(m for m in s.judgment_memories if m.result_id == result.id)
    assert mem.commander_decision == "approve"
    assert client.post(f"/judgment/results/{result.id}/feedback",
                       json={"decision": "praise"}).status_code == 400
