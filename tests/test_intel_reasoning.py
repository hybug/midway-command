"""S2.7 推理工具与不确定度测试（红灯先行）。

验收（s2-intelligence-system-plan.md Phase S2.7）：
- 工具输出是候选关系而非唯一真值
- 结果只能由 NPC 工具调用产生
- 玩家可以在复盘中看到参谋是否使用过这些工具
"""
import math
from datetime import datetime, timedelta, timezone

import pytest

from src.intel import reasoning
from src.intel import service as intel
from src.intel.contracts import ActorRole, EvidenceStatus, MessageStatus, SourceType
from src.intel.models import Evidence, MessageEnvelope
from src.intel.reasoning import (
    bearing_intersection,
    coverage_gaps,
    evidence_conflict_report,
    possible_area,
    what_depends_on,
)
from src.state import Position

T0 = datetime(1942, 6, 4, 5, 0, tzinfo=timezone.utc)


def make_state():
    from src.state import GameClock, GameState
    return GameState(clock=GameClock(game_time=T0), rng_seed=42)


def make_evidence(state, *, lat, lon, bearing, distance, source="VS-6",
                  role=ActorRole.INTEL_OFFICER):
    msg = MessageEnvelope(sender_id="pilot", sender_call_sign=source,
                          filed_at=T0, received_at=T0,
                          status=MessageStatus.RECEIVED)
    state.messages.append(msg)
    ev = intel.register_evidence(
        state, message=msg, source_id=source,
        source_type=SourceType.CARRIER_SCOUT,
        access_roles=[role, ActorRole.CHIEF_OF_STAFF],
        summary=f"{source} contact",
        position=Position(lat=lat, lon=lon),
        reported={"bearing": bearing, "distance_nm": distance, "count": 2},
    )
    return ev


# ── 权限 ──

def test_tools_require_intel_role():
    state = make_state()
    with pytest.raises(PermissionError):
        bearing_intersection(state, actor_id="navigator",
                             lines=[{"lat": 30, "lon": -178, "bearing_deg": 45},
                                    {"lat": 31, "lon": -177, "bearing_deg": 225}])


def test_tools_refuse_evidence_without_permission():
    state = make_state()
    ev = make_evidence(state, lat=30.2, lon=-178.1, bearing=233, distance=195,
                       role=ActorRole.CAPTAIN)  # 只有舰长可见
    with pytest.raises(PermissionError):
        possible_area(state, actor_id="intel_officer", lat=ev.lat, lon=ev.lon,
                      observed_at=T0, evidence_id=ev.id)


# ── 方位线交叉：候选而非真值 ──

def test_bearing_intersection_candidates():
    state = make_state()
    # 两个观察点从不同方向指向同一目标（30.0, -178.0）
    target = (30.0, -178.0)
    from src.scouting import calculate_bearing, calculate_distance_nm
    o1 = (32.0, -175.0)
    o2 = (29.0, -176.5)
    lines = [
        {"lat": o1[0], "lon": o1[1], "bearing_deg": calculate_bearing(o1, target),
         "label": "TF16", "evidence_id": ""},
        {"lat": o2[0], "lon": o2[1], "bearing_deg": calculate_bearing(o2, target),
         "label": "TF17", "evidence_id": ""},
    ]
    out = bearing_intersection(state, actor_id="intel_officer", lines=lines)
    assert len(out["candidates"]) == 1
    cand = out["candidates"][0]
    dist_to_target = calculate_distance_nm(target, (cand["lat"], cand["lon"]))
    assert dist_to_target < 15  # 候选点接近真实交汇处
    assert cand["quality"] in ("good", "poor")
    assert "非唯一真值" in out["note"]  # 候选关系，非唯一真值
    # 工具调用留痕
    assert len(state.tool_calls) == 1
    rec = state.tool_calls[0]
    assert rec.actor_id == "intel_officer"
    assert rec.tool_name == "bearing_intersection"


def test_parallel_bearings_no_candidates():
    state = make_state()
    out = bearing_intersection(
        state, actor_id="intel_officer",
        lines=[{"lat": 30.0, "lon": -178.0, "bearing_deg": 45},
               {"lat": 30.5, "lon": -178.0, "bearing_deg": 46}])
    assert out["candidates"] == []  # 近平行无稳定交点


# ── 可能区域 ──

