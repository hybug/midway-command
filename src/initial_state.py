"""Build the initial game state for June 4, 1942, 04:00.

Force structure from docs/HISTORICAL_NOTES.md; fleet opening positions are
scenario-driven (theaters/midway/scenario.json — M.4 布兵唯一化).
Times are Zone +12 (Midway time zone).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

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

# 战区剧本（布兵唯一来源）：舰队初始位/航向/航速从 scenario.json 读取，
# 与前端战区包同源（M.4 实体层投影唯一化后 ENT/HOR 真实位直接落图面构图）。
_SCENARIO_JSON = Path(__file__).resolve().parent.parent / "theaters" / "midway" / "scenario.json"

# scenario.json air_groups.type → 状态模型枚举（O.3 通用剧本化构建）
_AIR_GROUP_TYPE = {
    "fighter": AirGroupType.FIGHTER,
    "dive_bomber": AirGroupType.DIVE_BOMBER,
    "dive": AirGroupType.DIVE_BOMBER,
    "torpedo": AirGroupType.TORPEDO,
}
_AIRCRAFT_TYPE = {
    "fighter": AircraftType.VF,
    "dive_bomber": AircraftType.SBD,
    "dive": AircraftType.SBD,
    "torpedo": AircraftType.TBD,
}
_ORDNANCE = {"dive_bomber": "500lb_bomb", "dive": "500lb_bomb", "torpedo": "torpedo"}


def _scenario_deployments() -> dict:
    """scenario.json 布兵表：callsign（ENT/HOR）→ task force 条目。"""
    scenario = json.loads(_SCENARIO_JSON.read_text(encoding="utf-8"))
    return {tf["callsign"]: tf for tf in scenario["task_forces"]}


def build_initial_state(scenario_path: Path | None = None) -> GameState:
    """按战区包 scenario 构建 GameState（O.3 参数化）。

    - 缺省 / midway 包 → 既有历史开局（key pilots 等史实细节，逐字段不变）；
    - 其余包 → 通用剧本化构建（clock_start/布兵/敌舰队全部走 scenario 数据）。
    """
    path = Path(scenario_path) if scenario_path else _SCENARIO_JSON
    if path.resolve() == _SCENARIO_JSON:
        return _build_midway_state()
    scenario = json.loads(path.read_text(encoding="utf-8"))
    return _build_state_from_scenario(scenario)


def _build_state_from_scenario(scenario: dict) -> GameState:
    """通用剧本化初始态（O.3 珊瑚海等多岛战区包）。

    布兵唯一来源 scenario.json：clock_start → GameClock；task_forces →
    本方舰队（航母位=编队位，机队按 air_groups 折算）；enemy_fleet →
    结构化敌舰队（entities 层）+ actual_enemy 条目（god-view，不下发玩家）。
    known_enemy 初始为空——敌情经侦察产生（可视性分层核心机制）。
    """
    clock = GameClock(
        game_time=datetime.fromisoformat(scenario["clock_start"].replace("Z", "+00:00")),
        tick_minutes=15,
    )

    task_forces: list[TaskForce] = []
    for tf in scenario["task_forces"]:
        carriers = []
        for c in tf["carriers"]:
            aircraft = [
                Aircraft(
                    id=f"{_AIRCRAFT_TYPE[ag['type']].value}-{ag['squadron']}-{i:02d}",
                    type=_AIRCRAFT_TYPE[ag["type"]],
                    squadron=ag["squadron"],
                    carrier=c["name"],
                    status=AircraftStatus.READY,
                    fuel_pct=100.0,
                    ammo_pct=100.0,
                    ordnance=_ORDNANCE.get(ag["type"], "none"),
                )
                for ag in c.get("air_groups", [])
                for i in range(1, ag["count"] + 1)
            ]
            carriers.append(Carrier(
                name=c["name"],
                position=Position(lat=tf["lat"], lon=tf["lon"]),
                course=tf["course"],
                speed=tf["speed"],
                cap_strength=c.get("cap_strength", 12),
                damage_level=c.get("damage_level", 0),
                air_groups=[
                    AirGroup(
                        type=_AIR_GROUP_TYPE[ag["type"]],
                        count=ag["count"],
                        squadron_name=ag["squadron"],
                    )
                    for ag in c.get("air_groups", [])
                ],
                aircraft=aircraft,
            ))
        task_forces.append(TaskForce(
            name=tf["name"],
            carriers=carriers,
            course=tf["course"],
            speed=tf["speed"],
        ))

    state = GameState(
        clock=clock,
        task_forces=task_forces,
        known_enemy=[],
        incoming_messages=[],
        turn_type=TurnType.NORMAL,
        action_points=3,
        max_action_points=3,
    )

    # 敌舰队（结构化实体）：航母同位编队（scenario 只给编队位），随队移动同步
    ef = scenario["enemy_fleet"]
    enemy_carriers = [
        EntityCarrier(
            id=name.lower(),
            name=name,
            position=EntityPosition(lat=ef["lat"], lon=ef["lon"]),
            course=ef["course"],
            speed=ef["speed"],
            faction="japan",
            cap_strength=12,
            air_groups=[],
        )
        for name in ef["carriers"]
    ]
    state.enemy_fleet = EntityTaskForce(
        name=ef["name"],
        faction="japan",
        carriers=enemy_carriers,
        course=ef["course"],
        speed=ef["speed"],
    )
    state.actual_enemy = [
        {
            "name": ef["name"],
            "carriers": list(ef["carriers"]),
            "position": {"lat": ef["lat"], "lon": ef["lon"]},
            "status": "underway",
        }
    ]
    return state


def _build_midway_state() -> GameState:
    """中途岛历史开局（04:00, June 4, 1942）——M.4 以来逐字段保持不变。"""

    # TF16 opening deployment — scenario-driven（M.4：initial 位与 scenario.json 同源，
    # ENT 环礁西 45nm / HOR 西 28nm；两编队同向 270°、25kn。其余兵力结构不变）
    deploy = _scenario_deployments()
    tf16_course = deploy["ENT"]["course"]
    tf16_speed = deploy["ENT"]["speed"]

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
        position=Position(lat=deploy["ENT"]["lat"], lon=deploy["ENT"]["lon"]),
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
        position=Position(lat=deploy["HOR"]["lat"], lon=deploy["HOR"]["lon"]),
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
        course=tf16_course,
        speed=tf16_speed,
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
