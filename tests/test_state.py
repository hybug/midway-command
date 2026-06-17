"""Tests for GameState models."""
from datetime import datetime, timezone

import pytest

from src.state import (
    AirGroup,
    AirGroupStatus,
    AirGroupType,
    Carrier,
    EnemyKnown,
    GameClock,
    GamePhase,
    GameState,
    MissionPlan,
    Position,
    TaskForce,
    TurnType,
)
from src.initial_state import build_initial_state


class TestInitialState:
    """Verify initial state matches historical facts."""

    def test_game_time(self):
        state = build_initial_state()
        assert state.clock.game_time.hour == 4
        assert state.clock.game_time.minute == 0
        assert state.clock.game_time.day == 4
        assert state.clock.game_time.month == 6
        assert state.clock.game_time.year == 1942

    def test_tf16_course_and_speed(self):
        state = build_initial_state()
        tf16 = state.task_forces[0]
        assert tf16.name == "Task Force 16"
        assert tf16.course == 240
        assert tf16.speed == 25

    def test_tf16_position(self):
        state = build_initial_state()
        tf16 = state.task_forces[0]
        # 31.5°N 176°W (~200nm NE of Midway)
        assert 31.0 <= tf16.carriers[0].position.lat <= 32.0
        assert -176.5 <= tf16.carriers[0].position.lon <= -175.5

    def test_two_carriers(self):
        state = build_initial_state()
        tf16 = state.task_forces[0]
        assert len(tf16.carriers) == 2
        names = [c.name for c in tf16.carriers]
        assert "USS Enterprise (CV-6)" in names
        assert "USS Hornet (CV-8)" in names

    def test_air_group_counts(self):
        state = build_initial_state()
        enterprise = state.task_forces[0].carriers[0]

        fighters = [ag for ag in enterprise.air_groups if ag.type == AirGroupType.FIGHTER]
        dive_bombers = [ag for ag in enterprise.air_groups if ag.type == AirGroupType.DIVE_BOMBER]
        torpedo = [ag for ag in enterprise.air_groups if ag.type == AirGroupType.TORPEDO]

        assert len(fighters) == 1
        assert len(dive_bombers) == 1
        assert len(torpedo) == 1
        assert fighters[0].count == 27
        assert dive_bombers[0].count == 38
        assert torpedo[0].count == 15

    def test_air_groups_ready(self):
        state = build_initial_state()
        for tf in state.task_forces:
            for carrier in tf.carriers:
                for ag in carrier.air_groups:
                    assert ag.status == AirGroupStatus.READY
                    assert ag.fuel_pct == 100
                    assert ag.ammo_pct == 100

    def test_known_enemy_empty(self):
        state = build_initial_state()
        assert state.known_enemy == []

    def test_hidden_enemy_exists(self):
        state = build_initial_state()
        assert state._hidden_actual_enemy is not None
        assert len(state._hidden_actual_enemy) == 1
        assert state._hidden_actual_enemy[0]["name"] == "Kido Butai"


class TestSerialization:
    """Verify Pydantic serialization works."""

    def test_state_serializes_to_json(self):
        state = build_initial_state()
        json_str = state.model_dump_json(indent=2)
        assert "Task Force 16" in json_str
        assert "USS Enterprise" in json_str

    def test_hidden_enemy_excluded_from_json(self):
        state = build_initial_state()
        json_str = state.model_dump_json()
        assert "Kido Butai" not in json_str
        assert "_hidden_actual_enemy" not in json_str

    def test_round_trip(self):
        state = build_initial_state()
        json_str = state.model_dump_json()
        parsed = GameState.model_validate_json(json_str)
        assert parsed.task_forces[0].name == "Task Force 16"
        assert parsed.clock.game_time.hour == 4


class TestQueryFunctions:
    """Verify query_* functions don't leak actual state."""

    def test_state_summary_excludes_hidden_enemy(self):
        from src.agents.base import NPCAgent

        class TestAgent(NPCAgent):
            name = "Test"

            def build_system_prompt(self, state):
                return "test"

        agent = TestAgent()
        state = build_initial_state()
        summary = agent.get_state_summary(state)

        assert "_hidden" not in str(summary)
        assert "Kido Butai" not in str(summary)
        assert summary["known_enemy"] == "None"

    def test_state_summary_includes_fleet_data(self):
        from src.agents.base import NPCAgent

        class TestAgent(NPCAgent):
            name = "Test"

            def build_system_prompt(self, state):
                return "test"

        agent = TestAgent()
        state = build_initial_state()
        summary = agent.get_state_summary(state)

        assert summary["game_time"] == "04:00"
        assert len(summary["task_forces"]) == 1
        assert summary["task_forces"][0]["name"] == "Task Force 16"
        assert len(summary["task_forces"][0]["carriers"]) == 2


# ── STATE-001~009: 规格对齐测试 ──

