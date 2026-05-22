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
        assert state._enemy_fleet is not None
        assert state._enemy_fleet.name == "Kido Butai"
        assert state._enemy_fleet.faction == "japan"

    def test_enemy_fleet_has_four_carriers(self):
        state = build_initial_state()
        assert len(state._enemy_fleet.carriers) == 4
        carrier_names = [c.name for c in state._enemy_fleet.carriers]
        assert "Akagi" in carrier_names
        assert "Kaga" in carrier_names
        assert "Soryu" in carrier_names
        assert "Hiryu" in carrier_names

    def test_enemy_fleet_has_course_and_speed(self):
        state = build_initial_state()
        assert state._enemy_fleet.course == 135
        assert state._enemy_fleet.speed == 25

    def test_enemy_carriers_have_positions(self):
        state = build_initial_state()
        for carrier in state._enemy_fleet.carriers:
            assert carrier.position.lat != 0
            assert carrier.position.lon != 0

    def test_enemy_carriers_are_japan(self):
        state = build_initial_state()
        for carrier in state._enemy_fleet.carriers:
            assert carrier.faction == "japan"


class TestPositionUpdateIntegration:
    """Test position updates integrated with game state."""

    def test_both_fleets_move_after_tick(self):
        state = build_initial_state()

        # Record initial positions
        us_carrier = state.task_forces[0].carriers[0]
        enemy_carrier = state._enemy_fleet.carriers[0]
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
        enemy_lat = state._enemy_fleet.carriers[0].position.lat
        initial_lat_diff = abs(us_lat - enemy_lat)

        # Update multiple ticks
        for _ in range(4):
            update_all_positions(state, minutes=15)

        # Check new distance
        us_lat = state.task_forces[0].carriers[0].position.lat
        enemy_lat = state._enemy_fleet.carriers[0].position.lat
        new_lat_diff = abs(us_lat - enemy_lat)

        # They should be moving in different directions (us=240°, enemy=135°)
        # so latitude difference should change
        assert new_lat_diff != initial_lat_diff
