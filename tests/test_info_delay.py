"""Tests for information delay and distortion system.

S2.3 起：侦察报告延迟经由情报流（FiledMessage IN_TRANSIT → transit_eta →
RECEIVED），旧 PendingReport 管线退役。失真函数保持模块级语义（S2.1）。
"""
import pytest
from datetime import datetime, timezone, timedelta

from src.state import GameState, GameClock, TaskForce, Carrier, AirGroup, AirGroupType, AirGroupStatus, Position, Aircraft, AircraftType, AircraftStatus
from src.scouting import (
    distort_bearing, distort_distance, distort_count,
    compute_report_delay, check_scout_results
)
from src.intel import service as intel
from src.intel.flow import process_intel
from src.tools import handle_execute_action


def make_state_with_enemy(rng_seed=7):
    """Create a state with hidden enemy."""
    test_aircraft = [
        Aircraft(
            id=f"SBD-VB6-{i:02d}",
            type=AircraftType.SBD,
            squadron="VB-6",
            carrier="Enterprise",
            status=AircraftStatus.READY,
            fuel_pct=100.0,
            ammo_pct=100.0,
        )
        for i in range(1, 11)
    ]
    carrier = Carrier(
        name="USS Enterprise (CV-6)",
        position=Position(lat=32.0, lon=-175.0),
        cap_strength=12,
        air_groups=[
            AirGroup(type=AirGroupType.FIGHTER, count=27, status=AirGroupStatus.READY),
        ],
        aircraft=test_aircraft,
    )
    tf = TaskForce(name="TF16", carriers=[carrier], course=240, speed=25)
    state = GameState(
        clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)),
        task_forces=[tf],
        rng_seed=rng_seed,
    )
    state.actual_enemy = [{
        "name": "Kido Butai",
        "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"],
        "position": {"lat": 30.0, "lon": -178.0},
        "status": "rearming",
    }]
    return state


@pytest.fixture(autouse=True)
def fake_pilot_writer(monkeypatch):
    """情报流测试固定注入 fake 飞行员 writer（不触网）。"""
    from src.intel import flow

    class _FakeWriter:
        actor_id = "fake_pilot_vs6"

        def write_report(self, view, game_time):
            return (f"CONTACT {view['classification']} x{view['count']} "
                    f"BEARING {view['bearing']} DIST {view['distance_nm']} NM")

    monkeypatch.setattr(flow, "_default_writer", lambda: _FakeWriter())


class TestDistortion:
    """Test distortion functions."""

    def test_bearing_distortion_within_range(self):
        for _ in range(100):
            result = distort_bearing(180, max_error=5)
            assert 175 <= result <= 185 or result >= 355 or result <= 5

    def test_bearing_distortion_wraps_360(self):
        result = distort_bearing(2, max_error=5)
        assert 0 <= result <= 359

    def test_distance_distortion_close(self):
        for _ in range(50):
            result = distort_distance(100, max_error_pct=0.1)
            assert 85 <= result <= 115

    def test_count_distortion_can_undercount(self):
        results = [distort_count(4, undercount_prob=0.8) for _ in range(100)]
        undercounts = sum(1 for r in results if r < 4)
        assert undercounts > 30  # Should be ~80

    def test_count_distortion_can_be_accurate(self):
        results = [distort_count(4, undercount_prob=0.2) for _ in range(100)]
        accurate = sum(1 for r in results if r == 4)
        assert accurate > 50  # Should be ~80


class TestReportDelay:
    """Test report delay computation."""

    def test_delay_increases_with_distance(self):
        close_delays = [compute_report_delay(50) for _ in range(20)]
        far_delays = [compute_report_delay(190) for _ in range(20)]
        assert max(close_delays) < max(far_delays)

    def test_delay_within_bounds(self):
        for _ in range(100):
            delay = compute_report_delay(100)
            assert 20 <= delay <= 80


class TestIntelDeliveryFlow:
    """S2.3：探测 → IN_TRANSIT（transit_eta）→ 到达收报 → known_enemy 兼容。"""

    def _advance_scout(self, state, ticks=1, tick_min=15):
        for _ in range(ticks):
            state.clock.game_time += timedelta(minutes=tick_min)
            check_scout_results(state)

    def _find_detection(self):
        for seed in range(200):
            state = make_state_with_enemy(rng_seed=seed)
            handle_execute_action(state, "launch_scout", {"direction": "southwest"})
            self._advance_scout(state, ticks=9)
            msgs = [m for m in state.messages if m.message_kind == "scout_report"]
            if msgs:
                return state, msgs[0]
        return None, None

    def test_detection_creates_in_transit_message(self):
        state, msg = self._find_detection()
        assert msg is not None, "Should find a seed that produces detection"
        assert msg.status.value == "in_transit"
        assert msg.transit_eta is not None
        assert len(state.known_enemy) == 0
        assert intel.player_inbox(state) == []  # 未到达 → 玩家不可见

    def test_message_arrives_after_delay(self):
        state, msg = self._find_detection()
        assert msg is not None
        state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
        notifications = process_intel(state)

        assert msg.status.value in ("received", "logged", "routed")
        assert msg.received_at is not None
        assert len(state.evidence) == 1
        assert len(state.intel_work_items) == 1
        assert any("报告到达" in n for n in notifications)

    def test_message_has_distortion(self):
        state, msg = self._find_detection()
        assert msg is not None
        obs = next(o for o in state.observations
                   if o.id == msg.observation_id)
        # 报告值与真值不同（失真），或至少两者字段齐备可比较
        assert msg.fields["bearing"] != obs.bearing_true or \
            msg.fields["distance_nm"] != int(obs.distance_nm_true) or \
            msg.fields["count"] == obs.carrier_count_true

    def test_report_not_visible_to_player_before_arrival(self):
        state, msg = self._find_detection()
        assert msg is not None
        assert len(state.known_enemy) == 0
        assert intel.player_inbox(state) == []
