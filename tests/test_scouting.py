"""Tests for the scouting system — detection, probability, sector coverage."""
import random
import pytest
from datetime import datetime, timezone

from src.state import GameState, GameClock, TaskForce, Carrier, AirGroup, AirGroupType, AirGroupStatus, Position, Aircraft, AircraftType, AircraftStatus
from src.scouting import calculate_bearing, calculate_distance_nm, in_sector, check_scout_results
from src.tools import handle_execute_action
from src.events import EventScheduler


def make_state_with_enemy(enemy_lat=30.0, enemy_lon=-178.0):
    """Create a state with hidden enemy at specified position."""
    # Generate test aircraft (10 SBDs for testing)
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
            AirGroup(type=AirGroupType.FIGHTER, count=27, status=AirGroupStatus.READY, squadron_name="VF-6"),
            AirGroup(type=AirGroupType.DIVE_BOMBER, count=38, status=AirGroupStatus.READY, squadron_name="VB-6"),
        ],
        aircraft=test_aircraft,
    )
    tf = TaskForce(name="TF16", carriers=[carrier], course=240, speed=25)
    state = GameState(
        clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)),
        task_forces=[tf],
    )
    state._hidden_actual_enemy = [{
        "name": "Kido Butai",
        "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"],
        "position": {"lat": enemy_lat, "lon": enemy_lon},
        "status": "rearming",
        "aircraft_total": 248,
    }]
    return state


class TestBearingAndDistance:
    """Test basic geographic calculations."""

    def test_bearing_north(self):
        """Enemy directly south → bearing ~180°"""
        bearing = calculate_bearing((32.0, -175.0), (30.0, -175.0))
        assert 170 <= bearing <= 190

    def test_bearing_southwest(self):
        """Enemy at 30°N 178°W from 32°N 175°W → bearing ~233°"""
        bearing = calculate_bearing((32.0, -175.0), (30.0, -178.0))
        assert 220 <= bearing <= 245

    def test_distance_short(self):
        """Close positions → small distance."""
        dist = calculate_distance_nm((32.0, -175.0), (32.1, -175.1))
        assert dist < 20

    def test_distance_midway(self):
        """Fleet to enemy at 30°N 178°W → ~195 nm."""
        dist = calculate_distance_nm((32.0, -175.0), (30.0, -178.0))
        assert 180 <= dist <= 210


class TestSectorCoverage:
    """Test sector containment logic."""

    def test_bearing_in_sector(self):
        assert in_sector(232, 210, 240) is True

    def test_bearing_outside_sector(self):
        assert in_sector(232, 295, 325) is False

    def test_sector_wraps_360(self):
        """Sector 350-10 should contain bearing 355 and 5."""
        assert in_sector(355, 350, 10) is True
        assert in_sector(5, 350, 10) is True
        assert in_sector(200, 350, 10) is False


class TestScoutLaunch:
    """Test launching scouts via execute_action."""

    def test_launch_scout_creates_mission(self):
        state = make_state_with_enemy()
        result = handle_execute_action(state, "launch_scout", {"direction": "southwest"})
        assert len(state.active_scouts) == 1
        scout = state.active_scouts[0]
        assert scout.direction == "southwest"
        assert scout.status == "in_flight"
        assert scout.eta_minutes == 60
        assert "SBD" in result

    def test_scout_sector_covers_enemy(self):
        """Southwest search (205°-245°) should cover enemy at bearing ~233°."""
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})
        scout = state.active_scouts[0]
        # Sector search uses 40° spread: 225-20=205, 225+20=245
        assert scout.search_bearing_min == 205
        assert scout.search_bearing_max == 245

    def test_scout_sector_misses_enemy(self):
        """Northwest search (295°-325°) should NOT cover enemy at bearing ~233°."""
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "northwest"})
        scout = state.active_scouts[0]
        # Enemy at ~233° is outside 295°-325°
        assert not (scout.search_bearing_min <= 233 <= scout.search_bearing_max)


class TestScoutDetection:
    """Test the detection probability system."""

    def _advance_scout(self, state, ticks=1, tick_min=15):
        """Helper: advance time and check scouts, simulating EventScheduler ticks."""
        from datetime import timedelta
        for _ in range(ticks):
            state.clock.game_time += timedelta(minutes=tick_min)
            check_scout_results(state)

    def test_detection_creates_pending_report(self):
        """With favorable seed, southwest scout should detect and create pending report."""
        random.seed(1)  # Known to succeed
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})

        # Advance 9 ticks × 15min = 135 min (PREP 15 + OUTBOUND 45 + SEARCH 60 + 15 margin)
        self._advance_scout(state, ticks=9)

        # Detection creates PendingReport, not immediate EnemyKnown
        assert len(state.pending_reports) == 1
        assert len(state.known_enemy) == 0  # Not visible yet

    def test_detection_fails_when_sector_misses(self):
        """Northwest scout should never find enemy at 30°N 178°W."""
        random.seed(1)
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "northwest"})

        self._advance_scout(state, ticks=9)

        assert len(state.known_enemy) == 0

    def test_detection_not_before_search(self):
        """Scout should not report before SEARCHING phase completes."""
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})

        self._advance_scout(state, ticks=2)  # 30 min, still PREPARING

        assert len(state.known_enemy) == 0
        assert state.active_scouts[0].status == "in_flight"


class TestEventSchedulerIntegration:
    """Test scouting integrated with the event scheduler."""

    def test_full_flow_with_scheduler(self):
        """Launch scout → advance 8 ticks (120 min) → detection creates pending report."""
        random.seed(1)
        state = make_state_with_enemy()
        scheduler = EventScheduler()

        # Launch scout
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})

        # Advance 8 × 15 min = 120 min (PREP 15 + OUTBOUND 45 + SEARCH 60)
        all_notifications = []
        for _ in range(8):
            notes = scheduler.tick(state, 15)
            all_notifications.extend(notes)

        # Detection creates pending report, not immediate EnemyKnown
        assert len(state.pending_reports) == 1
        assert any("传输中" in n for n in all_notifications)
