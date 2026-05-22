"""Coordinate system: geographic ↔ hex grid conversion.

Hex grid uses axial coordinates (q, r).
Reference point: Midway Island (28.2°N, 177.4°W) → hex (0, 0).

Grid layout:
- Cell size: 10 nautical miles
- Radius: 20 cells (covers 200 nm range)
- Total cells: ~1,200
"""
import math

# Reference point: Midway Island
REF_LAT = 28.2
REF_LON = -177.4

# Grid parameters
CELL_SIZE_NM = 10  # nautical miles per hex cell
GRID_RADIUS = 20   # cells from center to edge


def world_to_hex(lat: float, lon: float) -> tuple[int, int]:
    """Convert geographic coordinates to hex grid coordinates.

    Args:
        lat: Latitude (positive = North)
        lon: Longitude (negative = West)

    Returns:
        (q, r) hex coordinates
    """
    # Convert to nautical miles from reference point
    # 1 degree latitude ≈ 60 nm
    # 1 degree longitude ≈ 60 * cos(lat) nm
    dlat = lat - REF_LAT
    dlon = lon - REF_LON

    nm_north = dlat * 60
    nm_east = dlon * 60 * math.cos(math.radians(REF_LAT))

    # Convert to hex coordinates
    # Hex grid: q = east, r = south (axial coordinates)
    q = nm_east / CELL_SIZE_NM
    r = nm_north / CELL_SIZE_NM

    # Round to nearest hex cell
    return _round_hex(q, r)


def hex_to_world(q: int, r: int) -> tuple[float, float]:
    """Convert hex grid coordinates to geographic coordinates (cell center).

    Args:
        q: Hex q coordinate
        r: Hex r coordinate

    Returns:
        (lat, lon) geographic coordinates
    """
    # Convert hex to nautical miles
    nm_east = q * CELL_SIZE_NM
    nm_north = r * CELL_SIZE_NM

    # Convert to geographic coordinates
    dlat = nm_north / 60
    dlon = nm_east / (60 * math.cos(math.radians(REF_LAT)))

    return REF_LAT + dlat, REF_LON + dlon


def hex_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    """Calculate distance between two hex cells in hex units.

    Uses cube coordinate distance formula.
    """
    # Convert axial to cube
    s1 = -q1 - r1
    s2 = -q2 - r2
    return max(abs(q1 - q2), abs(r1 - r2), abs(s1 - s2))


def hex_distance_nm(q1: int, r1: int, q2: int, r2: int) -> float:
    """Calculate distance between two hex cells in nautical miles."""
    return hex_distance(q1, r1, q2, r2) * CELL_SIZE_NM


def course_to_hex_direction(course: int) -> tuple[int, int]:
    """Convert ship course (0-360°) to hex direction vector.

    0° = North, 90° = East, 180° = South, 270° = West

    Returns:
        (dq, dr) direction vector
    """
    # Normalize course to 0-360
    course = course % 360

    # Convert to hex direction (6 directions, each 60°)
    # Hex directions: E, NE, NW, W, SW, SE
    # Course: N=0, E=90, S=180, W=270
    # Mapping: N→NW, NE→NE, E→E, SE→SE, S→SW, SW→SW, W→W, NW→NW
    if course < 30 or course >= 330:
        return (0, -1)   # North → NW in hex
    elif course < 90:
        return (1, -1)   # NE
    elif course < 150:
        return (1, 0)    # E
    elif course < 210:
        return (0, 1)    # SE → SW in hex
    elif course < 270:
        return (-1, 1)   # SW
    else:
        return (-1, 0)   # W


def hex_neighbors(q: int, r: int) -> list[tuple[int, int]]:
    """Get all 6 neighboring hex cells."""
    return [
        (q + 1, r),     # E
        (q + 1, r - 1), # NE
        (q, r - 1),     # NW
        (q - 1, r),     # W
        (q - 1, r + 1), # SW
        (q, r + 1),     # SE
    ]


def _round_hex(q: float, r: float) -> tuple[int, int]:
    """Round fractional hex coordinates to nearest hex cell."""
    # Convert to cube coordinates
    s = -q - r
    rq = round(q)
    rr = round(r)
    rs = round(s)

    # Fix rounding errors (q + r + s must = 0)
    q_diff = abs(rq - q)
    r_diff = abs(rr - r)
    s_diff = abs(rs - s)

    if q_diff > r_diff and q_diff > s_diff:
        rq = -rr - rs
    elif r_diff > s_diff:
        rr = -rq - rs

    return int(rq), int(rr)


def hex_in_range(q: int, r: int, center_q: int, center_r: int, radius: int) -> bool:
    """Check if a hex cell is within range of a center point."""
    return hex_distance(q, r, center_q, center_r) <= radius


def hex_sector(center_q: int, center_r: int, bearing_min: int, bearing_max: int, radius: int) -> list[tuple[int, int]]:
    """Get hex cells within a sector (bearing range) from center.

    Args:
        center_q, center_r: Center hex coordinates
        bearing_min, bearing_max: Bearing range in degrees
        radius: Max distance in hex units

    Returns:
        List of (q, r) hex coordinates in sector
    """
    cells = []
    for q in range(center_q - radius, center_q + radius + 1):
        for r in range(center_r - radius, center_r + radius + 1):
            if hex_distance(q, r, center_q, center_r) > radius:
                continue

            # Check bearing
            bearing = hex_bearing(center_q, center_r, q, r)
            if bearing_in_sector(bearing, bearing_min, bearing_max):
                cells.append((q, r))

    return cells


def hex_bearing(q1: int, r1: int, q2: int, r2: int) -> float:
    """Calculate bearing from hex (q1,r1) to hex (q2,r2) in degrees.

    Returns:
        Bearing in degrees (0=N, 90=E, 180=S, 270=W)
    """
    # Convert to world coordinates
    lat1, lon1 = hex_to_world(q1, r1)
    lat2, lon2 = hex_to_world(q2, r2)

    # Calculate bearing
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlon_r = math.radians(lon2 - lon1)

    y = math.sin(dlon_r) * math.cos(lat2_r)
    x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon_r)

    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360


def bearing_in_sector(bearing: float, sector_min: int, sector_max: int) -> bool:
    """Check if a bearing falls within a sector (handles wrap-around)."""
    if sector_min <= sector_max:
        return sector_min <= bearing <= sector_max
    else:  # wraps around 360
        return bearing >= sector_min or bearing <= sector_max
