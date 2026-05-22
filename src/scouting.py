"""Scouting detection engine with delay and distortion.

Flow:
1. Scout reaches search area → probability check
2. If detected → create PendingReport with delay (30-60 min) and distortion
3. On each time tick → check if any PendingReport has arrived
4. Arrived reports → convert to EnemyKnown (visible to player)
"""
import logging
import math
import random
from datetime import timedelta

from src.state import GameState, EnemyKnown, Position, PendingReport

logger = logging.getLogger("midway.scouting")


def calculate_bearing(pos1: tuple, pos2: tuple) -> float:
    """Calculate bearing from pos1 to pos2 in degrees."""
    lat1, lon1 = math.radians(pos1[0]), math.radians(pos1[1])
    lat2, lon2 = math.radians(pos2[0]), math.radians(pos2[1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def calculate_distance_nm(pos1: tuple, pos2: tuple) -> float:
    """Calculate distance in nautical miles between two positions."""
    lat1, lon1 = math.radians(pos1[0]), math.radians(pos1[1])
    lat2, lon2 = math.radians(pos2[0]), math.radians(pos2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    nm = 3440.065 * c  # Earth radius in nautical miles
    return nm


def in_sector(bearing: float, bearing_min: int, bearing_max: int) -> bool:
    """Check if a bearing falls within a sector (handles wrap-around)."""
    if bearing_min <= bearing_max:
        return bearing_min <= bearing <= bearing_max
    else:  # wraps around 360
        return bearing >= bearing_min or bearing <= bearing_max


def add_position_noise(pos: dict, noise_nm: float = 20) -> dict:
    """Add random noise to a position (simulates reconnaissance error)."""
    lat_noise = random.uniform(-noise_nm / 60, noise_nm / 60)
    lon_noise = random.uniform(-noise_nm / 60, noise_nm / 60)
    return {
        "lat": pos.get("lat", 0) + lat_noise,
        "lon": pos.get("lon", 0) + lon_noise,
    }


def distort_bearing(bearing: float, max_error: int = 5) -> int:
    """Add ±max_error degrees of error to a bearing."""
    error = random.randint(-max_error, max_error)
    return int((bearing + error + 360) % 360)


def distort_distance(distance: float, max_error_pct: float = 0.1) -> int:
    """Add ±max_error_pct percentage error to a distance."""
    error = random.uniform(-max_error_pct, max_error_pct)
    return int(distance * (1 + error))


def distort_count(real_count: int, undercount_prob: float = 0.3) -> int:
    """Possibly undercount carrier count (cloud cover, bad angle)."""
    if random.random() < undercount_prob:
        return max(1, real_count - random.randint(1, 2))
    return real_count


def compute_report_delay(distance_nm: float) -> int:
    """Compute report delay in minutes based on distance.

    Closer targets → faster reports (20-35 min).
    Distant targets → slower reports (35-55 min).
    """
    base = 20
    distance_factor = (distance_nm / 200) * 25  # 0-25 extra minutes
    jitter = random.randint(-5, 10)
    return int(base + distance_factor + jitter)


def check_scout_results(state: GameState) -> list[str]:
    """Check all active scout missions. If detection succeeds, create a PendingReport with delay."""
    notifications = []
    hidden = state._hidden_actual_enemy or []

    for scout in state.active_scouts:
        if scout.status != "in_flight":
            continue

        # Check if ETA has been reached
        elapsed = (state.clock.game_time - scout.launched_at).total_seconds() / 60
        if elapsed < scout.eta_minutes:
            continue

        # Scout has reached search area
        scout.status = "completed"
        logger.info(f"[SCOUT] {scout.id} reached search area ({scout.direction})")

        # Get fleet position
        tf = state.task_forces[0]
        fleet_pos = (tf.carriers[0].position.lat, tf.carriers[0].position.lon)

        # Check if any hidden enemy is in the search sector
        detected = False
        for enemy in hidden:
            enemy_pos_dict = enemy.get("position", {})
            enemy_pos = (enemy_pos_dict.get("lat", 0), enemy_pos_dict.get("lon", 0))

            bearing = calculate_bearing(fleet_pos, enemy_pos)
            distance = calculate_distance_nm(fleet_pos, enemy_pos)

            if not in_sector(bearing, scout.search_bearing_min, scout.search_bearing_max):
                continue
            if distance > scout.search_distance_nm:
                continue

            # Probability detection
            base_prob = 0.8  # 基础概率（从0.7提高）
            distance_ratio = distance / scout.search_distance_nm
            distance_factor = 1.0 - (distance_ratio * 0.4)  # 距离衰减（从0.6降低）
            prob = base_prob * distance_factor

            if random.random() < prob:
                # Detected! Create delayed report with distortion
                real_count = len(enemy.get("carriers", []))
                delay = compute_report_delay(distance)

                report = PendingReport(
                    scout_id=scout.id,
                    detected_at=state.clock.game_time,
                    arrive_at=state.clock.game_time + timedelta(minutes=delay),
                    real_bearing=bearing,
                    real_distance_nm=distance,
                    real_carrier_count=real_count,
                    reported_bearing=distort_bearing(bearing),
                    reported_distance_nm=distort_distance(distance),
                    reported_carrier_count=distort_count(real_count),
                    confidence="medium" if distance > 100 else "high",
                )
                state.pending_reports.append(report)
                notifications.append(f"📡 {scout.id} 发现敌舰！报告正在传输中，预计 {delay} 分钟后到达")
                logger.info(f"[SCOUT] {scout.id} DETECTED enemy at bearing {int(bearing)}°, distance {int(distance)}nm, delay={delay}min")
                detected = True
                break

        if not detected:
            msg = f"[{state.clock.game_time.strftime('%H:%M')}] {scout.id}: 搜索扇面内未发现敌舰"
            state.incoming_messages.append(msg)
            notifications.append(f"📡 {scout.id} 报告：扇面内未发现敌舰")
            logger.info(f"[SCOUT] {scout.id} found nothing in sector")

    return notifications


def check_pending_reports(state: GameState) -> list[str]:
    """Check if any pending reports have arrived. Convert to EnemyKnown."""
    notifications = []
    arrived = []

    for report in state.pending_reports:
        if state.clock.game_time >= report.arrive_at:
            # Report has arrived — convert to EnemyKnown
            enemy = EnemyKnown(
                position=Position(lat=0, lon=0),  # Position not used for display
                description=(
                    f"PBY {report.scout_id}: 敌航母约 {report.reported_carrier_count} 艘"
                    f" - 方位 {report.reported_bearing}°"
                    f" - 距离约 {report.reported_distance_nm} 海里"
                ),
                confidence=report.confidence,
                source=report.scout_id,
                reported_at=report.arrive_at,
            )
            state.known_enemy.append(enemy)
            msg = f"[{report.arrive_at.strftime('%H:%M')}] {enemy.description}"
            state.incoming_messages.append(msg)
            notifications.append(f"📡 {report.scout_id} 报告到达：{enemy.description}")
            arrived.append(report)
            logger.info(f"[REPORT] {report.scout_id} report arrived: bearing {report.reported_bearing}°, distance {report.reported_distance_nm}nm, carriers {report.reported_carrier_count}")

    # Remove arrived reports
    for r in arrived:
        state.pending_reports.remove(r)

    return notifications
