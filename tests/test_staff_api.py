"""S8 UI.4 STAFF 接口测试（红灯先行）：名册/正式判断/重判/极简档案。

验收：
- 参谋名册（白名单）：身份+状态+关注+最近互动；不出现 competence 等内部数值
- 普通对话与正式判断分离：判断经 /judgment/tasks 产生 JudgmentResult+报告
- NPC 不因 UI 操作获得越权信息（判断只消费权限内 EvidenceView）
- reconsider 只有新证据/反馈才能建新版本
- 无 LLM 降级：报告带机械降级标记（非玩法路径）
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import server as server_module
from src.cognition.persona import render_report
from src.cognition import context as cognition_ctx
from src.intel import service as intel
from src.intel.contracts import ActorRole, ApprovalStatus, MessageStatus, SourceType
from src.intel.models import IntelBrief, MessageEnvelope
from src.state import GameState, GameClock

NOW = datetime(1942, 5, 7, 10, 0, tzinfo=timezone.utc)


class _FakeGenerator:
    """fake LLM 候选生成（不触网）。"""

    def generate(self, task, context):
        return [{
            "text": "发现日军主力航母群，应立即全力攻击。",
            "predicted_class": "CV", "predicted_count_range": (2, 3),
            "predicted_position": (-12.2, 157.0),
            "supporting_evidence_ids": [context.evidence[0].evidence_id]
            if context.evidence else [],
            "assumptions": ["识别正确"],
            "recommendation": "立即放飞全力攻击群。",
            "change_my_mind": ["陆军飞机证实为掩护群时收拢攻击队"],
        }]


@pytest.fixture(autouse=True)
def fake_generator(monkeypatch):
    monkeypatch.setattr(server_module, "_make_generator", lambda actor: _FakeGenerator())
    monkeypatch.setattr(server_module, "_render_for", _fake_render)


def _fake_render(actor, task, result, hypotheses, client=None):
    return f"【判断】{result.chosen_hypothesis_id or '拒绝'}（{result.confidence_band}）"


def _state_with_evidence():
    s = GameState(clock=GameClock(game_time=NOW))
    msg = MessageEnvelope(
        id="MSG-000001", sender_id="VS5-1", sender_call_sign="VS5-1",
        observed_at=NOW - timedelta(minutes=30),
        received_at=NOW - timedelta(minutes=10),
        raw_text="TWO CV FOUR CA BEARING 100 DIST 150 NM",
        status=MessageStatus.LOGGED,
    )
    s.messages.append(msg)
    from src.state import Position
    intel.register_evidence(
        s, message=msg, source_id="VS5-1",
        source_type=SourceType.CARRIER_SCOUT,
        access_roles=[ActorRole.INTEL_OFFICER],
        summary="米西马以北报告两艘航母四艘巡洋舰",
        reported={"bearing": 100, "distance_nm": 150, "count": 2,
                  "classification": "CV"},
        position=Position(lat=-12.2, lon=157.0),
    )
    return s


def _client(s):
    server_module.game_state = s
    return TestClient(server_module.app)


def test_roster_lists_midway_and_coral_actors_without_internal_numbers():
    client = _client(_state_with_evidence())
    data = client.get("/staff/roster").json()
    ids = {a["actor_id"] for a in data["staff"]}
    assert {"browning", "intel_officer"} <= ids          # 中途岛对话型
    assert {"fitch", "tf17_intel", "tf17_ops"} <= ids    # 珊瑚海班子（NPC）
    assert "fletcher" not in ids                          # 玩家本人不进名册
    blob = json.dumps(data, ensure_ascii=False)
    for banned in ("competence", "risk_tolerance", "imagination", "autonomy",
                   "initiative", "attributes"):
        assert banned not in blob, f"名册泄露内部数值 {banned}"
    actor = next(a for a in data["staff"] if a["actor_id"] == "tf17_intel")
    assert actor["dossier"]["status_line"]
    assert "identity" not in json.dumps(actor["dossier"])


def test_judgment_task_produces_result_and_report():
    s = _state_with_evidence()
    client = _client(s)
    resp = client.post("/judgment/tasks", json={
        "actor_id": "tf17_intel",
        "question": "这份米西马方向接触报告是否足以支持立即放飞全力攻击？",
    })
    assert resp.status_code == 200
    data = resp.json()
    result = data["result"]
    assert result["chosen_hypothesis_id"] is not None
    assert result["confidence_band"] in ("low", "medium", "high")
    assert data["report"].startswith("【判断】")
    # 判断只消费权限内证据
    task = next(t for t in s.judgment_tasks if t.id == result["task_id"])
    assert task.evidence_ids                              # 装配自权限内证据
    assert s.judgment_reports[result["id"]]


def test_judgment_out_of_duty_refused_with_referral():
    s = _state_with_evidence()
    client = _client(s)
    resp = client.post("/judgment/tasks", json={
        "actor_id": "tf17_intel", "question": "CAP 应如何轮换？", "domain": "air",
    })
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["refusal_reason"] == "out_of_duty"
    assert "fitch" in (result["recommendation"] or "")


def test_reconsider_requires_revision_inputs_and_supersedes():
    s = _state_with_evidence()
    client = _client(s)
    r1 = client.post("/judgment/tasks", json={
        "actor_id": "tf17_intel", "question": "报告是否支持立即攻击？",
    }).json()["result"]
    # 无新证据无理由 → 拒绝建版
    bad = client.post(f"/npcs/tf17_intel/judgments/{r1['id']}/reconsider",
                      json={"reason": "", "new_evidence_ids": []})
    assert bad.status_code == 400
    # 新证据到达 → 新版本，旧结果保留
    msg2 = MessageEnvelope(
        id="MSG-000002", sender_id="VS5-2", sender_call_sign="VS5-2",
        observed_at=NOW, received_at=NOW, raw_text="ARMY AIRCRAFT REPORT 1 CV",
        status=MessageStatus.LOGGED,
    )
    s.messages.append(msg2)
    ev2 = intel.register_evidence(
        s, message=msg2, source_id="VS5-2", source_type=SourceType.CARRIER_SCOUT,
        access_roles=[ActorRole.INTEL_OFFICER], summary="陆军飞机报告一艘航母",
        reported={"count": 1, "classification": "CVL"},
    )
    s.intel_briefs.append(IntelBrief(id="BRF-000002", author_actor_id="tf17_intel",
                                     new_evidence_ids=[ev2.id], status="proposed"))
    ok = client.post(f"/npcs/tf17_intel/judgments/{r1['id']}/reconsider",
                     json={"reason": "陆军飞机新报告到达", "new_evidence_ids": [ev2.id]})
    assert ok.status_code == 200
    r2 = ok.json()["result"]
    assert r2["id"] != r1["id"]
    assert r2["supersedes_result_id"] is None or r2["id"] != r1["id"]
    old_mem = next(m for m in s.judgment_memories if m.result_id == r1["id"])
    new_mem = next(m for m in s.judgment_memories if m.result_id == r2["id"])
    assert old_mem.status == "revised"
    assert new_mem.supersedes_id == old_mem.id
    # 判断历史可查
    lst = client.get("/npcs/tf17_intel/judgments").json()["judgments"]
    assert [j["result"]["id"] for j in lst] == [r1["id"], r2["id"]]


def test_no_llm_degradation_marked(monkeypatch):
    """无 LLM：机械候选 + 降级报告显式标记（非正式玩法路径）。"""
    from src.cognition.persona import MechanicalCandidates
    monkeypatch.setattr(server_module, "_make_generator",
                        lambda actor: MechanicalCandidates(actor))
    monkeypatch.setattr(server_module, "_render_for",
                        lambda actor, task, result, hyps, client=None:
                        render_report(actor, task, result, hyps, client=None))
    monkeypatch.setattr("server.render_report", render_report, raising=False)
    s = _state_with_evidence()
    client = _client(s)
    data = client.post("/judgment/tasks", json={
        "actor_id": "tf17_intel", "question": "报告是否支持立即攻击？",
    }).json()
    assert "机械降级" in data["report"] and "非正式玩法路径" in data["report"]


def test_judgment_payloads_never_leak_actual_enemy():
    s = _state_with_evidence()
    s.actual_enemy = [{"name": "Shokaku", "carriers": ["Shokaku", "Zuikaku"],
                       "position": {"lat": -12.0, "lon": 157.0}}]
    client = _client(s)
    client.post("/judgment/tasks", json={
        "actor_id": "tf17_intel", "question": "报告是否支持立即攻击？"})
    blob = json.dumps({
        "roster": client.get("/staff/roster").json(),
        "judgments": client.get("/npcs/tf17_intel/judgments").json(),
    }, ensure_ascii=False).lower()
    for banned in ("actual_enemy", "shokaku", "zuikaku", "internal_truth_ref"):
        assert banned not in blob, f"STAFF 可见面泄露 {banned}"
