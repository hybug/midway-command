"""Build the initial game state for June 4, 1942, 04:00.

All data sourced from docs/HISTORICAL_NOTES.md.
Times are Zone +12 (Midway time zone).
"""
from datetime import datetime, timezone

from src.state import (
    AirGroup,
    AirGroupStatus,
    AirGroupType,
    Aircraft,
    AircraftType,
    AircraftStatus,
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

    # TF16 position: ~200nm NE of Midway, course 240°, speed 25 knots
    # Historical: Nimitz ordered TF16 to ambush position NE of Midway
    tf16_position = Position(lat=31.5, lon=-176.0)

    # ── Helper: generate aircraft list for a carrier ──
    def make_aircraft(carrier_name: str, squadron: str, aircraft_type: AircraftType,
                      count: int, key_pilots: dict = None) -> list[Aircraft]:
        """Generate a list of Aircraft objects for a squadron."""
        aircraft = []
        for i in range(1, count + 1):
            aid = f"{aircraft_type.value}-{squadron}-{i:02d}"
            is_key = bool(key_pilots and i in key_pilots)
            pilot = key_pilots.get(i) if is_key else None
            aircraft.append(Aircraft(
                id=aid,
                type=aircraft_type,
                squadron=squadron,
                carrier=carrier_name,
                status=AircraftStatus.READY,
                fuel_pct=100.0,
                ammo_pct=100.0,
                ordnance="500lb_bomb" if aircraft_type == AircraftType.SBD else
                         "torpedo" if aircraft_type == AircraftType.TBD else "none",
                is_key_pilot=is_key,
                pilot_name=pilot,
            ))
        return aircraft

    # Enterprise aircraft
    ent_fighters = make_aircraft("Enterprise", "VF-6", AircraftType.VF, 27)
    ent_dive = make_aircraft("Enterprise", "VB-6", AircraftType.SBD, 38,
                             key_pilots={1: "C. Wade McClusky (CAG)"})
    ent_torpedo = make_aircraft("Enterprise", "VT-6", AircraftType.TBD, 15)
    enterprise_aircraft = ent_fighters + ent_dive + ent_torpedo

    # Hornet aircraft
    hor_fighters = make_aircraft("Hornet", "VF-8", AircraftType.VF, 27)
    hor_dive = make_aircraft("Hornet", "VB-8", AircraftType.SBD, 38)
    hor_torpedo = make_aircraft("Hornet", "VT-8", AircraftType.TBD, 15,
                                key_pilots={1: "John C. Waldron (CDR)"})
    hornet_aircraft = hor_fighters + hor_dive + hor_torpedo

    # USS Enterprise (CV-6) — flagship
    # Each carrier needs its own Position object (no shared references)
    enterprise = Carrier(
        name="USS Enterprise (CV-6)",
        position=Position(lat=tf16_position.lat, lon=tf16_position.lon),
        cap_strength=12,
        air_groups=[
            AirGroup(type=AirGroupType.FIGHTER, count=27, squadron_name="VF-6"),
            AirGroup(type=AirGroupType.DIVE_BOMBER, count=38, squadron_name="VB-6/VS-6"),
            AirGroup(type=AirGroupType.TORPEDO, count=15, squadron_name="VT-6"),
        ],
        aircraft=enterprise_aircraft,
    )

    # USS Hornet (CV-8)
    hornet = Carrier(
        name="USS Hornet (CV-8)",
        position=Position(lat=tf16_position.lat, lon=tf16_position.lon),
        cap_strength=12,
        air_groups=[
            AirGroup(type=AirGroupType.FIGHTER, count=27, squadron_name="VF-8"),
            AirGroup(type=AirGroupType.DIVE_BOMBER, count=38, squadron_name="VB-8/VS-8"),
            AirGroup(type=AirGroupType.TORPEDO, count=15, squadron_name="VT-8"),
        ],
        aircraft=hornet_aircraft,
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
    # Kido Butai: ~240nm NW of Midway (bearing ~315°)
    # Historical: approaching from NW, moving ESE toward Midway
    akagi = EntityCarrier(
        id="akagi",
        name="Akagi",
        position=EntityPosition(lat=31.0, lon=-180.0),
        course=110,
        speed=20,
        faction="japan",
        cap_strength=12,
        air_groups=[],
    )
    kaga = EntityCarrier(
        id="kaga",
        name="Kaga",
        position=EntityPosition(lat=31.1, lon=-180.1),
        course=110,
        speed=20,
        faction="japan",
        cap_strength=12,
        air_groups=[],
    )
    soryu = EntityCarrier(
        id="soryu",
        name="Soryu",
        position=EntityPosition(lat=30.9, lon=-179.9),
        course=110,
        speed=20,
        faction="japan",
        cap_strength=12,
        air_groups=[],
    )
    hiryu = EntityCarrier(
        id="hiryu",
        name="Hiryu",
        position=EntityPosition(lat=31.05, lon=-179.95),
        course=110,
        speed=20,
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

    state.enemy_fleet = kido_butai

    state.actual_enemy = [
        {
            "name": "Kido Butai",
            "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"],
            "position": {"lat": 31.0, "lon": -180.0},
            "status": "rearming_for_midway_attack",
            "aircraft_total": 248,
        }
    ]
    return state
