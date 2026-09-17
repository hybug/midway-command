"""S2.1 骰子与可复现随机性测试（Phase S2.1，红灯先行）。

验收（s2-intelligence-system-plan.md Phase S2.1）：
- 同一局面同一种子可重放相同结果
- 每次检定都有理由、输入、骰值和效果记录（CheckRecord）
- 现有测试保持通过（迁移不破坏旧失真函数语义）
- 侦察检定使用实际执行单位能力；"grid" 搜索模式映射修复
"""
import random
from datetime import datetime, timedelta, timezone

import pytest

from src.state import (
    GameState, GameClock, TaskForce, Carrier, Position, Aircraft,
    AircraftType, AircraftStatus,
)
from src.intel.contracts import CheckType
from src.intel.rng import CheckRecord, RNGService
from src.dice import roll_check
from src.npc_config import UNIT_REGISTRY


# ── 公共构造 ──

def make_state(rng_seed=20260604):
    carrier = Carrier(
        name="USS Enterprise (CV-6)",
        position=Position(lat=32.0, lon=-175.0),
    )
    tf = TaskForce(name="TF16", carriers=[carrier], course=240, speed=25)
    state = GameState(
        clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)),
        task_forces=[tf],
        rng_seed=rng_seed,
    )
    return state


# ── CheckRecord 模型（计划 §6.10 字段）──

def test_check_record_schema_fields():
    rec = CheckRecord(
        check_id="chk_000001",
        check_type="detection_check",
        actor_id="SBD 侦察中队",
        game_time=datetime(1942, 6, 4, 5, 0, tzinfo=timezone.utc),
        random_seed="20260604:0",
        raw_roll=77,
        modifiers={"npc": "SBD 侦察中队 +12"},
        final_roll=72,
        degree="success",
        effects={"delay_min": 31},
        context={"reason": "侦察检定"},
    )
    assert rec.check_id == "chk_000001"
    assert rec.random_seed == "20260604:0"
    assert rec.degree == "success"
    assert rec.effects["delay_min"] == 31


def test_gamestate_has_rng_fields():
    state = make_state()
    assert state.rng_seed == 20260604
    assert state.check_records == []


# ── RNGService：可复现抽取 ──

def test_same_seed_replays_same_sequence():
    def run():
        state = make_state()
        rng = RNGService(state)
        vals = [
            rng.randint(CheckType.COMMUNICATION_CHECK, "test", 1, 60, reason="t1"),
            rng.chance(CheckType.DETECTION_CHECK, "test", 0.5, reason="t2"),
            rng.randint(CheckType.COMMUNICATION_CHECK, "test", -5, 10, reason="t3"),
        ]
        return vals, [r.model_dump() for r in state.check_records]
    v1, r1 = run()
    v2, r2 = run()
    assert v1 == v2
    assert r1 == r2


def test_different_seed_differs_eventually():
    vals = set()
    for seed in range(30):
        state = make_state(rng_seed=seed)
        rng = RNGService(state)
        vals.add(rng.randint(CheckType.COMMUNICATION_CHECK, "t", 1, 1_000_000, reason="x"))
    assert len(vals) > 10, "不同种子应产生不同序列"


def test_every_draw_appends_one_record():
    state = make_state()
    rng = RNGService(state)
    assert len(state.check_records) == 0
    rng.randint(CheckType.COMMUNICATION_CHECK, "t", 0, 5, reason="r1")
    assert len(state.check_records) == 1
    rng.chance(CheckType.DETECTION_CHECK, "t", 0.3, reason="r2")
    assert len(state.check_records) == 2
    rec = state.check_records[0]
    assert rec.random_seed == "20260604:0"
    assert rec.context["reason"] == "r1"
    assert len(rec.raw_rolls) == 1


def test_record_ids_are_ordered():
    state = make_state()
    rng = RNGService(state)
    for _ in range(3):
        rng.randint(CheckType.COMMUNICATION_CHECK, "t", 0, 5, reason="r")
    ids = [r.check_id for r in state.check_records]
    assert ids == sorted(ids) and len(set(ids)) == 3


# ── 检定型抽取：d100 + 修正 + CheckRecord ──

def test_detection_check_uses_executing_unit():
    state = make_state()
    rng = RNGService(state)
    unit = UNIT_REGISTRY["sbd_scout_section"]
    result, rec = rng.detection_check(
        unit=unit, distance_nm=195, pattern="sector", reason="侦察检定",
    )
    from src.dice import DiceResult
    assert isinstance(result, DiceResult)
    assert rec.check_type == CheckType.DETECTION_CHECK.value
    assert rec.actor_id == unit.name  # 实际执行单位，非 Browning
    assert rec.final_roll == result.modified_roll
    assert rec.degree == result.level
    assert rec.random_seed


