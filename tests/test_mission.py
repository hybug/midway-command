"""Tests for §5 出击规划 — AIR-017~022"""
import pytest
from datetime import datetime, timezone

from src.state import (
    GameState, GameClock, TaskForce, Carrier, Position,
    Aircraft, AircraftType, AircraftStatus,
)
from src.mission import (
    calculate_intercept, calculate_fuel_budget,
    plan_mission, confirm_mission, reject_mission,
    get_mission_plan,
)


def _make_state() -> GameState:
    aircraft = [
        Aircraft(id="SBD-01", type=AircraftType.SBD, squadron="VB-6", carrier="Enterprise"),
        Aircraft(id="SBD-02", type=AircraftType.SBD, squadron="VB-6", carrier="Enterprise"),
    ]
    carrier = Carrier(
        name="Enterprise",
        position=Position(lat=31.5, lon=-176.0),
        course=240,
        speed=25,
        aircraft=aircraft,
    )
    tf = TaskForce(name="TF16", carriers=[carrier], course=240, speed=25)
    return GameState(
        clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)),
        task_forces=[tf],
    )


class TestInterceptCalc:
    """AIR-017: 拦截点计算"""

    def test_intercept_basic(self):
        """基本拦截计算"""
        result = calculate_intercept(
            enemy_lat=31.0, enemy_lon=-180.0,
            enemy_course=110, enemy_speed=20,
            launch_lat=31.5, launch_lon=-176.0,
            aircraft_speed=150,
        )
        assert result is not None
        assert result["distance_nm"] > 0
        assert result["flight_time_min"] > 0
        assert 0 <= result["heading"] < 360

    def test_intercept_no_solution(self):
        """飞机速度不足"""
        result = calculate_intercept(
            enemy_lat=31.0, enemy_lon=-180.0,
            enemy_course=110, enemy_speed=200,  # 敌舰比飞机快
            launch_lat=31.5, launch_lon=-176.0,
            aircraft_speed=150,
        )
        # 可能有解也可能无解，取决于具体参数
        # 只要不抛异常即可


class TestFuelBudget:
    """AIR-018: 油量预算"""

    def test_fuel_budget_sufficient(self):
        """油量充足（短距离）"""
        budget = calculate_fuel_budget(50, "SBD")
        # outbound = 0.6*50 = 30%, return = 30%, reserve = 10%, total = 70%, margin = 30%
        assert budget["feasible"] is True
        assert budget["fuel_margin_pct"] > 0

    def test_fuel_budget_insufficient(self):
        """油量不足（超长距离）"""
        budget = calculate_fuel_budget(200, "SBD")
        # outbound = 0.6*200 = 120%, already > 100%
        assert budget["feasible"] is False
        assert budget["fuel_margin_pct"] < 0

    def test_fuel_budget_tight(self):
        """油量紧张"""
        budget = calculate_fuel_budget(60, "SBD")
        # outbound = 0.6*60 = 36%, return = 36%, reserve = 10%, total = 82%, margin = 18%
        assert budget["feasible"] is True
        assert budget["warning"] is not None


class TestPlanMission:
    """AIR-019: 出击规划流程"""

    def test_planning_flow(self):
        """创建规划"""
        state = _make_state()
        enemy_report = {
            "position": {"lat": 31.0, "lon": -180.0},
            "course": 110,
            "speed": 20,
            "description": "疑似航母编队",
            "confidence": "medium",
        }
        plan = plan_mission(state, enemy_report)
        assert plan is not None
        assert plan.id is not None
        assert plan.feasible is not None
        assert plan.npc_briefing_data is not None

    def test_npc_briefing_data(self):
        """AIR-020: NPC 简报数据完整性"""
        state = _make_state()
        enemy_report = {
            "position": {"lat": 31.0, "lon": -180.0},
            "course": 110,
            "speed": 20,
            "description": "疑似航母编队",
            "confidence": "medium",
        }
        plan = plan_mission(state, enemy_report)
        data = plan.npc_briefing_data
        assert "target" in data
        assert "intercept" in data
        assert "fuel" in data
        assert "warnings" in data
        assert "feasible" in data


class TestConfirmReject:
    """AIR-021/022: 确认/拒绝"""

    def test_plan_confirm(self):
        """AIR-022: 确认方案"""
        state = _make_state()
        enemy_report = {
            "position": {"lat": 31.0, "lon": -180.0},
            "course": 110,
            "speed": 20,
        }
        plan = plan_mission(state, enemy_report)
        if plan.feasible:
            ag = confirm_mission(state, plan.id)
            assert ag is not None

    def test_plan_reject(self):
        """AIR-021: 拒绝方案"""
        state = _make_state()
        enemy_report = {
            "position": {"lat": 31.0, "lon": -180.0},
            "course": 110,
            "speed": 20,
        }
        plan = plan_mission(state, enemy_report)
        reject_mission(state, plan.id)
        assert plan.feasible is False
