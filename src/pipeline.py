"""Tick Pipeline -- executes game logic steps in order.

Each tick consists of multiple TickStep instances, executed by ascending order.
If a step raises an exception, the error is logged and the step is skipped.
"""
import logging
from dataclasses import dataclass
from datetime import timedelta, datetime, timezone
from typing import Callable

from src.state import GameState, GamePhase

logger = logging.getLogger("midway.pipeline")

GAME_OVER_TIME = datetime(1942, 6, 4, 8, 0, tzinfo=timezone.utc)


def advance_clock(state: GameState, minutes: int) -> list[str]:
    """Step 10: advance the game clock."""
    state.clock.game_time += timedelta(minutes=minutes)
    logger.info("[CLOCK] Advanced %dmin -> %s", minutes, state.clock.game_time.strftime("%H:%M"))
    return []


def update_positions(state: GameState, minutes: int) -> list[str]:
    """Step 20: update all entity positions."""
    from src.entities import update_all_positions
    update_all_positions(state, minutes)
    return []


def advance_routes(state: GameState, minutes: int) -> list[str]:
    """Step 25: move route-bound fleets along active route waypoints (N.4)."""
    from src.entities import advance_route_fleet
    for route in state.routes:
        advance_route_fleet(state, route, minutes)
    return []


def update_spatial_index(state: GameState, minutes: int) -> list[str]:
    """Step 30: rebuild spatial index."""
    from src.spatial import update_spatial_index as rebuild
    rebuild(state)
    return []


def process_scouting(state: GameState, minutes: int) -> list[str]:
    """Step 40: check scouting results."""
    from src.scouting import check_scout_results
    return check_scout_results(state)


def process_intel_step(state: GameState, minutes: int) -> list[str]:
    """Step 50: 情报流——电文到达/旗舰收报/登记路由/工作项（S2.3 起替代旧 pending reports）。"""
    from src.intel.flow import process_intel
    return process_intel(state)


def process_staff_step(state: GameState, minutes: int) -> list[str]:
    """Step 55: S4 指挥链——链上报告逐跳上呈（送达触发可选提醒钩子）。"""
    from src.staff import service as staff
    from src.staff.roster import get_active_roster
    return staff.process_staff_step(state, minutes, roster=get_active_roster())


def process_orders_step(state: GameState, minutes: int) -> list[str]:
    """Step 57: S5 命令——S2 送达判定 → EXACT 激活 / INTENT 待批 → 执行与报告回传。"""
    from src.orders import service as orders
    from src.staff.roster import get_active_roster
    return orders.process_orders_step(state, minutes, roster=get_active_roster())


def fire_events(state: GameState, minutes: int) -> list[str]:
    """Step 60: fire due events (placeholder -- wired via EventScheduler)."""
    return []


def check_game_over(state: GameState, minutes: int) -> list[str]:
    """Step 70: check whether the game should end.

    Ends when:
      - game_time >= 08:00  (TIME-SM-001)
      - All carriers sunk   (TIME-SM-002)
    """
    if state.game_phase == GamePhase.GAME_OVER:
        return []

    if state.clock.game_time >= GAME_OVER_TIME:
        state.game_phase = GamePhase.GAME_OVER
        logger.info("[GAME_OVER] Time limit reached (08:00)")
        return ["TIME'S UP -- 08:00 reached. Game over."]

    all_carriers = [c for tf in state.task_forces for c in tf.carriers]
    if all_carriers and all(c.damage_level >= 3 for c in all_carriers):
        state.game_phase = GamePhase.GAME_OVER
        logger.info("[GAME_OVER] All carriers sunk")
        return ["All carriers sunk. Game over."]

    return []


def reset_ap(state: GameState, minutes: int) -> list[str]:
    """Step 80: reset action points to max."""
    state.action_points = state.max_action_points
    logger.info("[AP] Reset to %d", state.action_points)
    return []


@dataclass
class TickStep:
    """A single step in the pipeline."""
    name: str
    handler: Callable[[GameState, int], list[str]]
    order: int
    enabled: bool = True


class Pipeline:
    """Tick pipeline: executes registered steps in order."""

    def __init__(self):
        self.steps: list[TickStep] = []

    def register(self, step: TickStep):
        self.steps = [s for s in self.steps if s.name != step.name]
        self.steps.append(step)
        self.steps.sort(key=lambda s: s.order)
        logger.info("[PIPELINE] Registered: %s (order=%d)", step.name, step.order)

    def disable(self, name: str):
        for step in self.steps:
            if step.name == name:
                step.enabled = False

    def enable(self, name: str):
        for step in self.steps:
            if step.name == name:
                step.enabled = True

    def execute(self, state: GameState, minutes: int = 15) -> list[str]:
        """Execute all enabled steps; collect notifications."""
        all_notifications: list[str] = []
        for step in self.steps:
            if not step.enabled:
                continue
            try:
                notes = step.handler(state, minutes)
                if notes:
                    all_notifications.extend(notes)
            except Exception as e:
                logger.error("[PIPELINE] Step '%s' failed: %s", step.name, e, exc_info=True)
        return all_notifications


def build_default_pipeline() -> Pipeline:
    """Create the standard Midway pipeline with all steps registered."""
    p = Pipeline()
    p.register(TickStep("advance_clock",       advance_clock,       10))
    p.register(TickStep("update_positions",    update_positions,    20))
    p.register(TickStep("advance_routes",      advance_routes,      25))
    p.register(TickStep("update_spatial_index",update_spatial_index,30))
    p.register(TickStep("process_scouting",    process_scouting,    40))
    p.register(TickStep("process_intel",       process_intel_step,  50))
    p.register(TickStep("process_staff",       process_staff_step,  55))
    p.register(TickStep("process_orders",      process_orders_step, 57))
    p.register(TickStep("fire_events",         fire_events,         60))
    p.register(TickStep("check_game_over",     check_game_over,     70))
    p.register(TickStep("reset_ap",            reset_ap,            80))
    return p