def test_communication_check_recorded():
    state = make_state()
    rng = RNGService(state)
    result, rec = rng.communication_check(
        actor_id="VS-6 电台员", competence=5, distance_nm=200,
        reason="通信检定",
    )
    assert rec.check_type == CheckType.COMMUNICATION_CHECK.value
    assert rec.raw_roll == result.raw_roll


def test_roll_check_accepts_raw_roller():
    # dice.roll_check 支持注入骰源（全局 random 路径不变）
    fixed = iter([50])
    result = roll_check(npc_modifier=0, raw_roller=lambda: next(fixed))
    assert result.raw_roll == 50


# ── 旧失真函数：无 rng 时回退全局 random（旧测试语义不变）──

def test_legacy_distortion_wrappers_still_global_random():
    from src.scouting import distort_bearing, distort_distance
    random.seed(42)
    a = (distort_bearing(180, max_error=5), distort_distance(100))
    random.seed(42)
    b = (distort_bearing(180, max_error=5), distort_distance(100))
    assert a == b  # 同种子两次调用结果一致（回退全局 random 路径未变）


def test_scouting_distortion_with_rng_recorded():
    from src.scouting import distort_bearing, compute_report_delay
    state = make_state()
    rng = RNGService(state)
    b1 = distort_bearing(180, max_error=5, rng=rng)
    delay = compute_report_delay(150, rng=rng)
    assert 0 <= b1 <= 359
    assert 20 <= delay <= 60
    assert len(state.check_records) == 2
    assert all(r.context.get("reason") for r in state.check_records)


# ── 侦察管线迁移：检定与失真全部落记录，可回放 ──

def make_scout_state(rng_seed=7):
    state = make_state(rng_seed=rng_seed)
    carrier = state.task_forces[0].carriers[0]
    carrier.aircraft = [
        Aircraft(
            id=f"SBD-VB6-{i:02d}",
            type=AircraftType.SBD,
            squadron="VB-6",
            carrier="Enterprise",
            status=AircraftStatus.READY,
        )
        for i in range(1, 11)
    ]
    state.actual_enemy = [{
        "name": "Kido Butai",
        "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"],
        "position": {"lat": 30.0, "lon": -178.0},
        "status": "rearming",
    }]
    from src.tools import handle_execute_action
    handle_execute_action(state, "launch_scout", {"direction": "southwest"})
    return state


def _advance(state, ticks):
    for _ in range(ticks):
        state.clock.game_time += timedelta(minutes=15)
        from src.scouting import check_scout_results
        check_scout_results(state)


def test_scouting_pipeline_records_checks():
    state = make_scout_state(rng_seed=7)
    _advance(state, 10)
    # 管线至少应产生记录（检定/失真/损失抽取）
    assert len(state.check_records) > 0
    types = {r.check_type for r in state.check_records}
    assert CheckType.DETECTION_CHECK.value in types


def test_scouting_pipeline_replay_identical():
    def run():
        state = make_scout_state(rng_seed=7)
        _advance(state, 14)
        return (
            [r.model_dump() for r in state.check_records],
            [
                {
                    "real": (p.real_bearing, round(p.real_distance_nm, 6),
                             p.real_carrier_count),
                    "reported": (p.reported_bearing, p.reported_distance_nm,
                                 p.reported_carrier_count),
                    "arrive_at": p.arrive_at.isoformat(),
                }
                for p in state.pending_reports
            ],
        )
    assert run() == run(), "同一种子的侦察流程必须逐字段可回放"


def test_no_bare_random_in_scouting_pipeline_path():
    # 静态守卫：scouting.py 管线路径不得直接调用全局 random（迁移完整性）
    import inspect
    import src.scouting as scouting
    for name in ("_process_searching", "_process_returning"):
        src = inspect.getsource(getattr(scouting, name))
        assert "random." not in src, f"{name} 仍直接使用全局 random"


# ── grid 搜索模式映射修复（骰子缺口 #4）──

def test_launch_scout_grid_pattern_maps_to_expanding_square():
    from src.tools import handle_execute_action
    state = make_scout_state(rng_seed=1)
    state.active_scouts.clear()
    result = handle_execute_action(
        state, "launch_scout",
        {"direction": "north", "pattern": "grid"},
    )
    assert "Error" not in result
    assert state.active_scouts[0].search_pattern.value == "expanding_square"


def test_launch_scout_unknown_pattern_falls_back():
    from src.tools import handle_execute_action
    state = make_scout_state(rng_seed=1)
    state.active_scouts.clear()
    handle_execute_action(state, "launch_scout", {"direction": "north", "pattern": "bogus"})
    assert state.active_scouts[0].search_pattern.value == "sector"
