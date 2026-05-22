"""Tool definitions and handlers for NPC agents.

Tools follow OpenAI function-calling format. Handlers receive GameState and
mutate it in-place (for write tools) or return serialized data (for read tools).
"""
from src.state import GameState, ScoutMission
from src.recon_plan import create_recon_plan, ReconPlan

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI format)
# ---------------------------------------------------------------------------

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "query_fleet_status",
            "description": (
                "Query the current status of a task force: position, course, speed, "
                "carrier locations, CAP strength, and air group readiness (fuel, ammo, status)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_force_id": {
                        "type": "string",
                        "description": "Task force name or identifier, e.g. 'TF16' or 'Task Force 16'",
                    }
                },
                "required": ["task_force_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_recon",
            "description": (
                "Propose a reconnaissance plan to the commander. Use this when the player asks "
                "to send scouts or search for the enemy. This does NOT execute the plan — it creates "
                "a detailed proposal for the commander to review and confirm. "
                "The plan includes: aircraft count, search sector, range, altitude, timeline."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "Search direction, e.g. 'northwest', 'southwest', 'north'",
                    },
                    "aircraft_count": {
                        "type": "integer",
                        "description": "Number of PBY aircraft to deploy (default: 4)",
                    },
                    "range_nm": {
                        "type": "integer",
                        "description": "Search range in nautical miles (default: 200)",
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_action",
            "description": (
                "Execute a fleet action immediately. As Chief of Staff, you have the authority "
                "to adjust course and CAP strength directly. You do NOT need commander confirmation "
                "for these actions — execute first, report after. "
                "Use this when the commander gives an order or when you believe action is needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["set_course", "adjust_cap", "set_speed"],
                        "description": "Type of action to execute.",
                    },
                    "details": {
                        "type": "object",
                        "description": "Action-specific parameters, e.g. {'course': 220} or {'carrier': 'Enterprise', 'count': 16}",
                    },
                },
                "required": ["action_type", "details"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_query_fleet_status(state: GameState, task_force_id: str) -> str:
    """Return a human-readable summary of the requested task force."""
    tf = None
    for t in state.task_forces:
        if task_force_id.lower() in t.name.lower():
            tf = t
            break

    if tf is None:
        return f"Error: Task force '{task_force_id}' not found."

    lines = [
        f"Task Force: {tf.name}",
        f"  Position: {tf.carriers[0].position.lat:.1f}N {abs(tf.carriers[0].position.lon):.1f}W",
        f"  Course: {tf.course}°, Speed: {tf.speed} knots",
    ]

    for c in tf.carriers:
        lines.append(f"  Carrier: {c.name}")
        lines.append(f"    CAP: {c.cap_strength} fighters")
        for ag in c.air_groups:
            lines.append(
                f"    {ag.squadron_name or ag.type.value}: {ag.count} aircraft "
                f"({ag.status.value}, fuel {ag.fuel_pct}%, ammo {ag.ammo_pct}%)"
            )

    return "\n".join(lines)


def handle_execute_action(state: GameState, action_type: str, details: dict) -> str:
    """Execute an action directly. Mutates game state."""
    if action_type == "set_course":
        course = details.get("course")
        if course is None:
            return "Error: 'course' required in details."
        if not (0 <= course <= 359):
            return f"Error: Course {course} out of range (0-359)."
        for tf in state.task_forces:
            old = tf.course
            tf.course = course
            return f"航向已从 {old}° 调整至 {course}°。"
        return "Error: No task force found."

    elif action_type == "set_speed":
        speed = details.get("speed")
        if speed is None:
            return "Error: 'speed' required in details."
        if not (0 <= speed <= 35):
            return f"Error: Speed {speed} out of range (0-35)."
        for tf in state.task_forces:
            old = tf.speed
            tf.speed = speed
            return f"航速已从 {old} 节调整至 {speed} 节。"
        return "Error: No task force found."

    elif action_type == "adjust_cap":
        carrier_name = details.get("carrier", "")
        count = details.get("count")
        if count is None:
            return "Error: 'count' required in details."
        for tf in state.task_forces:
            for c in tf.carriers:
                if carrier_name.lower() in c.name.lower():
                    old = c.cap_strength
                    c.cap_strength = max(0, count)
                    return f"{c.name} 的 CAP 已从 {old} 架调整至 {count} 架。"
        return f"Error: Carrier '{carrier_name}' not found."

    elif action_type == "launch_scout":
        direction = details.get("direction", "northwest")
        count = details.get("count", 4)
        direction_map = {
            "northwest": 310, "north": 0, "northeast": 45,
            "east": 90, "southeast": 135, "south": 180,
            "southwest": 225, "west": 270,
        }
        heading = direction_map.get(direction.lower(), 310)
        spread = 30
        half = spread // 2
        bearing_min = (heading - half) % 360
        bearing_max = (heading + half) % 360

        mission_id = f"PBY-{len(state.active_scouts) + 1}"
        mission = ScoutMission(
            id=mission_id,
            direction=direction.lower(),
            heading=heading,
            launched_at=state.clock.game_time,
            eta_minutes=60,
            status="in_flight",
            search_bearing_min=bearing_min,
            search_bearing_max=bearing_max,
            search_distance_nm=200,
            aircraft_count=count,
        )
        state.active_scouts.append(mission)
        return (
            f"PBY {count} 架已起飞，搜索扇面 {bearing_min}°-{bearing_max}°，"
            f"约 200 海里。预计 1 小时后有报告。"
        )

    else:
        return f"Error: Unknown action type '{action_type}'."


def handle_propose_recon(state: GameState, direction: str, aircraft_count: int = 4, range_nm: int = 200) -> str:
    """Create a reconnaissance plan without executing it.

    Returns a formatted plan string for the commander to review.
    The plan is stored in state.pending_suggestions for later confirmation.
    """
    from src.recon_plan import create_recon_plan
    from src.state import PendingSuggestion
    from datetime import datetime

    # Get fleet position
    tf = state.task_forces[0]
    fleet_lat = tf.carriers[0].position.lat
    fleet_lon = tf.carriers[0].position.lon

    # Create plan
    plan = create_recon_plan(
        player_intent=direction,
        fleet_lat=fleet_lat,
        fleet_lon=fleet_lon,
        known_enemy=state.known_enemy,
        personality="aggressive"
    )

    # Override with player preferences if provided
    if aircraft_count != 4:
        plan.aircraft_count = aircraft_count
    if range_nm != 200:
        plan.range_nm = range_nm

    # Store as pending suggestion
    suggestion = PendingSuggestion(
        npc="Browning",
        action_type="launch_scout",
        details={
            "direction": direction,
            "aircraft_count": plan.aircraft_count,
            "range_nm": plan.range_nm,
            "sector_start": plan.sector_start,
            "sector_end": plan.sector_end,
        },
        proposed_at=datetime.utcnow(),
    )
    state.pending_suggestions.append(suggestion)

    return plan.to_display_string()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_HANDLERS = {
    "query_fleet_status": handle_query_fleet_status,
    "execute_action": handle_execute_action,
    "propose_recon": handle_propose_recon,
}


def set_course(state: GameState, task_force_id: str, course: int) -> str:
    """Directly set a task force's course. Called by app.py for manual override."""
    if not (0 <= course <= 359):
        return f"Error: Course {course} out of range (0-359)."

    for tf in state.task_forces:
        if task_force_id.lower() in tf.name.lower():
            old = tf.course
            tf.course = course
            return f"航向已从 {old}° 改为 {course}°。"

    return f"Error: Task force '{task_force_id}' not found."
