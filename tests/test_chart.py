"""Tests for §9 海图参谋系统 — CHART-001~015"""
import pytest
from datetime import datetime, timezone

from src.state import (
    GameState, GameClock, TaskForce, Carrier, Position,
    AirGroup, AirGroupType, AirGroupStatus,
    Aircraft, AircraftType, AircraftStatus,
    EnemyKnown, PendingReport,
)
from src.render.chart import (
    get_chart_data, confirm_contact, get_canvas_coords,
)
from src.render.coordinate import REF_LAT, REF_LON


def _make_state() -> GameState:
    """创建测试状态。"""
    carrier = Carrier(
        name="Enterprise",
        position=Position(lat=31.5, lon=-176.0),
        course=240,
        speed=25,
        air_groups=[
            AirGroup(type=AirGroupType.FIGHTER, count=27, status=AirGroupStatus.READY),
        ],
    )
    tf = TaskForce(name="TF16", carriers=[carrier], course=240, speed=25)
    state = GameState(
        clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)),
        task_forces=[tf],
    )
    return state


class TestFleetDisplay:
    """CHART-001: 己方舰队显示"""

    def test_fleet_display_position(self):
        """舰队位置正确"""
        state = _make_state()
        data = get_chart_data(state)
        assert len(data["fleet"]) == 1
        assert data["fleet"][0]["name"] == "Enterprise"
        assert data["fleet"][0]["lat"] == 31.5
        assert data["fleet"][0]["lon"] == -176.0

    def test_fleet_display_heading(self):
        """舰队航向正确"""
        state = _make_state()
        data = get_chart_data(state)
        assert data["fleet"][0]["course"] == 240


class TestPendingContact:
    """CHART-002: 敌军待确认标记"""

    def test_pending_contact_appear(self):
        """待确认标记出现"""
        state = _make_state()
        state.pending_reports.append(PendingReport(
            scout_id="scout-01",
            detected_at=datetime(1942, 6, 4, 5, 0, tzinfo=timezone.utc),
            arrive_at=datetime(1942, 6, 4, 5, 30, tzinfo=timezone.utc),
            real_bearing=240,
            real_distance_nm=200,
            real_carrier_count=4,
            reported_bearing=238,
            reported_distance_nm=190,
            reported_carrier_count=3,
            confidence="medium",
        ))
        data = get_chart_data(state)
        assert len(data["enemy_contacts"]["pending"]) == 1
        assert data["enemy_contacts"]["pending"][0]["scout_id"] == "scout-01"


class TestConfirmContact:
    """CHART-003: 圈出确认"""

    def test_confirm_contact_data_update(self):
        """确认后数据更新"""
        state = _make_state()
        state.pending_reports.append(PendingReport(
            scout_id="scout-01",
            detected_at=datetime(1942, 6, 4, 5, 0, tzinfo=timezone.utc),
            arrive_at=datetime(1942, 6, 4, 5, 30, tzinfo=timezone.utc),
            real_bearing=240,
            real_distance_nm=200,
            real_carrier_count=4,
            reported_bearing=238,
            reported_distance_nm=190,
            reported_carrier_count=3,
            confidence="medium",
        ))

        result = confirm_contact(state, 0)
        assert result is True
        assert len(state.pending_reports) == 0
        assert len(state.known_enemy) == 1


class TestScoutRoute:
    """CHART-004: 侦察航线显示"""

    def test_scout_route_planning(self):
        """规划中的侦察航线"""
        state = _make_state()
        data = get_chart_data(state)
        assert "scout_routes" in data


class TestMidway:
    """中途岛显示"""

    def test_midway_position(self):
        """中途岛位置正确"""
        data = get_chart_data(_make_state())
        assert data["midway"]["lat"] == REF_LAT
        assert data["midway"]["lon"] == REF_LON
        assert data["midway"]["hex"] == (0, 0)


class TestCanvasCoords:
    """坐标转换"""

    def test_canvas_coords_basic(self):
        """基本坐标转换"""
        x, y = get_canvas_coords(REF_LAT, REF_LON)
        # 中途岛应该在中心附近
        assert abs(x - 400) < 10
        assert abs(y - 400) < 10

    def test_canvas_coords_offset(self):
        """偏移坐标"""
        x1, y1 = get_canvas_coords(REF_LAT, REF_LON)
        x2, y2 = get_canvas_coords(REF_LAT + 1, REF_LON)
        # 纬度增加 → y 减小（向北）
        assert y2 < y1