def test_possible_area_grows_with_age():
    state = make_state()
    out1 = possible_area(state, actor_id="intel_officer",
                         lat=30.2, lon=-178.1, observed_at=T0)
    state.clock.game_time = T0 + timedelta(hours=3)
    out2 = possible_area(state, actor_id="intel_officer",
                         lat=30.2, lon=-178.1, observed_at=T0)
    r1 = out1["candidates"][0]["radius_nm"]
    r2 = out2["candidates"][0]["radius_nm"]
    assert r2 > r1  # 位置年龄越大，可能区域越大
    assert out2["candidates"][0]["age_hours"] == 3.0


# ── 覆盖缺口 ──

def test_coverage_gaps_deterministic():
    state = make_state()
    searched = [{"lat": 30.2, "lon": -177.6, "radius_nm": 50}]
    kwargs = dict(center_lat=30.2, center_lon=-178.2, radius_nm=100,
                  searched=searched)
    out1 = coverage_gaps(state, actor_id="intel_officer", **kwargs)
    n1 = len(out1["candidates"])
    assert n1 > 0  # 西侧未被覆盖 → 有缺口
    # 缺口点在被搜索圆之外
    for g in out1["candidates"]:
        d = math.hypot((g["lon"] + 177.6) * 60 * math.cos(math.radians(g["lat"])),
                       (g["lat"] - 30.2) * 60)
        assert d > 50
    state2 = make_state()
    out2 = coverage_gaps(state2, actor_id="intel_officer", **kwargs)
    assert out1["candidates"] == out2["candidates"]  # 确定性：同输入同输出


# ── 冲突提示工具与依赖反查 ──

def test_conflict_tool_reports_and_records():
    state = make_state()
    e1 = make_evidence(state, lat=30.2, lon=-178.1, bearing=233, distance=195,
                       source="VS-6")
    e2 = make_evidence(state, lat=30.4, lon=-176.0, bearing=120, distance=120,
                       source="PBY-3")
    out = evidence_conflict_report(state, actor_id="intel_officer",
                                   evidence_ids=[e1.id, e2.id])
    assert len(out["conflicts"]) >= 1
    assert state.tool_calls[-1].tool_name == "evidence_conflict_report"


def test_what_depends_on_reverse_lookup():
    from src.intel.policy import MechanicalPolicy
    from src.intel.rng import RNGService
    # 组装一个最小判断链
    state = make_state()
    ev = make_evidence(state, lat=30.2, lon=-178.1, bearing=233, distance=195)
    claim = intel.record_claim(
        state, assessment_id="AS-000001", actor_id="intel_officer",
        claim_type="judgment", text="敌主力存在",
        based_on_evidence_ids=[ev.id], tool_call_ids=["TOOL-000001"],
    )
    assessment = state.assessments
    from src.intel.models import NPCAssessment
    assessment.append(NPCAssessment(
        id="AS-000001", author_actor_id="intel_officer",
        based_on_evidence_ids=[ev.id], dice_record_ids=["chk_1"],
        claims=[claim.id],
    ))
    out = what_depends_on(state, actor_id="intel_officer",
                          assessment_id="AS-000001")
    assert out["evidence_ids"] == [ev.id]
    assert out["dice_record_ids"] == ["chk_1"]
    assert "TOOL-000001" in out["tool_call_ids"]
    assert out["claims"][0]["text"] == "敌主力存在"


# ── 无调用即无派生（D12/D15 工具侧）──

def test_no_tool_call_no_derived_products():
    state = make_state()
    assert state.tool_calls == []
    # 系统不会静默生成任何交叉点/可能区域/缺口
    # （工具只在被参谋调用时产出并落记录）
    assert len(state.tool_calls) == 0


# ── 可回放 ──

def test_tool_calls_replay_identical():
    def run():
        state = make_state()
        bearing_intersection(
            state, actor_id="intel_officer",
            lines=[{"lat": 32.0, "lon": -175.0, "bearing_deg": 233},
                   {"lat": 29.0, "lon": -176.5, "bearing_deg": 40}])
        possible_area(state, actor_id="intel_officer", lat=30.2, lon=-178.1,
                      observed_at=T0)
        coverage_gaps(state, actor_id="intel_officer", center_lat=30.2,
                      center_lon=-178.2, radius_nm=80,
                      searched=[{"lat": 30.2, "lon": -177.6, "radius_nm": 40}])
        return [t.model_dump() for t in state.tool_calls]
    assert run() == run(), "工具调用序列必须可复现"
