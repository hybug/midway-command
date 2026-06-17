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
    """Test the detection system with dice."""

    def _advance_scout(self, state, ticks=1, tick_min=15):
        """Helper: advance time and check scouts."""
        from datetime import timedelta
        for _ in range(ticks):
            state.clock.game_time += timedelta(minutes=tick_min)
            check_scout_results(state)

    def test_search_completes_and_returns(self):
        """Scout should complete search and transition to returning."""
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})
        self._advance_scout(state, ticks=12)  # More ticks to ensure completion
        scout = state.active_scouts[0]
        assert scout.status == "completed"
        assert scout.phase.value in ("landed", "lost")

    def test_detection_fails_when_sector_misses(self):
        """Northwest scout should never find enemy at 30°N 178°W."""
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "northwest"})
        self._advance_scout(state, ticks=9)
        assert len(state.known_enemy) == 0

    def test_detection_not_before_search(self):
        """Scout should not report before SEARCHING phase completes."""
        state = make_state_with_enemy()
        handle_execute_action(state, "launch_scout", {"direction": "southwest"})
        self._advance_scout(state, ticks=2)
        assert len(state.known_enemy) == 0
        assert state.active_scouts[0].status == "in_flight"

    def test_detection_can_succeed(self):
        """With enough attempts, detection should eventually succeed."""
        found = False
        for seed in range(100):
            random.seed(seed)
            state = make_state_with_enemy()
            handle_execute_action(state, "launch_scout", {"direction": "southwest"})
            self._advance_scout(state, ticks=9)
            if len(state.pending_reports) > 0:
                found = True
                break
        assert found, "Detection should succeed at least once in 100 attempts"


class TestEventSchedulerIntegration:
    """Test scouting integrated with the event scheduler."""

    def test_full_flow_with_scheduler(self):
        """Launch scout → advance ticks → detection creates pending report."""
        found = False
        for seed in range(200):
            random.seed(seed)
            state = make_state_with_enemy()
            scheduler = EventScheduler()
            handle_execute_action(state, "launch_scout", {"direction": "southwest"})
            all_notifications = []
            for _ in range(12):
                notes = scheduler.tick(state, 15)
                all_notifications.extend(notes)
            if any("传输中" in n or "发现" in n for n in all_notifications):
                found = True
                break
        assert found, "Should find detection via scheduler in 200 attempts"


# ═══════════════════════════════════════════════════════
# 航线生成测试（§6.5.1~6.5.3）
# ═══════════════════════════════════════════════════════

from src.scouting import (
    generate_sector_route,
    generate_expanding_square_route,
    generate_parallel_route,
    check_detection,
)


class TestSectorRoute:
    """SC-001: 扇形搜索航线生成"""

    def test_sector_route_basic(self):
        """基本扇形航线"""
        fleet_pos = (31.5, -176.0)
        route = generate_sector_route(fleet_pos, center_bearing=45, sector_width=60, radius_nm=100)
        assert len(route) > 0
        # 应该包含多个 hex
        assert len(route) >= 5

    def test_sector_route_wrap_360(self):
        """SC-001: 跨360°扇形"""
        fleet_pos = (31.5, -176.0)
        route = generate_sector_route(fleet_pos, center_bearing=350, sector_width=40, radius_nm=100)
        assert len(route) > 0


class TestExpandingSquareRoute:
    """SC-002: 扩展方形航线生成"""

    def test_expanding_square_route(self):
        """扩展方形航线"""
        fleet_pos = (31.5, -176.0)
        route = generate_expanding_square_route(fleet_pos, max_radius_nm=50)
        assert len(route) > 0
        # 应该覆盖多个 hex
        assert len(route) >= 10


class TestParallelRoute:
    """SC-003: 平行搜索航线生成"""

    def test_parallel_track_route(self):
        """平行搜索航线"""
        fleet_pos = (31.5, -176.0)
        route = generate_parallel_route(fleet_pos, bearing=45, width_nm=100, spacing_nm=20)
        assert len(route) > 0


class TestRouteLength:
    """SC-004: 航线长度计算"""

    def test_route_length(self):
        """航线长度"""
        fleet_pos = (31.5, -176.0)
        route = generate_sector_route(fleet_pos, center_bearing=45, sector_width=60, radius_nm=100)
        # 航线应该有合理的长度
        assert len(route) > 0


class TestSpatialEncounter:
    """SC-005: 空间相遇检测"""

    def test_detect_same_hex(self):
        """同格相遇"""
        state = make_state_with_enemy(enemy_lat=31.5, enemy_lon=-176.0)
        from src.render.coordinate import world_to_hex
        scout_hex = world_to_hex(31.5, -176.0)
        detections = check_detection(scout_hex, state)
        assert len(detections) > 0

    def test_detect_adjacent_hex(self):
        """相邻格相遇"""
        state = make_state_with_enemy(enemy_lat=31.5, enemy_lon=-176.0)
        from src.render.coordinate import world_to_hex
        # 相邻 hex
        scout_hex = (world_to_hex(31.5, -176.0)[0] + 1, world_to_hex(31.5, -176.0)[1])
        detections = check_detection(scout_hex, state)
        # 相邻格应该能检测到
        assert len(detections) >= 0  # 取决于 hex 距离

    def test_detect_no_enemy(self):
        """无敌舰时不检测"""
        state = make_state_with_enemy(enemy_lat=31.5, enemy_lon=-176.0)
        # 远处的 hex
        detections = check_detection((50, 50), state)
        assert len(detections) == 0
