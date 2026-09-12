"""战区包校验（CHART_SYSTEM.md §三/§七）。"""
from pathlib import Path
import json
from tools.validate_theater import validate_theater

BASE = Path(__file__).resolve().parent.parent
PACK = BASE / "theaters" / "midway"

def test_midway_pack_complete():
    missing = [f for f in ["theater.json", "geography.geojson", "scenario.json", "README.md"]
               if not (PACK / f).exists()]
    assert missing == [], f"战区包缺文件: {missing}"

def test_midway_pack_passes_validator():
    result = validate_theater(PACK)
    assert result["ok"], result["errors"]

def test_theater_schema_core_fields():
    pack = json.loads((PACK / "theater.json").read_text())
    assert pack["id"] == "midway" and pack["view"]["view_nm"] == 45
    assert len(pack["bases"]) >= 1 and len(pack["sectors"]) >= 1
    gr = pack["graticule"]
    assert gr["minor_step"] == 0.25 and gr["major_step"] == 1.0

def test_scenario_fleet_positions_match_mockup():
    sc = json.loads((PACK / "scenario.json").read_text())
    pos = {u["callsign"]: (u["lat"], u["lon"]) for u in sc["task_forces"]}
    assert 35 <= _nm_west_of_atoll(*pos["ENT"]) <= 55   # ENT 环礁西 35-55nm（成品图量取）
    assert 20 <= _nm_west_of_atoll(*pos["HOR"]) <= 40   # HOR 环礁西 20-40nm

def _nm_west_of_atoll(lat: float, lon: float) -> float:
    """环礁心 (28.2, -177.4) 到该点的距离 nm（成品图量取基准）；经度须在环礁西侧。"""
    from src.scouting import calculate_distance_nm
    assert lon < -177.4, f"舰队应在环礁西侧: lon={lon}"
    return calculate_distance_nm((28.2, -177.4), (lat, lon))
