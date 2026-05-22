"""Action Point (AP) system for turn-based gameplay.

Each turn has a limited number of actions. Dialogue and commands consume AP.
Waiting does not consume AP. When AP runs out, the player must advance time.
"""
import logging
from src.state import GameState, TurnType

logger = logging.getLogger("midway.ap")

# AP configuration per turn type
AP_CONFIG = {
    TurnType.NORMAL: 3,
    TurnType.CRITICAL: 5,
    TurnType.EMERGENCY: 2,
}


def get_max_ap(turn_type: TurnType) -> int:
    """Get the maximum AP for a given turn type."""
    return AP_CONFIG.get(turn_type, 3)


def init_turn(state: GameState, turn_type: TurnType = TurnType.NORMAL):
    """Initialize a new turn with the given type."""
    state.turn_type = turn_type
    state.max_action_points = get_max_ap(turn_type)
    state.action_points = state.max_action_points
    logger.info(f"[AP] New turn: {turn_type.value}, AP={state.action_points}")


def consume_ap(state: GameState, action: str = "action") -> bool:
    """Consume 1 AP for an action. Returns True if successful, False if no AP left."""
    if state.action_points <= 0:
        logger.warning(f"[AP] Cannot consume AP for '{action}': no AP left")
        return False
    state.action_points -= 1
    logger.info(f"[AP] Consumed 1 AP for '{action}', remaining={state.action_points}")
    return True


def has_ap(state: GameState) -> bool:
    """Check if there are AP remaining."""
    return state.action_points > 0


def reset_ap(state: GameState):
    """Reset AP to max (called when advancing time)."""
    state.action_points = state.max_action_points
    logger.info(f"[AP] Reset AP to {state.action_points}")


def get_ap_status(state: GameState) -> dict:
    """Get current AP status for display."""
    return {
        "current": state.action_points,
        "max": state.max_action_points,
        "turn_type": state.turn_type.value,
        "can_act": has_ap(state),
    }
