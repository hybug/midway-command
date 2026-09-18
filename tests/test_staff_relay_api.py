"""S8 UI.6 S3/S4 联动接口测试（红灯先行）：玩家转述链 + 指挥官反馈端点。

验收：
- 玩家转述：记录转述者/被转述者/内容来源（M8.5.6 转述来源链），
  被转述 NPC 不因此获得越权信息（只收到自然语言摘要）
- 指挥官反馈：经端点落记忆（不改写原结果，§8.3）
- 分歧/来访事件：字段契约在（S4 引擎未实施，前端桩供给）
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


def test_player_relay_records_chain_and_respects_privacy():
    s, outcomes = _ready_state()
    server_module.game_state = s
    client = TestClient(server_module.app)
    result_id = outcomes["tf17_intel"]["result"].id
    resp = client.post("/staff/relay", json={
        "from_result_id": result_id,
        "to_actor_id": "fitch",
        "note": "情报参谋认为证据可靠性存疑",
    })
    assert resp.status_code == 200
    relays = client.get("/staff/relays").json()["relays"]
    assert relays[-1]["from_actor"] == "tf17_intel"
    assert relays[-1]["to_actor"] == "fitch"
    assert relays[-1]["from_result_id"] == result_id
    # 转述进入时间线（可追溯）
    events = client.get("/log/timeline").json()["events"]
    assert any(e["kind"] == "player_relay" for e in events)
    # 被转述者的判断记忆未被污染（转述不是判断输入——信息流经玩家显式动作）
    assert all(m.actor_id in ("tf17_intel", "fitch", "tf17_ops")
               for m in s.judgment_memories)
    # 越权目标拒绝
    bad = client.post("/staff/relay", json={
        "from_result_id": result_id, "to_actor_id": "nonexistent", "note": "x"})
    assert bad.status_code == 404


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
