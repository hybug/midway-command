"""Tests for §2 Tick Pipeline — TIME-008~009"""
import pytest
from datetime import datetime, timezone

from src.pipeline import Pipeline, TickStep
from src.state import GameClock, GameState


def _make_state() -> GameState:
    return GameState(clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)))


class TestPipelineOrder:
    """TIME-008: 管线执行顺序"""

    def test_pipeline_order(self):
        """TC-TIME-008: 步骤按 order 从小到大执行"""
        call_order = []

        def step_a(state, minutes):
            call_order.append("A")
            return []

        def step_b(state, minutes):
            call_order.append("B")
            return []

        def step_c(state, minutes):
            call_order.append("C")
            return []

        pipeline = Pipeline()
        pipeline.register(TickStep(name="C", handler=step_c, order=30))
        pipeline.register(TickStep(name="A", handler=step_a, order=10))
        pipeline.register(TickStep(name="B", handler=step_b, order=20))

        pipeline.execute(_make_state())
        assert call_order == ["A", "B", "C"]

    def test_pipeline_step_exception_continues(self):
        """TC-TIME-008b: 步骤异常不影响后续"""
        call_order = []

        def step_a(state, minutes):
            call_order.append("A")
            return []

        def step_b(state, minutes):
            raise ValueError("test error")

        def step_c(state, minutes):
            call_order.append("C")
            return []

        pipeline = Pipeline()
        pipeline.register(TickStep(name="A", handler=step_a, order=10))
        pipeline.register(TickStep(name="B", handler=step_b, order=20))
        pipeline.register(TickStep(name="C", handler=step_c, order=30))

        notifications = pipeline.execute(_make_state())
        assert call_order == ["A", "C"]  # B 被跳过

    def test_pipeline_returns_notifications(self):
        """步骤返回的通知被收集"""
        def step_a(state, minutes):
            return ["notification A"]

        def step_b(state, minutes):
            return ["notification B1", "notification B2"]

        pipeline = Pipeline()
        pipeline.register(TickStep(name="A", handler=step_a, order=10))
        pipeline.register(TickStep(name="B", handler=step_b, order=20))

        notifications = pipeline.execute(_make_state())
        assert notifications == ["notification A", "notification B1", "notification B2"]


class TestPipelineRegister:
    """TIME-009: 管线步骤注册"""

    def test_pipeline_register_override(self):
        """TC-TIME-009: 同名步骤覆盖旧的"""
        call_count = {"count": 0}

        def handler_v1(state, minutes):
            call_count["count"] += 1
            return ["v1"]

        def handler_v2(state, minutes):
            call_count["count"] += 10
            return ["v2"]

        pipeline = Pipeline()
        pipeline.register(TickStep(name="test", handler=handler_v1, order=10))
        pipeline.register(TickStep(name="test", handler=handler_v2, order=10))

        notifications = pipeline.execute(_make_state())
        assert notifications == ["v2"]
        assert call_count["count"] == 10  # v1 没有被调用

    def test_pipeline_disable(self):
        """禁用步骤不执行"""
        call_order = []

        def step_a(state, minutes):
            call_order.append("A")
            return []

        def step_b(state, minutes):
            call_order.append("B")
            return []

        pipeline = Pipeline()
        pipeline.register(TickStep(name="A", handler=step_a, order=10))
        pipeline.register(TickStep(name="B", handler=step_b, order=20))

        pipeline.disable("B")
        pipeline.execute(_make_state())
        assert call_order == ["A"]

    def test_pipeline_enable(self):
        """启用步骤恢复执行"""
        call_order = []

        def step_a(state, minutes):
            call_order.append("A")
            return []

        pipeline = Pipeline()
        pipeline.register(TickStep(name="A", handler=step_a, order=10))

        pipeline.disable("A")
        pipeline.execute(_make_state())
        assert call_order == []

        pipeline.enable("A")
        pipeline.execute(_make_state())
        assert call_order == ["A"]
