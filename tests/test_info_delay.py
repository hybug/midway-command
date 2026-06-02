"""Tests for information delay and distortion system."""
import random
import pytest
from datetime import datetime, timezone, timedelta

from src.state import GameState, GameClock, TaskForce, Carrier, AirGroup, AirGroupType, AirGroupStatus, Position
from src.scouting import (
    distort_bearing, distort_distance, distort_count,
    compute_report_delay, check_scout_results, check_pending_reports
)
from src.tools import handle_execute_action


def make_state_with_enemy():
    """Create a state with hidden enemy."""
    carrier = Carrier(
        name="USS Enterprise (CV-6)",
        position=Position(lat=32.0, lon=-175.0),
        cap_strength=12,
        air_groups=[
            AirGroup(type=AirGroupType.FIGHTER, count=27, status=AirGroupStatus.READY),
        ],
    )
    tf = TaskForce(name="TF16", carriers=[carrier], course=240, speed=25)
    state = GameState(
        clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)),
        task_forces=[tf],
    )
    state._hidden_actual_enemy = [{
        "name": "Kido Butai",
        "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"],
        "position": {"lat": 30.0, "lon": -178.0},
        "status": "rearming",
    }]
    return state


class TestDistortion:
    """Test distortion functions."""

    def test_bearing_distortion_within_range(self):
        random.seed(42)
        for _ in range(100):
            result = distort_bearing(180, max_error=5)
            assert 175 <= result <= 185 or result >= 355 or result <= 5

    def test_bearing_distortion_wraps_360(self):
        random.seed(42)
        result = distort_bearing(2, max_error=5)
        assert 0 <= result <= 359

    def test_distance_distortion_close(self):
        random.seed(42)
        for _ in range(50):
            result = distort_distance(100, max_error_pct=0.1)
            assert 85 <= result <= 115

    def test_count_distortion_can_undercount(self):
        random.seed(42)
        results = [distort_count(4, undercount_prob=0.8) for _ in range(100)]
        # With 80% undercount prob, most should be < 4
        undercounts = sum(1 for r in results if r < 4)
        assert undercounts > 30  # Should be ~80

    def test_count_distortion_can_be_accurate(self):
        random.seed(42)
        results = [distort_count(4, undercount_prob=0.2) for _ in range(100)]
        accurate = sum(1 for r in results if r == 4)
        assert accurate > 50  # Should be ~80


class TestReportDelay:
    """Test report delay computation."""

    def test_delay_increases_with_distance(self):
        random.seed(42)
        close_delays = [compute_report_delay(50) for _ in range(20)]
        far_delays = [compute_report_delay(190) for _ in range(20)]
        assert max(close_delays) < max(far_delays)

    def test_delay_within_bounds(self):
        random.seed(42)
        for _ in range(100):
            delay = compute_report_delay(100)
            assert 20 <= delay <= 80


class TestPendingReportFlow:
    """Test the full flow: detection → pending → arrival."""

    def _advance_scout(self, state, ticks=1, tick_min=15):
        """Helper: advance time and check scouts, simulating EventScheduler ticks."""
        for _ in range(ticks):
            state.clock.game_time += timedelta(minutes=tick_min)
            check_scout_results(state)

    def test_detection_creates_pending_report(self):
        random.seed(1)
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})

        self._advance_scout(state, ticks=9)

        assert len(state.pending_reports) == 1
        assert len(state.known_enemy) == 0
        assert state.pending_reports[0].scout_id is not None

    def test_pending_report_arrives_after_delay(self):
        random.seed(1)
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})

        self._advance_scout(state, ticks=9)
        report = state.pending_reports[0]

        # Advance past arrival time
        state.clock.game_time = report.arrive_at + timedelta(minutes=1)
        notifications = check_pending_reports(state)

        assert len(state.pending_reports) == 0
        assert len(state.known_enemy) == 1
        assert any("报告到达" in n for n in notifications)

    def test_pending_report_has_distortion(self):
        random.seed(1)
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})

        self._advance_scout(state, ticks=9)
        report = state.pending_reports[0]

        assert report.real_bearing != report.reported_bearing or \
               report.real_distance_nm != report.reported_distance_nm or \
               report.real_carrier_count != report.reported_carrier_count

    def test_pending_report_not_visible_to_player(self):
        random.seed(1)
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})

        self._advance_scout(state, ticks=9)

        assert len(state.known_enemy) == 0


class TestEventSchedulerIntegration:
    """Test delay system integrated with event scheduler."""
    from src.events import EventScheduler

    def test_full_flow_with_delay(self):
        random.seed(1)
        state = make_state_with_enemy()
        scheduler = TestEventSchedulerIntegration.EventScheduler()

        handle_execute_action(state, "launch_scout", {"direction": "southwest"})

        all_notifications = []
        for _ in range(9):
            notes = scheduler.tick(state, 15)
            all_notifications.extend(notes)

        assert any("传输中" in n for n in all_notifications)
