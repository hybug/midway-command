"""Tests for GameState models."""
from datetime import datetime, timezone

import pytest

from src.state import (
    AirGroup,
    AirGroupStatus,
    AirGroupType,
    Carrier,
    EnemyKnown,
    GameClock,
    GameState,
    Position,
    TaskForce,
)
from src.initial_state import build_initial_state


class TestInitialState:
    """Verify initial state matches historical facts."""

    def test_game_time(self):
        state = build_initial_state()
        assert state.clock.game_time.hour == 4
        assert state.clock.game_time.minute == 0
        assert state.clock.game_time.day == 4
        assert state.clock.game_time.month == 6
        assert state.clock.game_time.year == 1942

    def test_tf16_course_and_speed(self):
        state = build_initial_state()
        tf16 = state.task_forces[0]
        assert tf16.name == "Task Force 16"
        assert tf16.course == 240
        assert tf16.speed == 25

    def test_tf16_position(self):
        state = build_initial_state()
        tf16 = state.task_forces[0]
        # Approx 32°N 175°W
        assert 31.5 <= tf16.carriers[0].position.lat <= 32.5
        assert -175.5 <= tf16.carriers[0].position.lon <= -174.5

    def test_two_carriers(self):
        state = build_initial_state()
        tf16 = state.task_forces[0]
        assert len(tf16.carriers) == 2
        names = [c.name for c in tf16.carriers]
        assert "USS Enterprise (CV-6)" in names
        assert "USS Hornet (CV-8)" in names

    def test_air_group_counts(self):
        state = build_initial_state()
        enterprise = state.task_forces[0].carriers[0]

        fighters = [ag for ag in enterprise.air_groups if ag.type == AirGroupType.FIGHTER]
        dive_bombers = [ag for ag in enterprise.air_groups if ag.type == AirGroupType.DIVE_BOMBER]
        torpedo = [ag for ag in enterprise.air_groups if ag.type == AirGroupType.TORPEDO]

        assert len(fighters) == 1
        assert len(dive_bombers) == 1
        assert len(torpedo) == 1
        assert fighters[0].count == 27
        assert dive_bombers[0].count == 38
        assert torpedo[0].count == 15

    def test_air_groups_ready(self):
        state = build_initial_state()
        for tf in state.task_forces:
            for carrier in tf.carriers:
                for ag in carrier.air_groups:
                    assert ag.status == AirGroupStatus.READY
                    assert ag.fuel_pct == 100
                    assert ag.ammo_pct == 100

    def test_known_enemy_empty(self):
        state = build_initial_state()
        assert state.known_enemy == []

    def test_hidden_enemy_exists(self):
        state = build_initial_state()
        assert state._hidden_actual_enemy is not None
        assert len(state._hidden_actual_enemy) == 1
        assert state._hidden_actual_enemy[0]["name"] == "Kido Butai"


class TestSerialization:
    """Verify Pydantic serialization works."""

    def test_state_serializes_to_json(self):
        state = build_initial_state()
        json_str = state.model_dump_json(indent=2)
        assert "Task Force 16" in json_str
        assert "USS Enterprise" in json_str

    def test_hidden_enemy_excluded_from_json(self):
        state = build_initial_state()
        json_str = state.model_dump_json()
        assert "Kido Butai" not in json_str
        assert "_hidden_actual_enemy" not in json_str

    def test_round_trip(self):
        state = build_initial_state()
        json_str = state.model_dump_json()
        parsed = GameState.model_validate_json(json_str)
        assert parsed.task_forces[0].name == "Task Force 16"
        assert parsed.clock.game_time.hour == 4


class TestQueryFunctions:
    """Verify query_* functions don't leak actual state."""

    def test_state_summary_excludes_hidden_enemy(self):
        from src.agents.base import NPCAgent

        class TestAgent(NPCAgent):
            name = "Test"

            def build_system_prompt(self, state):
                return "test"

        agent = TestAgent()
        state = build_initial_state()
        summary = agent.get_state_summary(state)

        assert "_hidden" not in str(summary)
        assert "Kido Butai" not in str(summary)
        assert summary["known_enemy"] == "None"

    def test_state_summary_includes_fleet_data(self):
        from src.agents.base import NPCAgent

        class TestAgent(NPCAgent):
            name = "Test"

            def build_system_prompt(self, state):
                return "test"

        agent = TestAgent()
        state = build_initial_state()
        summary = agent.get_state_summary(state)

        assert summary["game_time"] == "04:00"
        assert len(summary["task_forces"]) == 1
        assert summary["task_forces"][0]["name"] == "Task Force 16"
        assert len(summary["task_forces"][0]["carriers"]) == 2
