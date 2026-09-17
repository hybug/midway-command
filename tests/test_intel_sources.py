"""S2.6 舰艇接触与友军电报测试（红灯先行）。

验收（s2-intelligence-system-plan.md Phase S2.6）：
- 非航空来源不会绕过通信和情报流程
- 友军报告会保留转述层级与原发送者
- 不同传感器的识别差异可感知
"""
from datetime import timedelta

import pytest

from src.intel import flow
from src.intel import service as intel
from src.intel import sources as sourcesvc
from src.intel.contracts import (
    ContactStatus,
    MessageStatus,
    SourceType,
    WorkItemStatus,
)
from src.intel.flow import process_intel
from tests.test_intel_flow import ScriptedRng, make_state


class _FakeWriter:
    actor_id = "fake_sensor_operator"

    def write_report(self, view, game_time):
        return f"[{view['sensor'].upper()}] {view['classification']} x{view['count']} " \
               f"BEARING {view['bearing']} DIST {view['distance_nm']} NM"


@pytest.fixture(autouse=True)
def fake_llm_channels(monkeypatch):
    monkeypatch.setattr(flow, "_default_writer", lambda: None)
    monkeypatch.setattr(flow, "_default_analyst", lambda: None)


# ── 统一证据协议（不绕过通信和情报流程）──

def test_lookout_report_goes_through_full_protocol():
    state = make_state(rng_seed=5)
    fleet = state.task_forces[0].carriers[0].position
    msg = sourcesvc.report_surface_observation(
        state, source_type=SourceType.VISUAL_LOOKOUT,
        source_unit="ENTERPRISE LOOKOUT", observer_position=fleet,
        bearing_true=233.0, distance_nm_true=120.0, target_count=3,
        writer=None, rng=ScriptedRng(),
    )
    # 在途：内容不可见（同一通信协议）
    assert msg.status == MessageStatus.IN_TRANSIT
    assert intel.player_inbox(state) == []
    assert state.known_enemy == []
    assert state.evidence == []  # 未到达即无证据——无旁路
    # 到达 → 收报 → 证据 → 工作项
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    assert msg.status == MessageStatus.ROUTED
    assert len(state.evidence) == 1
    assert state.evidence[0].source_type == SourceType.VISUAL_LOOKOUT
    assert len(state.intel_work_items) == 1
    assert state.intel_work_items[0].status == WorkItemStatus.ASSIGNED.value


def test_radar_contact_identity_differs_from_lookout():
    """不同传感器的识别差异可感知。"""
    state = make_state(rng_seed=5)
    fleet = state.task_forces[0].carriers[0].position
    # 雷达：只能看到回波，不见舰型
    radar_msg = sourcesvc.report_surface_observation(
        state, source_type=SourceType.RADAR,
        source_unit="ENTERPRISE RADAR", observer_position=fleet,
        bearing_true=233.0, distance_nm_true=130.0, target_count=3,
        writer=None, rng=ScriptedRng(quality="success"),
    )
    # 瞭望：可以识别出水面舰艇
    lookout_msg = sourcesvc.report_surface_observation(
        state, source_type=SourceType.VISUAL_LOOKOUT,
        source_unit="ENTERPRISE LOOKOUT", observer_position=fleet,
        bearing_true=233.0, distance_nm_true=130.0, target_count=3,
        writer=None, rng=ScriptedRng(quality="success"),
    )
    assert "未识别" in radar_msg.fields["classification"]
    assert radar_msg.fields["classification"] != lookout_msg.fields["classification"]
    # 雷达方位/距离更准（profile：bearing_err 3 < 瞭望 6）——失真幅度可感知差异
    assert abs(radar_msg.fields["bearing"] - 233) <= abs(lookout_msg.fields["bearing"] - 233)


