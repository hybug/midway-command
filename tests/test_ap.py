"""Tests for Action Point (AP) system."""
import pytest
from datetime import datetime, timezone

from src.state import GameState, GameClock, TurnType
from src.ap import consume_ap, has_ap, reset_ap, get_ap_status, init_turn


def make_test_state(ap=3, max_ap=None, turn_type=TurnType.NORMAL):
    """Create a minimal GameState for testing.

    If max_ap is None, uses the default for the given turn_type.
    If max_ap is explicitly provided, overrides after init_turn.
    """
    state = GameState(
        clock=GameClock(
            game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc),
            tick_minutes=15,
        ),
        task_forces=[],
        turn_type=turn_type,
        action_points=ap,
        max_action_points=3,
    )
    init_turn(state, turn_type)
    if max_ap is not None:
        state.max_action_points = max_ap
    state.action_points = ap
    return state


class TestAPConsumption:
    """Test AP consumption logic."""

    def test_consume_ap_success(self):
        state = make_test_state(ap=3)
        assert consume_ap(state, "test") is True
        assert state.action_points == 2

    def test_consume_ap_multiple(self):
        state = make_test_state(ap=3)
        consume_ap(state, "test1")
        consume_ap(state, "test2")
        assert state.action_points == 1

    def test_consume_ap_zero(self):
        state = make_test_state(ap=0)
        assert consume_ap(state, "test") is False
        assert state.action_points == 0

    def test_consume_ap_cannot_go_negative(self):
        state = make_test_state(ap=1)
        consume_ap(state, "test1")
        assert consume_ap(state, "test2") is False
        assert state.action_points == 0


class TestAPCheck:
    """Test AP availability check."""

    def test_has_ap_true(self):
        state = make_test_state(ap=3)
        assert has_ap(state) is True

    def test_has_ap_false(self):
        state = make_test_state(ap=0)
        assert has_ap(state) is False

    def test_has_ap_one(self):
        state = make_test_state(ap=1)
        assert has_ap(state) is True


class TestAPReset:
    """Test AP reset logic."""

    def test_reset_ap(self):
        state = make_test_state(ap=1, max_ap=3)
        reset_ap(state)
        assert state.action_points == 3

    def test_reset_ap_different_max(self):
        state = make_test_state(ap=0, max_ap=5)
        reset_ap(state)
        assert state.action_points == 5


class TestAPStatus:
    """Test AP status reporting."""

    def test_get_ap_status(self):
        state = make_test_state(ap=2, max_ap=3, turn_type=TurnType.NORMAL)
        status = get_ap_status(state)
        assert status["current"] == 2
        assert status["max"] == 3
        assert status["turn_type"] == "normal"
        assert status["can_act"] is True

    def test_get_ap_status_no_ap(self):
        state = make_test_state(ap=0, max_ap=3)
        status = get_ap_status(state)
        assert status["current"] == 0
        assert status["can_act"] is False


class TestTurnTypes:
    """Test different turn types."""

    def test_normal_turn(self):
        state = make_test_state(turn_type=TurnType.NORMAL)
        assert state.max_action_points == 3

    def test_critical_turn(self):
        state = make_test_state(turn_type=TurnType.CRITICAL)
        assert state.max_action_points == 5

    def test_emergency_turn(self):
        state = make_test_state(turn_type=TurnType.EMERGENCY)
        assert state.max_action_points == 2
