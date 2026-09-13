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

from src.routes import RouteStatus, full_fleet_name

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
    # Zero distance is identity: avoids asin(sin(x)) float round-trip drift.
    if distance_nm == 0:
        return Position(lat=current.lat, lon=current.lon)

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

    # Wrap longitude to [-180, 180]
    lon_deg = math.degrees(lon2)
    while lon_deg > 180:
        lon_deg -= 360
    while lon_deg < -180:
        lon_deg += 360

    return Position(lat=math.degrees(lat2), lon=lon_deg)


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
    # 航线舰队由 advance_route_fleet 驱动（N.4），通用位移跳过避免双重移动
    route_bound = _route_bound_fleet_names(state)

    # Update US task forces
    for tf in state.task_forces:
        if tf.name in route_bound:
            continue
        update_entity_position(tf, minutes)

    # Update enemy fleet (if structured)
    if hasattr(state, 'enemy_fleet') and state.enemy_fleet:
        update_entity_position(state.enemy_fleet, minutes)

        # Sync actual_enemy positions from enemy_fleet
        if state.actual_enemy and state.enemy_fleet.carriers:
            for i, carrier in enumerate(state.enemy_fleet.carriers):
                if i < len(state.actual_enemy):
                    state.actual_enemy[i]["position"] = {
                        "lat": carrier.position.lat,
                        "lon": carrier.position.lon,
                    }

    logger.info(f"[POSITIONS] All positions updated for {minutes} min advance")


# ── 航线航行（N.4：舰队沿航路点按 speed 位移）──


def _route_bound_fleet_names(state) -> set:
    """所有 active 航线绑定的舰队全名集合（owner 短名经映射还原）。"""
    names = set()
    for route in getattr(state, "routes", []):
        if route.status == RouteStatus.ACTIVE:
            full = full_fleet_name(route.owner)
            if full:
                names.add(full)
    return names


def _route_cursor(route) -> int:
    """下一航路点下标（Route.progress，夹取到合法范围）。"""
    return max(0, min(route.progress, len(route.waypoints)))


def _advance_formation(fleet, bearing: float, distance_nm: float) -> None:
    """全队沿同一方位位移同一距离，保持队形。"""
    for carrier in fleet.carriers:
        new_pos = calculate_new_position(carrier.position, bearing, distance_nm)
        carrier.position.lat = new_pos.lat
        carrier.position.lon = new_pos.lon


def advance_route_fleet(state, route, minutes: int) -> None:
    """active 航线的 owner 舰队沿航路点按 speed 位移（N.4）。

    - bearing 对下一航路点实时推导
    - 剩余距离 ≤ 本 tick 位移：到点精确吸附并切下一段（Route.progress 推进）
    - 全部航路点完成 → route.status = done
    - 非 active 航线 / owner 未绑定舰队：静默跳过
    """
    if route.status != RouteStatus.ACTIVE:
        return

    full_name = full_fleet_name(route.owner)
    if full_name is None:
        logger.warning("[ROUTE] 航线 owner '%s' 未绑定舰队，跳过", route.owner)
        return
    fleet = next(
        (tf for tf in state.task_forces if tf.name == full_name), None
    )
    if fleet is None or not fleet.carriers:
        logger.warning("[ROUTE] 舰队 '%s' 不存在，跳过", route.owner)
        return

    # 延迟导入：scouting 依赖 src.state，模块级导入会成环
    from src.scouting import calculate_bearing, calculate_distance_nm

    remaining = fleet.speed * (minutes / 60)
    lead = fleet.carriers[0].position
    idx = _route_cursor(route)

    while remaining > 0 and idx < len(route.waypoints):
        target = route.waypoints[idx]
        current = (lead.lat, lead.lon)
        target_t = (target.lat, target.lon)
        dist_to_wp = calculate_distance_nm(current, target_t)
        bearing = calculate_bearing(current, target_t)

        if dist_to_wp <= remaining:
            # 到点：吸附切下一段
            _advance_formation(fleet, bearing, dist_to_wp)
            remaining -= dist_to_wp
            idx += 1
        else:
            _advance_formation(fleet, bearing, remaining)
            remaining = 0

        fleet.course = int(round(bearing)) % 360
        for carrier in fleet.carriers:
            carrier.course = int(round(bearing)) % 360

    route.progress = idx
    if idx >= len(route.waypoints):
        route.status = RouteStatus.DONE
        logger.info("[ROUTE] 航线 %s 航行完成（%s）", route.id[:8], route.owner)
