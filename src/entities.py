"""Entity system for all game units.

Hierarchy:
    Entity (base)
    ├── NavalEntity
    │   ├── Carrier
    │   ├── Cruiser
    │   └── Destroyer
    └── AirEntity
        ├── ScoutMission
        ├── StrikeGroup
        └── CAPFighter
"""
import math
import logging
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("midway.entities")


class Position(BaseModel):
    """Geographic position."""
    lat: float
    lon: float

    def to_tuple(self) -> tuple:
        return (self.lat, self.lon)


class Entity(BaseModel):
    """Base class for all game entities."""
    id: str
    name: str
    position: Position


class NavalEntity(Entity):
    """Sea-based unit (carrier, cruiser, destroyer)."""
    course: int = Field(ge=0, le=359)  # Heading in degrees
    speed: int = Field(ge=0, le=35)    # Speed in knots
    faction: str = "us"  # "us" or "japan"


class Carrier(NavalEntity):
    """Aircraft carrier (enemy or friendly)."""
    air_groups: list = Field(default_factory=list)  # List of AirGroup dicts
    cap_strength: int = Field(default=0, ge=0)
    damage_level: int = Field(default=0, ge=0, le=3)


class AirEntity(Entity):
    """Flying unit (scout, strike, CAP)."""
    aircraft_type: str  # "PBY", "SBD", "TBD", "F4F", "Zero", etc.
    count: int = Field(ge=0)
    status: str = "deck"  # deck / launching / in_flight / returning / landed
    origin: str  # ID of source carrier or base
    destination: Optional[Position] = None
    speed: int = 150  # Flight speed in knots
    fuel_remaining: int = 100  # Percentage
    mission: str = "scout"  # scout / strike / cap
    faction: str = "us"


class TaskForce(BaseModel):
    """A fleet formation (carriers + escorts)."""
    name: str
    faction: str  # "us" or "japan"
    carriers: list[Carrier] = Field(default_factory=list)
    course: int = Field(ge=0, le=359)
    speed: int = Field(default=25, ge=0, le=35)

    @property
    def position(self) -> Position:
        """Fleet position = first carrier position."""
        if self.carriers:
            return self.carriers[0].position
        return Position(lat=0, lon=0)


def calculate_new_position(
    current: Position,
    course: int,
    distance_nm: float,
) -> Position:
    """Calculate new position after moving along a course.

    Args:
        current: Current position (lat, lon)
        course: Heading in degrees (0=N, 90=E, 180=S, 270=W)
        distance_nm: Distance to move in nautical miles

    Returns:
        New position
    """
    # Convert to radians
    lat1 = math.radians(current.lat)
    lon1 = math.radians(current.lon)
    bearing = math.radians(course)

    # Earth radius in nautical miles
    R = 3440.065

    # Calculate new position
    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance_nm / R) +
        math.cos(lat1) * math.sin(distance_nm / R) * math.cos(bearing)
    )

    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(distance_nm / R) * math.cos(lat1),
        math.cos(distance_nm / R) - math.sin(lat1) * math.sin(lat2)
    )

    return Position(lat=math.degrees(lat2), lon=math.degrees(lon2))


def update_entity_position(entity, minutes: int):
    """Update a naval entity's position based on course and speed.

    Args:
        entity: NavalEntity, Carrier, TaskForce, or legacy state.TaskForce
        minutes: Time elapsed in minutes
    """
    # Handle TaskForce (from entities.py or state.py)
    if hasattr(entity, 'carriers'):
        for carrier in entity.carriers:
            update_entity_position(carrier, minutes)
        return

    # Handle Carrier or NavalEntity (update in-place to preserve type)
    if hasattr(entity, 'course') and hasattr(entity, 'speed') and hasattr(entity, 'position'):
        distance_nm = entity.speed * (minutes / 60)
        if distance_nm > 0:
            old_lat, old_lon = entity.position.lat, entity.position.lon
            new_pos = calculate_new_position(
                entity.position, entity.course, distance_nm
            )
            entity.position.lat = new_pos.lat
            entity.position.lon = new_pos.lon
            logger.debug(
                f"[MOVE] {getattr(entity, 'id', getattr(entity, 'name', '?'))} moved "
                f"({old_lat:.2f},{old_lon:.2f}) → "
                f"({entity.position.lat:.2f},{entity.position.lon:.2f})"
            )


def update_all_positions(state, minutes: int):
    """Update positions of all entities in the game state.

    Args:
        state: GameState
        minutes: Time elapsed in minutes
    """
    # Update US task forces
    for tf in state.task_forces:
        update_entity_position(tf, minutes)

    # Update enemy fleet (if structured)
    if hasattr(state, '_enemy_fleet') and state._enemy_fleet:
        update_entity_position(state._enemy_fleet, minutes)

    logger.info(f"[POSITIONS] All positions updated for {minutes} min advance")
