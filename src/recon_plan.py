"""Reconnaissance planning system.

Generates detailed reconnaissance plans for the player to approve.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("midway.recon")


@dataclass
class ReconPlan:
    """A detailed reconnaissance mission plan."""
    # Aircraft info
    aircraft_type: str = "SBD"  # SBD Dauntless (侦察型)
    aircraft_count: int = 4
    source_carrier: str = "Enterprise"

    # Search parameters
    sector_start: int = 280  # degrees
    sector_end: int = 340    # degrees
    range_nm: int = 200      # nautical miles
    altitude_ft: int = 1000  # feet

    # Timeline (will be calculated)
    launch_time: str = ""
    arrive_sector: str = ""
    search_complete: str = ""
    recovery_time: str = ""
    expected_report: str = ""

    # Notes
    notes: str = ""

    # Status
    status: str = "pending"  # pending / confirmed / in_progress / completed

    def calculate_timeline(self, current_time: datetime):
        """Calculate mission timeline based on current time."""
        # Launch preparation: 15 minutes
        launch_dt = current_time + timedelta(minutes=15)
        self.launch_time = launch_dt.strftime("%H:%M")

        # Flight to sector: ~45 minutes (depends on range)
        arrive_dt = launch_dt + timedelta(minutes=45)
        self.arrive_sector = arrive_dt.strftime("%H:%M")

        # Search time: ~60 minutes
        search_dt = arrive_dt + timedelta(minutes=60)
        self.search_complete = search_dt.strftime("%H:%M")

        # Return flight: ~45 minutes
        recovery_dt = search_dt + timedelta(minutes=45)
        self.recovery_time = recovery_dt.strftime("%H:%M")

        # Expected report: during search
        report_dt = arrive_dt + timedelta(minutes=30)
        self.expected_report = f"{report_dt.strftime('%H:%M')} - {search_dt.strftime('%H:%M')}"

    def to_display_string(self) -> str:
        """Format plan for display to player using military order format."""
        from src.order_renderer import create_recon_order, OrderRenderer

        order = create_recon_order(
            aircraft_type=self.aircraft_type,
            aircraft_count=self.aircraft_count,
            carrier=self.source_carrier,
            sector_start=self.sector_start,
            sector_end=self.sector_end,
            range_nm=self.range_nm,
            altitude_ft=self.altitude_ft,
            launch_time=self.launch_time,
            arrive_sector=self.arrive_sector,
            search_complete=self.search_complete,
            recovery_time=self.recovery_time,
            expected_report=self.expected_report,
            notes=self.notes,
        )
        renderer = OrderRenderer()
        return renderer.render(order)


def create_recon_plan(
    player_intent: str,
    fleet_lat: float,
    fleet_lon: float,
    known_enemy: list,
    personality: str = "aggressive"
) -> ReconPlan:
    """Create a reconnaissance plan based on player intent and situation.

    Args:
        player_intent: What the player wants to search (e.g., "northwest")
        fleet_lat: Current fleet latitude
        fleet_lon: Current fleet longitude
        known_enemy: List of known enemy contacts
        personality: NPC personality (affects plan parameters)

    Returns:
        ReconPlan with all parameters filled
    """
    plan = ReconPlan()

    # Parse direction from player intent
    direction_map = {
        "north": (330, 30),
        "northeast": (30, 90),
        "east": (60, 120),
        "southeast": (120, 180),
        "south": (150, 210),
        "southwest": (210, 270),
        "west": (240, 300),
        "northwest": (280, 340),
    }

    # Default to northwest if not specified
    sector = (280, 340)
    for direction, angles in direction_map.items():
        if direction in player_intent.lower():
            sector = angles
            break

    plan.sector_start = sector[0]
    plan.sector_end = sector[1]

    # Apply personality bias
    if personality == "aggressive":
        # Browning: more aircraft, narrower sector, longer range
        plan.aircraft_count = 6
        plan.range_nm = 250
        plan.altitude_ft = 1500
        plan.notes = "优先搜索情报指示方向，集中力量"
    else:
        # Conservative: fewer aircraft, wider sector
        plan.aircraft_count = 4
        plan.range_nm = 200
        plan.altitude_ft = 1000
        plan.notes = "广泛搜索，覆盖更多区域"

    # Adjust based on known enemy
    if known_enemy:
        last_contact = known_enemy[-1]
        plan.notes += f"。参考上次接触: {last_contact.description}"

    # Calculate timeline
    plan.calculate_timeline(datetime(1942, 6, 4, 4, 0))

    logger.info(f"[RECON] Created plan: {plan.aircraft_count} aircraft, "
                f"sector {plan.sector_start}-{plan.sector_end}°, "
                f"range {plan.range_nm}nm")

    return plan
