"""Event system for time-based triggers.

Events fire at specific game times when the player advances the clock.
Each event has a trigger time and a handler that modifies game state.
Also integrates with the scouting system to check for scout results.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from src.state import GameState, EnemyKnown, Position
from src.scouting import check_scout_results, check_pending_reports
from src.entities import update_all_positions
from src.spatial import update_spatial_index

logger = logging.getLogger("midway.events")


@dataclass
class GameEvent:
    """An event that triggers at a specific game time."""
    name: str
    trigger_time: datetime
    handler: Callable[[GameState], str]  # Returns notification text
    fired: bool = False


class EventScheduler:
    """Manages and triggers time-based events."""

    def __init__(self):
        self.events: list[GameEvent] = []
        self.notifications: list[str] = []

    def register(self, event: GameEvent):
        """Register an event."""
        self.events.append(event)
        logger.info(f"[EVENT] Registered: {event.name} at {event.trigger_time.strftime('%H:%M')}")

    def tick(self, state: GameState, minutes: int = 15) -> list[str]:
        """Advance game time and fire any due events. Returns notification texts."""
        self.notifications = []

        # Advance clock
        from datetime import timedelta
        state.clock.game_time += timedelta(minutes=minutes)
        logger.info(f"[CLOCK] Advanced {minutes} min → {state.clock.game_time.strftime('%H:%M')}")

        # Update all entity positions
        update_all_positions(state, minutes)

        # Update spatial index for fast queries
        update_spatial_index(state)

        # Check scouting results first
        scout_notifications = check_scout_results(state)
        self.notifications.extend(scout_notifications)

        # Check if any delayed reports have arrived
        report_notifications = check_pending_reports(state)
        self.notifications.extend(report_notifications)

        # Check and fire other events
        for event in self.events:
            if not event.fired and state.clock.game_time >= event.trigger_time:
                logger.info(f"[EVENT] Firing: {event.name}")
                notification = event.handler(state)
                event.fired = True
                self.notifications.append(notification)

        return self.notifications


# ── Event Handlers ──

def handle_midway_attack(state: GameState) -> str:
    """06:00 — Japanese attack on Midway."""
    msg = f"[{state.clock.game_time.strftime('%H:%M')}] 中途岛报告：遭日军空袭，敌机约100架"
    state.incoming_messages.append(msg)

    logger.info(f"[EVENT] Midway attack: {msg}")
    return "⚡ 中途岛遭日军空袭！"


# ── Pre-configured event sequence ──

def create_midway_events() -> EventScheduler:
    """Create the standard Midway event sequence.

    PBY reports are now driven by player scouting decisions,
    not hardcoded time triggers.
    """
    scheduler = EventScheduler()

    # 06:00 — Midway under attack (historical, not player-driven)
    scheduler.register(GameEvent(
        name="中途岛遭袭",
        trigger_time=datetime(1942, 6, 4, 6, 0, tzinfo=timezone.utc),
        handler=handle_midway_attack,
    ))

    return scheduler
