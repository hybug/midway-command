"""Spatial index system using hex grid as spatial hash.

Provides fast queries for game logic:
- What entities are in a hex cell?
- What hex is an entity in?
- Which hexes are in range of a point?
- Is entity A in range of entity B?

Geographic coordinates remain the truth source.
Hex grid is the spatial index for fast lookups.
"""
import logging
from collections import defaultdict
from typing import Optional

from src.render.coordinate import world_to_hex, hex_distance, hex_to_world, CELL_SIZE_NM

logger = logging.getLogger("midway.spatial")


class SpatialIndex:
    """Hex-based spatial index for game entities.

    Maps entity IDs to hex cells, and provides fast spatial queries.
    Updated each tick when entity positions change.
    """

    def __init__(self):
        # entity_id -> (q, r) hex position
        self.entity_positions: dict[str, tuple[int, int]] = {}
        # (q, r) -> set of entity_ids in that cell
        self.hex_entities: dict[tuple[int, int], set[str]] = defaultdict(set)

    def clear(self):
        """Clear all index data."""
        self.entity_positions.clear()
        self.hex_entities.clear()

    def update_entity(self, entity_id: str, lat: float, lon: float):
        """Update an entity's position in the index."""
        q, r = world_to_hex(lat, lon)
        new_pos = (q, r)

        # Remove from old position
        old_pos = self.entity_positions.get(entity_id)
        if old_pos and old_pos in self.hex_entities:
            self.hex_entities[old_pos].discard(entity_id)
            if not self.hex_entities[old_pos]:
                del self.hex_entities[old_pos]

        # Add to new position
        self.entity_positions[entity_id] = new_pos
        self.hex_entities[new_pos].add(entity_id)

    def remove_entity(self, entity_id: str):
        """Remove an entity from the index."""
        old_pos = self.entity_positions.pop(entity_id, None)
        if old_pos and old_pos in self.hex_entities:
            self.hex_entities[old_pos].discard(entity_id)
            if not self.hex_entities[old_pos]:
                del self.hex_entities[old_pos]

    def get_entities_in_hex(self, q: int, r: int) -> set[str]:
        """Get all entity IDs in a hex cell."""
        return self.hex_entities.get((q, r), set()).copy()

    def get_hex_for_entity(self, entity_id: str) -> Optional[tuple[int, int]]:
        """Get the hex position of an entity."""
        return self.entity_positions.get(entity_id)

    def get_hexes_in_range(self, center_q: int, center_r: int, range_hex: int) -> list[tuple[int, int]]:
        """Get all hex cells within range of a center point."""
        cells = []
        for q in range(center_q - range_hex, center_q + range_hex + 1):
            for r in range(center_r - range_hex, center_r + range_hex + 1):
                if hex_distance(q, r, center_q, center_r) <= range_hex:
                    cells.append((q, r))
        return cells

    def get_entities_in_range(self, center_q: int, center_r: int, range_hex: int) -> dict[str, tuple[int, int]]:
        """Get all entities within range, with their positions."""
        result = {}
        for q in range(center_q - range_hex, center_q + range_hex + 1):
            for r in range(center_r - range_hex, center_r + range_hex + 1):
                if hex_distance(q, r, center_q, center_r) <= range_hex:
                    for eid in self.hex_entities.get((q, r), set()):
                        result[eid] = (q, r)
        return result

    def entities_in_same_hex(self, entity_id: str) -> set[str]:
        """Get other entities in the same hex as the given entity."""
        pos = self.entity_positions.get(entity_id)
        if not pos:
            return set()
        return self.hex_entities.get(pos, set()) - {entity_id}

    def entities_nearby(self, entity_id: str, range_hex: int) -> dict[str, tuple[int, int]]:
        """Get entities nearby (within range hex cells)."""
        pos = self.entity_positions.get(entity_id)
        if not pos:
            return {}
        return self.get_entities_in_range(pos[0], pos[1], range_hex)

    def distance_between(self, entity_a: str, entity_b: str) -> Optional[int]:
        """Get hex distance between two entities. Returns None if either not found."""
        pos_a = self.entity_positions.get(entity_a)
        pos_b = self.entity_positions.get(entity_b)
        if not pos_a or not pos_b:
            return None
        return hex_distance(pos_a[0], pos_a[1], pos_b[0], pos_b[1])

    def distance_nm_between(self, entity_a: str, entity_b: str) -> Optional[float]:
        """Get nautical mile distance between two entities."""
        hex_dist = self.distance_between(entity_a, entity_b)
        if hex_dist is None:
            return None
        return hex_dist * CELL_SIZE_NM

    def debug_summary(self) -> str:
        """Return a summary string for debugging."""
        total_entities = len(self.entity_positions)
        total_hexes = len(self.hex_entities)
        return f"SpatialIndex: {total_entities} entities in {total_hexes} hexes"


# Global spatial index instance
_spatial_index: Optional[SpatialIndex] = None


def get_spatial_index() -> SpatialIndex:
    """Get or create the global spatial index."""
    global _spatial_index
    if _spatial_index is None:
        _spatial_index = SpatialIndex()
    return _spatial_index


def update_spatial_index(state) -> None:
    """Update the spatial index with current entity positions.

    Called each tick after positions are updated.
    """
    idx = get_spatial_index()
    idx.clear()

    # Update US fleet positions
    for tf in state.task_forces:
        for carrier in tf.carriers:
            idx.update_entity(carrier.name, carrier.position.lat, carrier.position.lon)

    # Update enemy positions from actual_enemy
    if state.actual_enemy:
        for i, enemy in enumerate(state.actual_enemy):
            epos = enemy.get("position", {})
            name = enemy.get("name", f"enemy_{i}")
            idx.update_entity(name, epos.get("lat", 0), epos.get("lon", 0))

    # Update scout aircraft positions
    for scout in state.active_scouts:
        if scout.position and scout.status == "in_flight":
            idx.update_entity(scout.id, scout.position.lat, scout.position.lon)

    logger.debug(f"[SPATIAL] {idx.debug_summary()}")
