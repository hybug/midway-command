"""Scouting detection engine with full lifecycle.

Phases:
1. PREPARING  (0-15min)  — 甲板准备，不消耗燃油
2. OUTBOUND   (15-60min) — 飞往搜索区域，消耗燃油
3. SEARCHING  (60-120min)— 搜索中，消耗燃油
4. RETURNING  (120-165min)— 返航中，消耗燃油
5. LANDED/DIVERTED/DITCHED/LOST — 着舰/转降/迫降/损失

Fuel model (SBD Dauntless):
- Cruise: 0.8% fuel per nm
- Search: 0.4% fuel per minute (circling)
- Total range: ~250nm at full fuel
"""
import logging
import math
import random
from datetime import timedelta

from src.state import (
    GameState, EnemyKnown, Position, PendingReport,
    ScoutMission, ScoutPhase, AircraftLoss, AircraftStatus, SearchPattern,
)

logger = logging.getLogger("midway.scouting")

# ── SBD Dauntless parameters (normalized to fuel_pct, 200gal tank) ──
PREP_TIME_MIN = 15          # 起飞准备时间
OUTBOUND_TIME_MIN = 45      # 飞往搜索区域时间
SEARCH_TIME_MIN = 60        # 搜索持续时间
RETURN_TIME_MIN = 45        # 返航时间（与去程相同）
FUEL_BURN_PER_NM = 0.6      # 巡航油耗: 1.2 gal/nm ÷ 200 gal = 0.6%/nm
FUEL_BURN_PER_SEARCH_MIN = 0.125  # 搜索油耗: 25 gal/hr ÷ 200 gal = 0.125%/min
FUEL_RETURN_MINIMUM = 15.0  # 返航最低燃油百分比
FUEL_CRITICAL = 5.0         # 燃油危险线
FUEL_LOW = 10.0             # 燃油低线

# ── Loss probabilities ──
WEATHER_LOSS_PROB = 0.05    # 天气损失概率
MIDWAY_LANDING_FAIL_PROB = 0.10  # 中途岛着舰失败概率
ENEMY_CAP_LOSS_PROB = 0.15  # 敌方CAP击落概率（仅在敌军附近）


# ═══════════════════════════════════════════════════════
# Coordinate utilities (same as before)
# ═══════════════════════════════════════════════════════

