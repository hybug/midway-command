"""Tests for the entity system — positions, movement, fleet structure."""
import math
import pytest
from src.entities import (
    Position, Entity, NavalEntity, Carrier, AirEntity, TaskForce,
    calculate_new_position, update_entity_position, update_all_positions
)
from src.initial_state import build_initial_state


class TestPosition:
    """Test Position model."""

    def test_position_creation(self):
        pos = Position(lat=32.0, lon=-175.0)
        assert pos.lat == 32.0
        assert pos.lon == -175.0

    def test_position_to_tuple(self):
        pos = Position(lat=32.0, lon=-175.0)
        assert pos.to_tuple() == (32.0, -175.0)


class TestNavalEntity:
    """Test NavalEntity."""

    def test_carrier_creation(self):
        carrier = Carrier(
            id="enterprise",
            name="USS Enterprise",
            position=Position(lat=32.0, lon=-175.0),
            course=240,
            speed=25,
            faction="us",
        )
        assert carrier.id == "enterprise"
        assert carrier.course == 240
        assert carrier.speed == 25
        assert carrier.faction == "us"

    def test_carrier_with_air_groups(self):
        carrier = Carrier(
            id="enterprise",
            name="USS Enterprise",
            position=Position(lat=32.0, lon=-175.0),
            course=240,
            speed=25,
            faction="us",
            air_groups=[{"type": "fighter", "count": 27}],
            cap_strength=12,
        )
        assert len(carrier.air_groups) == 1
        assert carrier.cap_strength == 12


class TestTaskForce:
    """Test TaskForce."""

    def test_task_force_creation(self):
        carrier = Carrier(
            id="enterprise",
            name="USS Enterprise",
            position=Position(lat=32.0, lon=-175.0),
            course=240,
            speed=25,
            faction="us",
        )
        tf = TaskForce(
            name="TF16",
            faction="us",
            carriers=[carrier],
            course=240,
            speed=25,
        )
        assert tf.name == "TF16"
        assert len(tf.carriers) == 1
        assert tf.position.lat == 32.0

    def test_enemy_task_force(self):
        carrier = Carrier(
            id="akagi",
            name="Akagi",
            position=Position(lat=30.0, lon=-178.0),
            course=135,
            speed=25,
            faction="japan",
        )
        tf = TaskForce(
            name="Kido Butai",
            faction="japan",
            carriers=[carrier],
            course=135,
            speed=25,
        )
        assert tf.faction == "japan"
        assert tf.carriers[0].faction == "japan"


class TestPositionCalculation:
    """Test geographic calculations."""

    def test_move_north(self):
        """Moving north should increase latitude."""
        pos = Position(lat=32.0, lon=-175.0)
        new_pos = calculate_new_position(pos, course=0, distance_nm=60)
        assert new_pos.lat > 32.0
        assert abs(new_pos.lon - (-175.0)) < 0.1

    def test_move_south(self):
        """Moving south should decrease latitude."""
        pos = Position(lat=32.0, lon=-175.0)
        new_pos = calculate_new_position(pos, course=180, distance_nm=60)
        assert new_pos.lat < 32.0

    def test_move_east(self):
        """Moving east should increase longitude."""
        pos = Position(lat=32.0, lon=-175.0)
        new_pos = calculate_new_position(pos, course=90, distance_nm=60)
        assert new_pos.lon > -175.0

    def test_move_west(self):
        """Moving west should decrease longitude."""
        pos = Position(lat=32.0, lon=-175.0)
        new_pos = calculate_new_position(pos, course=270, distance_nm=60)
        assert new_pos.lon < -175.0

    def test_zero_distance(self):
        """Zero distance should not change position."""
        pos = Position(lat=32.0, lon=-175.0)
        new_pos = calculate_new_position(pos, course=90, distance_nm=0)
        assert abs(new_pos.lat - 32.0) < 0.001
        assert abs(new_pos.lon - (-175.0)) < 0.001

    def test_15_minutes_at_25_knots(self):
        """15 minutes at 25 knots = 6.25 nm."""
        pos = Position(lat=32.0, lon=-175.0)
        distance = 25 * (15 / 60)  # 6.25 nm
        new_pos = calculate_new_position(pos, course=240, distance_nm=distance)
        # Should move southwest
        assert new_pos.lat < 32.0
        assert new_pos.lon < -175.0


class TestEntityMovement:
    """Test entity position updates."""

    def test_carrier_moves(self):
        carrier = Carrier(
            id="enterprise",
            name="USS Enterprise",
            position=Position(lat=32.0, lon=-175.0),
            course=240,
            speed=25,
            faction="us",
        )
        original_lat = carrier.position.lat
        update_entity_position(carrier, minutes=15)
        assert carrier.position.lat != original_lat

    def test_task_force_moves(self):
        carrier = Carrier(
            id="enterprise",
            name="USS Enterprise",
            position=Position(lat=32.0, lon=-175.0),
            course=240,
            speed=25,
            faction="us",
        )
        tf = TaskForce(
            name="TF16",
            faction="us",
            carriers=[carrier],
            course=240,
            speed=25,
        )
        original_lat = tf.carriers[0].position.lat
        update_entity_position(tf, minutes=15)
        assert tf.carriers[0].position.lat != original_lat