def test_night_degrades_lookout_identity():
    """瞭望的夜间识别降级（传感器特有规则）。"""
    state = make_state(rng_seed=5)
    fleet = state.task_forces[0].carriers[0].position
    day = sourcesvc.report_surface_observation(
        state, source_type=SourceType.VISUAL_LOOKOUT,
        source_unit="LOOKOUT-DAY", observer_position=fleet,
        bearing_true=233.0, distance_nm_true=100.0,
        environment="clear", writer=None, rng=ScriptedRng(quality="success"),
    )
    night = sourcesvc.report_surface_observation(
        state, source_type=SourceType.VISUAL_LOOKOUT,
        source_unit="LOOKOUT-NIGHT", observer_position=fleet,
        bearing_true=233.0, distance_nm_true=100.0,
        environment="night", writer=None, rng=ScriptedRng(quality="success"),
    )
    assert night.fields["classification"] != day.fields["classification"] or \
        night.fields["quality"] == "low"
    # 夜间瞭望退化为未识别
    assert "未识别" in night.fields["classification"]


# ── 友军电报：转述层级与原发送者保留 ──

def test_friendly_report_preserves_relay_chain():
    state = make_state(rng_seed=5)
    fleet = state.task_forces[0].carriers[0].position
    msg = sourcesvc.relay_friendly_report(
        state, from_force="TF17", original_sender="PENSACOLA",
        observer_position=fleet,
        bearing_true=280.0, distance_nm_true=160.0, target_count=2,
        writer=None, rng=ScriptedRng(),
    )
    assert msg.relay_chain == ["TF17"]
    assert msg.origin_sender == "PENSACOLA"
    assert "FROM PENSACOLA VIA TF17" in msg.raw_text
    assert msg.message_kind == "friendly_report"

    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    ev = state.evidence[0]
    # 证据 source 保留原发送者（非转述司令部）
    assert ev.source_id == "PENSACOLA"
    assert ev.source_type == SourceType.FRIENDLY_REPORT
    # 转述有损：可靠性低于直接报告（0.8 × 0.9）
    assert ev.source_reliability < 0.8


# ── 同一协议下的后续情报动作 ──

def test_sensor_evidence_enters_same_conflict_and_cycle_logic():
    from src.intel.flow import intel_work_queue, run_intelligence_cycle
    from src.intel.policy import MechanicalPolicy
    from tests.test_intel_conflicts import FakeAnalyst
    state = make_state(rng_seed=5)
    fleet = state.task_forces[0].carriers[0].position
    sourcesvc.report_surface_observation(
        state, source_type=SourceType.RADAR,
        source_unit="ENTERPRISE RADAR", observer_position=fleet,
        bearing_true=233.0, distance_nm_true=130.0, target_count=3,
        writer=None, rng=ScriptedRng(),
    )
    sourcesvc.report_surface_observation(
        state, source_type=SourceType.VISUAL_LOOKOUT,
        source_unit="ENTERPRISE LOOKOUT", observer_position=fleet,
        bearing_true=150.0, distance_nm_true=110.0, target_count=2,
        writer=None, rng=ScriptedRng(),
    )
    etas = [m.transit_eta for m in state.messages
            if m.status == MessageStatus.IN_TRANSIT]
    if etas:
        state.clock.game_time = max(etas) + timedelta(minutes=1)
    process_intel(state)
    item = intel_work_queue(state)[0]
    brief = run_intelligence_cycle(state, item, policy=MechanicalPolicy(),
                                   analyst=FakeAnalyst())
    # 两个大相径庭的来源观测 → 冲突登记 → 进简报未决问题（同一逻辑）
    assert len(state.evidence_conflicts) >= 1
    assert state.intel_briefs[-1].unresolved_questions


def test_sensor_message_can_be_lost_by_comm_check():
    state = make_state(rng_seed=5)
    fleet = state.task_forces[0].carriers[0].position
    msg = sourcesvc.report_surface_observation(
        state, source_type=SourceType.RADAR,
        source_unit="ENTERPRISE RADAR", observer_position=fleet,
        bearing_true=233.0, distance_nm_true=130.0,
        writer=None, rng=ScriptedRng(comm_raw=2),
    )
    assert msg.status == MessageStatus.LOST  # 同一通信检定纪律：可丢失
    state.clock.game_time += timedelta(hours=2)
    process_intel(state)
    assert state.evidence == []