def calculate_bearing(pos1: tuple, pos2: tuple) -> float:
    lat1, lon1 = math.radians(pos1[0]), math.radians(pos1[1])
    lat2, lon2 = math.radians(pos2[0]), math.radians(pos2[1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def calculate_distance_nm(pos1: tuple, pos2: tuple) -> float:
    lat1, lon1 = math.radians(pos1[0]), math.radians(pos1[1])
    lat2, lon2 = math.radians(pos2[0]), math.radians(pos2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 3440.065 * c


def in_sector(bearing: float, bearing_min: int, bearing_max: int) -> bool:
    if bearing_min <= bearing_max:
        return bearing_min <= bearing <= bearing_max
    else:
        return bearing >= bearing_min or bearing <= bearing_max


# ═══════════════════════════════════════════════════════
# Distortion functions (same as before)
# ═══════════════════════════════════════════════════════

def distort_bearing(bearing: float, max_error: int = 5) -> int:
    return int((bearing + random.randint(-max_error, max_error) + 360) % 360)


def distort_distance(distance: float, max_error_pct: float = 0.1) -> int:
    return int(distance * (1 + random.uniform(-max_error_pct, max_error_pct)))


def distort_count(real_count: int, undercount_prob: float = 0.3) -> int:
    if random.random() < undercount_prob:
        return max(1, real_count - random.randint(1, 2))
    return real_count


def compute_report_delay(distance_nm: float) -> int:
    base = 20
    distance_factor = (distance_nm / 200) * 25
    return int(base + distance_factor + random.randint(-5, 10))


# ═══════════════════════════════════════════════════════
# Phase state machine
# ═══════════════════════════════════════════════════════

def _get_fleet_pos(state: GameState) -> tuple:
    """Get fleet position as (lat, lon)."""
    tf = state.task_forces[0]
    return (tf.carriers[0].position.lat, tf.carriers[0].position.lon)


def _burn_fuel(scout: ScoutMission, amount: float, state: GameState):
    """Burn fuel on ScoutMission and linked Aircraft objects."""
    scout.fuel_pct = max(0.0, scout.fuel_pct - amount)
    # Also burn fuel on linked Aircraft
    for tf in state.task_forces:
        for carrier in tf.carriers:
            for aircraft in carrier.aircraft:
                if aircraft.id in scout.aircraft_ids:
                    aircraft.fuel_pct = max(0.0, aircraft.fuel_pct - amount)


def _advance_phase(scout: ScoutMission, new_phase: ScoutPhase, state: GameState):
    """Transition to a new phase."""
    scout.phase = new_phase
    scout.phase_started_at = state.clock.game_time

    # Update position based on phase
    fleet_pos = _get_fleet_pos(state)
    if new_phase == ScoutPhase.OUTBOUND:
        # Start at fleet position
        scout.position = Position(lat=fleet_pos[0], lon=fleet_pos[1])
    elif new_phase == ScoutPhase.SEARCHING:
        # Move to search area center (bearing + distance from fleet)
        mid_bearing = (scout.search_bearing_min + scout.search_bearing_max) / 2
        search_dist = min(scout.search_distance_nm, 180)  # Cap at 180nm
        scout.position = _bearing_distance_to_position(fleet_pos, mid_bearing, search_dist)
    elif new_phase == ScoutPhase.RETURNING:
        # Start return from current search position
        pass  # position stays at search area, will move toward fleet each tick

    logger.info(f"[SCOUT] {scout.id} → {new_phase.value} (fuel: {scout.fuel_pct:.1f}%)")


def _update_aircraft_on_landing(state: GameState, scout: ScoutMission, new_status: AircraftStatus):
    """Update Aircraft status when scout mission ends."""
    for tf in state.task_forces:
        for carrier in tf.carriers:
            for aircraft in carrier.aircraft:
                if aircraft.id in scout.aircraft_ids:
                    aircraft.status = new_status
                    aircraft.assigned_mission = None


def _check_enemy_proximity(state: GameState, scout: ScoutMission) -> bool:
    """Check if scout is near hidden enemy fleet."""
    hidden = state._hidden_actual_enemy or []
    fleet_pos = _get_fleet_pos(state)
    for enemy in hidden:
        epos = enemy.get("position", {})
        enemy_pos = (epos.get("lat", 0), epos.get("lon", 0))
        dist = calculate_distance_nm(fleet_pos, enemy_pos)
        # If scout searched in the right sector and enemy is within range
        bearing = calculate_bearing(fleet_pos, enemy_pos)
        if in_sector(bearing, scout.search_bearing_min, scout.search_bearing_max):
            if dist <= scout.search_distance_nm:
                return True
    return False


def _process_returning(scout: ScoutMission, state: GameState) -> list[str]:
    """Process the return phase of a scout mission."""
    notifications = []
    elapsed = (state.clock.game_time - scout.phase_started_at).total_seconds() / 60

    # Burn return fuel
    _burn_fuel(scout, FUEL_BURN_PER_NM * 2, state)  # ~2nm per 15min tick at cruise

    # Move position toward fleet (2nm per tick)
    if scout.position:
        fleet_pos = _get_fleet_pos(state)
        current = (scout.position.lat, scout.position.lon)
        dist_to_fleet = calculate_distance_nm(current, fleet_pos)
        if dist_to_fleet > 2:
            # Move 2nm toward fleet
            bearing_to_fleet = calculate_bearing(current, fleet_pos)
            new_pos = _bearing_distance_to_position(current, bearing_to_fleet, 2.0)
            scout.position.lat = new_pos.lat
            scout.position.lon = new_pos.lon
        else:
            # Close enough — snap to fleet
            scout.position.lat = fleet_pos[0]
            scout.position.lon = fleet_pos[1]

    # Check fuel status
    if scout.fuel_pct <= FUEL_CRITICAL:
        # Aircraft lost
        lost = min(2, scout.aircraft_count - scout.aircraft_lost)
        if lost > 0:
            scout.aircraft_lost += lost
            scout.loss_reasons.append(f"燃油耗尽损失 {lost} 架")
            state.aircraft_losses.extend([
                AircraftLoss(
                    scout_id=scout.id,
                    aircraft_number=scout.aircraft_lost - lost + i + 1,
                    reason="fuel_exhausted",
                    time=state.clock.game_time,
                )
                for i in range(lost)
            ])
            notifications.append(f"⚠️ {scout.id}: {lost} 架飞机因燃油耗尽坠海！（剩余 {scout.aircraft_count - scout.aircraft_lost} 架）")
            logger.warning(f"[SCOUT] {scout.id} LOST {lost} aircraft — fuel exhausted")

        # If all lost
        if scout.aircraft_lost >= scout.aircraft_count:
            _advance_phase(scout, ScoutPhase.LOST, state)
            scout.status = "completed"
            notifications.append(f"❌ {scout.id}: 全部飞机损失！任务终止。")
            return notifications

    elif scout.fuel_pct <= FUEL_LOW:
        # 50% chance of losing an aircraft
        if random.random() < 0.5:
            lost = 1
            scout.aircraft_lost += lost
            scout.loss_reasons.append(f"低燃油损失 {lost} 架")
            state.aircraft_losses.append(AircraftLoss(
                scout_id=scout.id,
                aircraft_number=scout.aircraft_lost,
                reason="fuel_exhausted",
                time=state.clock.game_time,
            ))
            notifications.append(f"⚠️ {scout.id}: 1 架飞机因燃油不足坠海！（剩余 {scout.aircraft_count - scout.aircraft_lost} 架）")

    # Check if return phase complete
    if elapsed >= RETURN_TIME_MIN:
        # Check weather loss (5% per aircraft remaining)
        remaining = scout.aircraft_count - scout.aircraft_lost
        weather_lost = sum(1 for _ in range(remaining) if random.random() < WEATHER_LOSS_PROB)
        if weather_lost > 0:
            scout.aircraft_lost += weather_lost
            scout.loss_reasons.append(f"天气损失 {weather_lost} 架")
            state.aircraft_losses.extend([
                AircraftLoss(
                    scout_id=scout.id,
                    aircraft_number=scout.aircraft_lost - weather_lost + i + 1,
                    reason="weather",
                    time=state.clock.game_time,
                )
                for i in range(weather_lost)
            ])
            notifications.append(f"🌧️ {scout.id}: {weather_lost} 架飞机因恶劣天气损失")

        # Final status
        remaining = scout.aircraft_count - scout.aircraft_lost
        if remaining <= 0:
            _advance_phase(scout, ScoutPhase.LOST, state)
            scout.status = "completed"
            # Mark all aircraft as lost
            _update_aircraft_on_landing(state, scout, AircraftStatus.MAINTENANCE)
            notifications.append(f"❌ {scout.id}: 全部飞机损失！任务终止。")
        else:
            _advance_phase(scout, ScoutPhase.LANDED, state)
            scout.status = "completed"
            _update_aircraft_on_landing(state, scout, AircraftStatus.LANDING)
            notifications.append(
                f"✅ {scout.id}: {remaining}/{scout.aircraft_count} 架飞机安全着舰"
                + (f"（损失 {scout.aircraft_lost} 架）" if scout.aircraft_lost > 0 else "")
            )
            logger.info(f"[SCOUT] {scout.id} LANDED — {remaining}/{scout.aircraft_count} aircraft")

    return notifications


def _process_searching(scout: ScoutMission, state: GameState) -> list[str]:
    """Process the search phase — detect enemies and check fuel."""
    notifications = []
    elapsed_search = (state.clock.game_time - scout.phase_started_at).total_seconds() / 60

    # Burn search fuel
    _burn_fuel(scout, FUEL_BURN_PER_SEARCH_MIN * 15, state)  # 15 min per tick

    # Detection check (at end of search)
    if elapsed_search >= SEARCH_TIME_MIN:
        hidden = state._hidden_actual_enemy or []
        fleet_pos = _get_fleet_pos(state)
        detected = False

        for enemy in hidden:
            epos = enemy.get("position", {})
            enemy_pos = (epos.get("lat", 0), epos.get("lon", 0))
            bearing = calculate_bearing(fleet_pos, enemy_pos)
            distance = calculate_distance_nm(fleet_pos, enemy_pos)

            if not in_sector(bearing, scout.search_bearing_min, scout.search_bearing_max):
                continue
            if distance > scout.search_distance_nm:
                continue

            # Pattern-dependent detection probability
            if scout.search_pattern == SearchPattern.SECTOR:
                base_prob = 0.8
                distance_decay = 0.4
            elif scout.search_pattern == SearchPattern.PARALLEL:
                base_prob = 0.6
                distance_decay = 0.3
            elif scout.search_pattern == SearchPattern.GRID:
                base_prob = 0.9
                distance_decay = 0.2
            else:
                base_prob = 0.8
                distance_decay = 0.4

            distance_ratio = distance / scout.search_distance_nm
            prob = base_prob * (1.0 - distance_ratio * distance_decay)

            if random.random() < prob:
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
                notifications.append(
                    f"📡 {scout.id} 发现敌舰！报告传输中，预计 {delay} 分钟后到达"
                )
                logger.info(f"[SCOUT] {scout.id} DETECTED at bearing {int(bearing)}°, {int(distance)}nm")
                detected = True
                break

        if not detected:
            state.incoming_messages.append(
                f"[{state.clock.game_time.strftime('%H:%M')}] {scout.id}: 搜索扇面内未发现敌舰"
            )
            notifications.append(f"📡 {scout.id}: 扇面内未发现敌舰")

        # Transition to return
        scout.return_heading = (scout.heading + 180) % 360  # Reverse heading
        scout.return_eta_minutes = RETURN_TIME_MIN
        _advance_phase(scout, ScoutPhase.RETURNING, state)

    return notifications


def _process_outbound(scout: ScoutMission, state: GameState) -> list[str]:
    """Process the outbound flight phase."""
    notifications = []
    elapsed = (state.clock.game_time - scout.phase_started_at).total_seconds() / 60

    # Burn outbound fuel
    _burn_fuel(scout, FUEL_BURN_PER_NM * 2, state)  # ~2nm per 15min tick

    if elapsed >= OUTBOUND_TIME_MIN:
        _advance_phase(scout, ScoutPhase.SEARCHING, state)

    return notifications


def _process_preparing(scout: ScoutMission, state: GameState) -> list[str]:
    """Process the preparation phase."""
    elapsed = (state.clock.game_time - scout.phase_started_at).total_seconds() / 60
    if elapsed >= PREP_TIME_MIN:
        _advance_phase(scout, ScoutPhase.OUTBOUND, state)
    return []


# ═══════════════════════════════════════════════════════
# Main check function (called by EventScheduler)
# ═══════════════════════════════════════════════════════

def check_scout_results(state: GameState) -> list[str]:
    """Check all active scout missions through the phase state machine.

    Each call processes the current phase. On the next tick, the next phase
    will be processed. This ensures time passes between phase transitions.
    """
    notifications = []

    for scout in state.active_scouts:
        if scout.status != "in_flight":
            continue
        if scout.phase in (ScoutPhase.LANDED, ScoutPhase.LOST, ScoutPhase.DITCHED, ScoutPhase.DIVERTED):
            continue

        if scout.phase == ScoutPhase.PREPARING:
            notifications.extend(_process_preparing(scout, state))
        elif scout.phase == ScoutPhase.OUTBOUND:
            notifications.extend(_process_outbound(scout, state))
        elif scout.phase == ScoutPhase.SEARCHING:
            notifications.extend(_process_searching(scout, state))
        elif scout.phase == ScoutPhase.RETURNING:
            notifications.extend(_process_returning(scout, state))

    return notifications


# ═══════════════════════════════════════════════════════
# Pending reports (unchanged logic)
# ═══════════════════════════════════════════════════════

def _bearing_distance_to_position(origin: tuple, bearing_deg: float, distance_nm: float) -> Position:
    """Convert bearing + distance from origin to a Position (lat/lon)."""
    lat1 = math.radians(origin[0])
    lon1 = math.radians(origin[1])
    bearing = math.radians(bearing_deg)
    R = 3440.065  # Earth radius in nm

    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance_nm / R) +
        math.cos(lat1) * math.sin(distance_nm / R) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(distance_nm / R) * math.cos(lat1),
        math.cos(distance_nm / R) - math.sin(lat1) * math.sin(lat2)
    )
    return Position(lat=math.degrees(lat2), lon=math.degrees(lon2))


def check_pending_reports(state: GameState) -> list[str]:
    """Check if any pending reports have arrived. Convert to EnemyKnown."""
    notifications = []
    arrived = []

    for report in state.pending_reports:
        if state.clock.game_time >= report.arrive_at:
            # Compute actual position from bearing/distance
            tf = state.task_forces[0]
            fleet_pos = (tf.carriers[0].position.lat, tf.carriers[0].position.lon)
            enemy_pos = _bearing_distance_to_position(
                fleet_pos, report.reported_bearing, report.reported_distance_nm
            )

            enemy = EnemyKnown(
                position=enemy_pos,
                description=(
                    f"SBD {report.scout_id}: 敌航母约 {report.reported_carrier_count} 艘"
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
            logger.info(f"[REPORT] {report.scout_id} arrived: {enemy.description}")

    for r in arrived:
        state.pending_reports.remove(r)

    return notifications