class TestInitialState:
    """Test initial state with enemy fleet."""

    def test_state_has_enemy_fleet(self):
        state = build_initial_state()
        assert state.enemy_fleet is not None
        assert state.enemy_fleet.name == "Kido Butai"
        assert state.enemy_fleet.faction == "japan"

    def test_enemy_fleet_has_four_carriers(self):
        state = build_initial_state()
        assert len(state.enemy_fleet.carriers) == 4
        carrier_names = [c.name for c in state.enemy_fleet.carriers]
        assert "Akagi" in carrier_names
        assert "Kaga" in carrier_names
        assert "Soryu" in carrier_names
        assert "Hiryu" in carrier_names

    def test_enemy_fleet_has_course_and_speed(self):
        state = build_initial_state()
        assert state.enemy_fleet.course == 135
        assert state.enemy_fleet.speed == 25

    def test_enemy_carriers_have_positions(self):
        state = build_initial_state()
        for carrier in state.enemy_fleet.carriers:
            assert carrier.position.lat != 0
            assert carrier.position.lon != 0

    def test_enemy_carriers_are_japan(self):
        state = build_initial_state()
        for carrier in state.enemy_fleet.carriers:
            assert carrier.faction == "japan"


class TestRouteKinematics:
    """批次 C1：舰队航线运动学（docs/plans/ui-fidelity-fix-plan.md）。

    签名校正：calculate_new_position 第三参为 distance_nm（非 speed/minutes），
    按语义换算 distance_nm = speed × minutes / 60，断言意图不变。
    """

    @staticmethod
    def _pos(lat: float, lon: float) -> Position:
        return Position(lat=lat, lon=lon)

    def test_due_north_increases_lat(self):
        """航向 0°（北）：纬度增、经度不变。24 节 × 60 分钟 = 24 nm。"""
        pos = calculate_new_position(self._pos(28.0, -177.4), course=0,
                                     distance_nm=24 * 60 / 60)
        assert pos.lat > 28.0
        assert abs(pos.lon - (-177.4)) < 0.5

    def test_due_east_increases_lon_wrapped(self):
        """航向 90°（东）：经度跨 ±180° 包裹到 [-180, 180]。

        600 节 × 60 分钟 = 600 nm，自 179.5°E 东向跨日界线后
        数值上必落在西经（负值），故断言 pos.lon < 0。
        """
        pos = calculate_new_position(self._pos(28.0, 179.5), course=90,
                                     distance_nm=600 * 60 / 60)
        assert -180 <= pos.lon <= 180, f"经度未包裹: {pos.lon}"
        assert pos.lon < 0, f"跨 180° 后应落在西经（负值）: {pos.lon}"

    def test_zero_speed_stays(self):
        pos = calculate_new_position(self._pos(28.0, -177.4), course=135,
                                     distance_nm=0 * 60 / 60)
        assert (pos.lat, pos.lon) == (28.0, -177.4)

    def test_update_all_positions_moves_both_fleets(self):
        """⑤多舰队同 tick 一致性：全部 TF、敌舰队均移动，且 actual_enemy 同步。"""
        state = build_initial_state()
        before = [(tf.carriers[0].position.lat, tf.carriers[0].position.lon)
                  for tf in state.task_forces]
        enemy_before = [(c.position.lat, c.position.lon)
                        for c in state.enemy_fleet.carriers]
        update_all_positions(state, minutes=15)
        after = [(tf.carriers[0].position.lat, tf.carriers[0].position.lon)
                 for tf in state.task_forces]
        enemy_after = [(c.position.lat, c.position.lon)
                       for c in state.enemy_fleet.carriers]
        assert before != after and enemy_before != enemy_after
        # actual_enemy[0] 应与敌首舰移动后的位置精确同步
        assert state.actual_enemy[0]["position"] == {
            "lat": state.enemy_fleet.carriers[0].position.lat,
            "lon": state.enemy_fleet.carriers[0].position.lon,
        }


class TestPositionUpdateIntegration:
    """Test position updates integrated with game state."""

    def test_both_fleets_move_after_tick(self):
        state = build_initial_state()

        # Record initial positions
        us_carrier = state.task_forces[0].carriers[0]
        enemy_carrier = state.enemy_fleet.carriers[0]
        us_initial = (us_carrier.position.lat, us_carrier.position.lon)
        enemy_initial = (enemy_carrier.position.lat, enemy_carrier.position.lon)

        # Update positions
        update_all_positions(state, minutes=15)

        # Both should have moved
        us_new = (us_carrier.position.lat, us_carrier.position.lon)
        enemy_new = (enemy_carrier.position.lat, enemy_carrier.position.lon)

        assert us_new != us_initial
        assert enemy_new != enemy_initial

    def test_fleets_diverge_over_time(self):
        state = build_initial_state()

        # Record initial distance
        us_lat = state.task_forces[0].carriers[0].position.lat
        enemy_lat = state.enemy_fleet.carriers[0].position.lat
        initial_lat_diff = abs(us_lat - enemy_lat)

        # Update multiple ticks
        for _ in range(4):
            update_all_positions(state, minutes=15)

        # Check new distance
        us_lat = state.task_forces[0].carriers[0].position.lat
        enemy_lat = state.enemy_fleet.carriers[0].position.lat
        new_lat_diff = abs(us_lat - enemy_lat)

        # They should be moving in different directions (us=240°, enemy=135°)
        # so latitude difference should change
        assert new_lat_diff != initial_lat_diff
