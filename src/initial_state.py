"""Build the initial game state for June 4, 1942, 04:00.

All data sourced from docs/HISTORICAL_NOTES.md.
Times are Zone +12 (Midway time zone).
"""
from datetime import datetime, timezone

from src.state import (
    AirGroup,
    AirGroupStatus,
    AirGroupType,
    Carrier,
    GameClock,
    GameState,
    Position,
    TaskForce,
    TurnType,
)
from src.entities import (
    TaskForce as EntityTaskForce,
    Carrier as EntityCarrier,
    Position as EntityPosition,
)


def build_initial_state() -> GameState:
    """Return the historical opening state at 04:00, June 4, 1942."""

    # TF16 position: approx 32°N 175°W, course 240°, speed 25 knots
    tf16_position = Position(lat=32.0, lon=-175.0)

    # USS Enterprise (CV-6) — flagship
    enterprise = Carrier(
        name="USS Enterprise (CV-6)",
        position=tf16_position,
        cap_strength=12,
        air_groups=[
            AirGroup(
                type=AirGroupType.FIGHTER,
                count=27,
                status=AirGroupStatus.READY,
                squadron_name="VF-6",
            ),
            AirGroup(
                type=AirGroupType.DIVE_BOMBER,
                count=38,
                status=AirGroupStatus.READY,
                squadron_name="VB-6/VS-6",
            ),
            AirGroup(
                type=AirGroupType.TORPEDO,
                count=15,
                status=AirGroupStatus.READY,
                squadron_name="VT-6",
            ),
        ],
    )

    # USS Hornet (CV-8)
    hornet = Carrier(
        name="USS Hornet (CV-8)",
        position=tf16_position,
        cap_strength=12,
        air_groups=[
            AirGroup(
                type=AirGroupType.FIGHTER,
                count=27,
                status=AirGroupStatus.READY,
                squadron_name="VF-8",
            ),
            AirGroup(
                type=AirGroupType.DIVE_BOMBER,
                count=38,
                status=AirGroupStatus.READY,
                squadron_name="VB-8/VS-8",
            ),
            AirGroup(
                type=AirGroupType.TORPEDO,
                count=15,
                status=AirGroupStatus.READY,
                squadron_name="VT-8",
            ),
        ],
    )

    # TF16
    tf16 = TaskForce(
        name="Task Force 16",
        carriers=[enterprise, hornet],
        course=240,
        speed=25,
    )

    # Game clock: June 4, 1942, 04:00
    clock = GameClock(
        game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc),
        tick_minutes=15,
    )

    state = GameState(
        clock=clock,
        task_forces=[tf16],
        known_enemy=[],
        incoming_messages=[],
        turn_type=TurnType.NORMAL,
        action_points=3,
        max_action_points=3,
    )
    # Enemy fleet (structured entity)
    akagi = EntityCarrier(
        id="akagi",
        name="Akagi",
        position=EntityPosition(lat=30.0, lon=-178.0),
        course=135,
        speed=25,
        faction="japan",
        cap_strength=12,
        air_groups=[],
    )
    kaga = EntityCarrier(
        id="kaga",
        name="Kaga",
        position=EntityPosition(lat=30.1, lon=-178.1),
        course=135,
        speed=25,
        faction="japan",
        cap_strength=12,
        air_groups=[],
    )
    soryu = EntityCarrier(
        id="soryu",
        name="Soryu",
        position=EntityPosition(lat=29.9, lon=-177.9),
        course=135,
        speed=25,
        faction="japan",
        cap_strength=12,
        air_groups=[],
    )
    hiryu = EntityCarrier(
        id="hiryu",
        name="Hiryu",
        position=EntityPosition(lat=30.0, lon=-178.2),
        course=135,
        speed=25,
        faction="japan",
        cap_strength=12,
        air_groups=[],
    )

    kido_butai = EntityTaskForce(
        name="Kido Butai",
        faction="japan",
        carriers=[akagi, kaga, soryu, hiryu],
        course=135,
        speed=25,
    )

    state._enemy_fleet = kido_butai

    state._hidden_actual_enemy = [
        {
            "name": "Kido Butai",
            "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"],
            "position": {"lat": 30.0, "lon": -178.0},
            "status": "rearming_for_midway_attack",
            "aircraft_total": 248,
        }
    ]
    return state
