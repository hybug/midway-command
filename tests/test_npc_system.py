"""Tests for §8 NPC系统 — NPC-001~007"""
import pytest
from datetime import datetime, timezone

from src.state import (
    GameState, GameClock, TaskForce, Carrier, Position,
    AirGroup, AirGroupType, AirGroupStatus,
    Aircraft, AircraftType, AircraftStatus,
    EnemyKnown,
)
from src.npc import (
    filter_state_for_npc, get_npc_params, prepare_llm_data,
    get_npc_list,
)
from src.npc_config import NPC_REGISTRY


def _make_state() -> GameState:
    """创建测试状态。"""
    carrier = Carrier(
        name="Enterprise",
        position=Position(lat=31.5, lon=-176.0),
        course=240,
        speed=25,
        air_groups=[
            AirGroup(type=AirGroupType.FIGHTER, count=27, status=AirGroupStatus.READY),
            AirGroup(type=AirGroupType.DIVE_BOMBER, count=38, status=AirGroupStatus.READY),
        ],
    )
    tf = TaskForce(name="TF16", carriers=[carrier], course=240, speed=25)
    state = GameState(
        clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)),
        task_forces=[tf],
        known_enemy=[
            EnemyKnown(
                position=Position(lat=31.0, lon=-180.0),
                description="疑似航母编队",
                confidence="medium",
                source="scout-01",
                reported_at=datetime(1942, 6, 4, 5, 0, tzinfo=timezone.utc),
            )
        ],
    )
    state._hidden_actual_enemy = [{
        "name": "Kido Butai",
        "carriers": ["Akagi", "Kaga"],
        "position": {"lat": 31.0, "lon": -180.0},
    }]
    return state


class TestInfoFilter:
    """NPC-001: 信息过滤"""

    def test_info_filter_browning(self):
        """Browning 看到全局态势"""
        state = _make_state()
        filtered = filter_state_for_npc(state, "browning")
        assert "task_forces" in filtered
        assert "known_enemy" in filtered
        assert "clock" in filtered

    def test_info_filter_murray(self):
        """Murray 只看 Enterprise"""
        state = _make_state()
        filtered = filter_state_for_npc(state, "murray")
        assert "task_forces" in filtered
        # 只有 Enterprise
        for tf in filtered["task_forces"]:
            for carrier in tf["carriers"]:
                assert carrier["name"] == "Enterprise"

    def test_info_filter_comms(self):
        """通信官只看消息"""
        state = _make_state()
        filtered = filter_state_for_npc(state, "radio_officer")
        assert "incoming_messages" in filtered
        # 不应该看到舰队位置
        assert "task_forces" not in filtered


class TestNoActualEnemy:
    """NPC-007: NPC 不访问 actual_enemy"""

    def test_no_actual_enemy(self):
        """actual_enemy 不在过滤结果中"""
        state = _make_state()
        for npc_name in NPC_REGISTRY:
            filtered = filter_state_for_npc(state, npc_name)
            assert "actual_enemy" not in filtered
            assert "_hidden_actual_enemy" not in filtered


class TestNPCParams:
    """NPC 参数查询"""

    def test_get_npc_params(self):
        """获取 NPC 参数"""
        params = get_npc_params("browning")
        assert params is not None
        assert params["name"] == "Miles Browning"
        assert params["competence"] == 9

    def test_get_npc_params_nonexistent(self):
        """不存在的 NPC 返回 None"""
        params = get_npc_params("nonexistent")
        assert params is None


class TestLLMData:
    """NPC-006: LLM 数据准备"""

    def test_llm_data_package(self):
        """LLM 数据包完整性"""
        state = _make_state()
        data = prepare_llm_data(state, "browning", context="侦察报告到达")
        assert "role" in data
        assert "personality" in data
        assert "filtered_state" in data
        assert "context" in data
        assert data["context"] == "侦察报告到达"

    def test_llm_data_personality(self):
        """人格参数正确"""
        state = _make_state()
        data = prepare_llm_data(state, "browning")
        assert data["personality"]["autonomy"] == 8
        assert data["personality"]["competence"] == 9


class TestNPCList:
    """获取 NPC 列表"""

    def test_get_npc_list(self):
        """NPC 列表完整"""
        npcs = get_npc_list()
        assert len(npcs) == 5
        names = [n["name"] for n in npcs]
        assert "Miles Browning" in names
        assert "George Murray" in names
