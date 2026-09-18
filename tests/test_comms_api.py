"""S8 UI.2 COMMS 接口测试（红灯先行）。

验收（s8-ui-ux-system-plan.md Phase UI.2 / M8.3）：
- 频道与索引：INCOMING/OUTGOING/TF17·TF11/CORRECTIONS/ARCHIVE 可由白名单字段区分
- 电文详情：收发时间链/路由/勘误链字段齐全（原文不可编辑是 UI 纪律）
- 关联跳转：电文可定位到引用其证据的简报与判断
- 在途和丢失内容不可见（D1 不回归）；勘误只追加（D4 不回归）
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import server as server_module
from src.intel import service as intel
from src.intel.contracts import ActorRole, CommCondition, MessageStatus, SourceType, WorkPriority
from src.intel.models import MessageEnvelope
from src.state import GameState, GameClock

NOW = datetime(1942, 5, 7, 10, 0, tzinfo=timezone.utc)


def _client_with(state):
    server_module.game_state = state
    return TestClient(server_module.app)


def _state():
    s = GameState(clock=GameClock(game_time=NOW))
    return s


def _file_contact(s, *, call_sign="VS5-2", relay=False, kind="scout_report"):
    msg = MessageEnvelope(
        sender_id="orig" if relay else call_sign,
        sender_call_sign=call_sign,
        recipient_ids=["TF16 FLAG"],
        priority=WorkPriority.FLASH,
        message_kind="friendly_report" if relay else kind,
        observed_at=NOW - timedelta(minutes=30),
        received_at=NOW - timedelta(minutes=10),
        raw_text="TWO CV FOUR CA BEARING 100 DIST 150 NM",
        fields={"bearing": 100, "distance_nm": 150, "count": 2,
                "classification": "CV", "quality": "standard"},
        origin_sender="TF11 COMMAND" if relay else None,
        relay_chain=["TF11"] if relay else [],
        condition=CommCondition.COMPLETE,
        status=MessageStatus.LOGGED,
    )
    msg.filed_at = NOW - timedelta(minutes=25)
    msg.id = f"MSG-{len(s.messages) + 1:06d}"
    s.messages.append(msg)
    return msg


def test_inbox_exposes_detail_and_link_fields():
    s = _state()
    msg = _file_contact(s)
    ev = intel.register_evidence(
        s, message=msg, source_id=msg.sender_call_sign,
        source_type=SourceType.CARRIER_SCOUT,
        access_roles=[ActorRole.INTEL_OFFICER], summary="米西马接触",
    )
    from src.intel.models import IntelBrief, NPCAssessment
    assessment = NPCAssessment(id="AS-000001", author_actor_id="tf17_intel",
                               based_on_evidence_ids=[ev.id])
    s.assessments.append(assessment)
    s.intel_briefs.append(IntelBrief(id="BRF-000001", author_actor_id="tf17_intel",
                                     new_evidence_ids=[ev.id], status="proposed"))
    client = _client_with(s)
    data = client.get("/intel/inbox").json()
    m = next(x for x in data["messages"] if x["id"] == msg.id)
    for field in ("observed_at", "filed_at", "received_at", "condition",
                  "routed_to", "origin_sender", "relay_chain", "kind",
                  "related_brief_ids", "related_assessment_ids"):
        assert field in m, f"inbox 缺字段 {field}"
    assert m["related_brief_ids"] == ["BRF-000001"]
    assert m["related_assessment_ids"] == ["AS-000001"]


def test_comms_channels_endpoint_partitions_channels():
    s = _state()
    relayed = _file_contact(s, call_sign="TF11-1", relay=True)
    direct = _file_contact(s, call_sign="VS5-3")
    correction = MessageEnvelope(
        id="MSG-000004",
        sender_id="VS5-2", sender_call_sign="VS5-2",
        message_kind="correction", priority=WorkPriority.CORRECTION,
        observed_at=NOW, received_at=NOW, status=MessageStatus.LOGGED,
        supersedes_message_id=direct.id, raw_text="CORRECTION: 1 CV NOT 2",
    )
    s.messages.append(correction)
    archived = _file_contact(s, call_sign="VS5-4")
    archived.id = "MSG-000005"
    archived.status = MessageStatus.ARCHIVED
    outgoing = MessageEnvelope(
        id="MSG-000006",
        sender_id="fletcher", sender_call_sign="CTF-17",
        message_kind="outgoing", priority=WorkPriority.ROUTINE,
        observed_at=NOW, received_at=NOW, status=MessageStatus.FILED,
        raw_text="COMMENCE LAUNCH AT 0700",
    )
    s.messages.append(outgoing)
    in_transit = MessageEnvelope(
        id="MSG-000007",
        sender_id="VS5-9", sender_call_sign="VS5-9",
        message_kind="scout_report", observed_at=NOW, status=MessageStatus.IN_TRANSIT,
        raw_text="SECRET IN TRANSIT CONTENT",
    )
    s.messages.append(in_transit)

    client = _client_with(s)
    channels = client.get("/comms/channels").json()["channels"]
    ids = {name: [m["id"] for m in msgs] for name, msgs in channels.items()}
    assert direct.id in ids["INCOMING"]
    assert relayed.id in ids["TF17_TF11"]
    assert correction.id in ids["CORRECTIONS"]
    assert outgoing.id in ids["OUTGOING"]
    assert archived.id in ids["ARCHIVE"]
    # 在途内容不可见（D1）
    all_ids = {i for lst in ids.values() for i in lst}
    assert in_transit.id not in all_ids
    assert "SECRET IN TRANSIT" not in str(channels)


def test_outgoing_draft_confirm_flow():
    s = _state()
    client = _client_with(s)
    resp = client.post("/comms/outgoing", json={
        "raw_text": "TF17 COURSE 310 SPEED 27",
        "priority": "routine",
    })
    assert resp.status_code == 200
    out = resp.json()
    assert out["message"]["sender_id"] == "fletcher"
    assert out["message"]["kind"] == "outgoing"
    assert out["message"]["status"] == "filed"      # 已拍发存档
    # OUTGOING 频道可见
    channels = client.get("/comms/channels").json()["channels"]
    assert any(m["id"] == out["message"]["id"] for m in channels["OUTGOING"])
    # 空电文拒绝（发报需确认内容）
    assert client.post("/comms/outgoing", json={"raw_text": "  "}).status_code == 400