class TestGamePhase:
    """STATE-001: GameState 唯一性 + game_phase 字段"""

    def test_gamestate_creation(self):
        """STATE-001: GameState 可以正常创建"""
        state = build_initial_state()
        assert state is not None
        assert state.clock is not None

    def test_game_phase_default_playing(self):
        """game_phase 默认为 PLAYING"""
        state = build_initial_state()
        assert state.game_phase == GamePhase.PLAYING

    def test_game_phase_can_be_game_over(self):
        """game_phase 可以设置为 GAME_OVER"""
        state = build_initial_state()
        state.game_phase = GamePhase.GAME_OVER
        assert state.game_phase == GamePhase.GAME_OVER


class TestPositionUnified:
    """STATE-002/003: Position 统一 + to_tuple"""

    def test_position_unified(self):
        """STATE-002: Position 使用 state.py 的定义"""
        pos = Position(lat=31.5, lon=-176.0)
        assert pos.lat == 31.5
        assert pos.lon == -176.0

    def test_position_to_tuple(self):
        """STATE-003: Position.to_tuple() 返回 (lat, lon)"""
        pos = Position(lat=31.5, lon=-176.0)
        assert pos.to_tuple() == (31.5, -176.0)

    def test_position_optional_fields(self):
        """Position 可选字段正确"""
        pos = Position(lat=31.5, lon=-176.0, bearing=240, distance_nm=200, reference="TF16")
        assert pos.bearing == 240
        assert pos.distance_nm == 200
        assert pos.reference == "TF16"


class TestActualEnemyAccessible:
    """STATE-004: actual_enemy 公开属性"""

    def test_actual_enemy_accessible(self):
        """STATE-004: actual_enemy 是公开属性"""
        state = build_initial_state()
        # actual_enemy 应该是公开字段
        assert hasattr(state, 'actual_enemy')
        assert isinstance(state.actual_enemy, list)

    def test_actual_enemy_in_model_dump(self):
        """STATE-007: actual_enemy 包含在序列化中"""
        state = build_initial_state()
        data = state.model_dump()
        assert 'actual_enemy' in data


class TestSerializationExtended:
    """STATE-007/008/009: 序列化、约束、默认值"""

    def test_serialization_roundtrip(self):
        """STATE-007: model_dump → model_validate 往返"""
        state = build_initial_state()
        data = state.model_dump()
        restored = GameState.model_validate(data)
        assert restored.clock.game_time == state.clock.game_time
        assert len(restored.task_forces) == len(state.task_forces)

    def test_field_constraints(self):
        """STATE-008: Pydantic 约束在创建时生效"""
        # speed 不能为负 — 创建时应报错
        clock = GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc))
        with pytest.raises(Exception):
            TaskForce(name="Test", course=0, speed=-1)

        # action_points 不能为负 — 创建时应报错
        with pytest.raises(Exception):
            GameState(clock=clock, action_points=-1)

    def test_defaults(self):
        """STATE-009: 默认值正确"""
        clock = GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc))
        state = GameState(clock=clock)
        assert state.game_phase == GamePhase.PLAYING
        assert state.turn_type == TurnType.NORMAL
        assert state.action_points == 3
        assert state.max_action_points == 3
        assert state.task_forces == []
        assert state.known_enemy == []
        assert state.actual_enemy == []


class TestMissionPlan:
    """MissionPlan 数据模型"""

    def test_mission_plan_creation(self):
        """MissionPlan 可以正常创建"""
        plan = MissionPlan(
            id="plan-001",
            target_position=Position(lat=31.0, lon=-180.0),
            target_course=110,
            target_speed=20,
            intercept_point=Position(lat=31.2, lon=-179.5),
            intercept_heading=235,
            intercept_distance_nm=185,
            flight_time_min=74,
            fuel_margin_pct=22.5,
            feasible=True,
            npc_briefing_data={"target": {"bearing": 240}},
        )
        assert plan.id == "plan-001"
        assert plan.feasible is True
        assert plan.fuel_margin_pct == 22.5

    def test_mission_plan_in_state(self):
        """GameState 可以包含 mission_plans"""
        state = build_initial_state()
        assert state.mission_plans == []


class TestAirGroupExtended:
    """AirGroup 扩展字段"""

    def test_air_group_new_fields(self):
        """AirGroup 新增字段可正常使用"""
        ag = AirGroup(
            id="ag-001",
            type=AirGroupType.DIVE_BOMBER,
            count=38,
            carrier_name="USS Enterprise (CV-6)",
            mission_type="strike",
        )
        assert ag.id == "ag-001"
        assert ag.carrier_name == "USS Enterprise (CV-6)"
        assert ag.mission_type == "strike"
        assert ag.plan_id is None
        assert ag.intercept_heading is None

    def test_air_group_status_planning(self):
        """AirGroupStatus 包含 PLANNING"""
        assert AirGroupStatus.PLANNING == "planning"
        assert AirGroupStatus.ATTACKING == "attacking"
        assert AirGroupStatus.REFUELING == "refueling"
        assert AirGroupStatus.REARMING == "rearming"
        assert AirGroupStatus.LOST == "lost"
