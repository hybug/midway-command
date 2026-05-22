"""Hex grid renderer for the tactical map.

Renders a hex grid map with ASCII characters, supporting:
- Fog of war (unscouted areas hidden)
- Entity placement (fleets, scouts, islands)
- Search sector visualization
"""
from dataclasses import dataclass
from typing import Optional
from src.render.coordinate import (
    GRID_RADIUS, hex_distance, hex_neighbors,
    world_to_hex, hex_to_world, hex_sector
)


@dataclass
class CellData:
    """Data for a single hex cell."""
    terrain: str = "sea"       # sea, island
    faction: Optional[str] = None  # us, japan
    entity_type: Optional[str] = None  # fleet, scout, island
    scouted: bool = False
    in_search_sector: bool = False
    label: str = ""


class HexGrid:
    """Hex grid map renderer."""

    def __init__(self, radius: int = GRID_RADIUS):
        self.radius = radius
        self.cells: dict[tuple[int, int], CellData] = {}

    def clear(self):
        """Clear all cells."""
        self.cells.clear()

    def get_cell(self, q: int, r: int) -> CellData:
        """Get cell data, creating default if not exists."""
        if (q, r) not in self.cells:
            self.cells[(q, r)] = CellData()
        return self.cells[(q, r)]

    def place_entity(self, q: int, r: int, entity_type: str, faction: str, label: str = ""):
        """Place an entity on the grid."""
        cell = self.get_cell(q, r)
        cell.entity_type = entity_type
        cell.faction = faction
        cell.label = label

    def mark_scouted(self, q: int, r: int):
        """Mark a cell as scouted."""
        cell = self.get_cell(q, r)
        cell.scouted = True

    def mark_sector(self, cells: list[tuple[int, int]]):
        """Mark cells as part of a search sector."""
        for q, r in cells:
            cell = self.get_cell(q, r)
            cell.in_search_sector = True

    def render_ascii(self, center_q: int = 0, center_r: int = 0, radius: int = 10) -> str:
        """Render hex grid as ASCII art.

        Args:
            center_q, center_r: Center of view
            radius: How many cells to show from center

        Returns:
            ASCII string representation
        """
        lines = []

        # Calculate bounds
        min_r = center_r - radius
        max_r = center_r + radius
        min_q = center_q - radius
        max_q = center_q + radius

        for r in range(min_r, max_r + 1):
            # Indent for hex offset
            indent = "  " * abs(r - min_r) if r % 2 != 0 else "  " * abs(r - min_r)
            line = indent

            for q in range(min_q, max_q + 1):
                cell = self.get_cell(q, r)
                symbol = self._get_cell_symbol(cell)
                line += symbol + " "

            lines.append(line)

        return "\n".join(lines)

    def render_for_player(self, state, center_q: int = 0, center_r: int = 0, radius: int = 10) -> str:
        """Render map from player's perspective (with fog of war).

        Only shows:
        - Scouted areas
        - Own fleet position
        - Known enemy positions (from reports)
        - Search sectors
        """
        self.clear()

        # Place own fleet
        for tf in state.task_forces:
            for carrier in tf.carriers:
                q, r = world_to_hex(carrier.position.lat, carrier.position.lon)
                self.place_entity(q, r, "fleet", "us", carrier.name[:3])

        # Place known enemy (from reports, with distortion)
        for enemy in state.known_enemy:
            q, r = world_to_hex(enemy.position.lat, enemy.position.lon)
            self.place_entity(q, r, "fleet", "japan", "敌")

        # Place Midway
        mq, mr = world_to_hex(28.2, -177.4)
        self.place_entity(mq, mr, "island", None, "中途岛")

        # Mark scouted areas (around fleet position)
        fleet_q, fleet_r = world_to_hex(
            state.task_forces[0].carriers[0].position.lat,
            state.task_forces[0].carriers[0].position.lon
        )
        for q in range(fleet_q - 5, fleet_q + 6):
            for r in range(fleet_r - 5, fleet_r + 6):
                if hex_distance(q, r, fleet_q, fleet_r) <= 5:
                    self.mark_scouted(q, r)

        # Mark search sectors
        for scout in state.active_scouts:
            if scout.status == "in_flight":
                sector_cells = hex_sector(
                    fleet_q, fleet_r,
                    scout.search_bearing_min, scout.search_bearing_max,
                    20
                )
                self.mark_sector(sector_cells)

        return self.render_ascii(center_q, center_r, radius)

    def _get_cell_symbol(self, cell: CellData) -> str:
        """Get display symbol for a cell."""
        if cell.entity_type == "fleet":
            if cell.faction == "us":
                return "■"
            elif cell.faction == "japan":
                return "▲"
        elif cell.entity_type == "island":
            return "◆"
        elif cell.entity_type == "scout":
            return "?"

        if cell.in_search_sector:
            return "░"

        if cell.scouted:
            return "~"

        return "·"
