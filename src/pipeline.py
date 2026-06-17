"""Tick Pipeline — 按顺序执行游戏逻辑步骤。

每个 tick 由多个 TickStep 组成，按 order 从小到大依次执行。
某步骤抛异常时记录日志并跳过，不影响后续步骤。

用法：
    pipeline = Pipeline()
    pipeline.register(TickStep(name="advance_clock", handler=advance_clock, order=10))
    pipeline.register(TickStep(name="update_positions", handler=update_positions, order=20))
    notifications = pipeline.execute(state, minutes=15)
"""
import logging
from dataclasses import dataclass, field
from typing import Callable

from src.state import GameState

logger = logging.getLogger("midway.pipeline")


@dataclass
class TickStep:
    """管线中的一个步骤。"""
    name: str
    handler: Callable[[GameState, int], list[str]]
    order: int
    enabled: bool = True


class Pipeline:
    """Tick 管线：按 order 依次执行所有注册的步骤。"""

    def __init__(self):
        self.steps: list[TickStep] = []

    def register(self, step: TickStep):
        """注册一个步骤。同名步骤覆盖旧的。"""
        # 移除同名旧步骤
        self.steps = [s for s in self.steps if s.name != step.name]
        self.steps.append(step)
        self.steps.sort(key=lambda s: s.order)
        logger.info(f"[PIPELINE] Registered: {step.name} (order={step.order})")

    def disable(self, name: str):
        """临时禁用一个步骤。"""
        for step in self.steps:
            if step.name == name:
                step.enabled = False
                logger.info(f"[PIPELINE] Disabled: {name}")

    def enable(self, name: str):
        """启用一个步骤。"""
        for step in self.steps:
            if step.name == name:
                step.enabled = True
                logger.info(f"[PIPELINE] Enabled: {name}")

    def execute(self, state: GameState, minutes: int = 15) -> list[str]:
        """执行所有启用的步骤，返回通知列表。

        某步骤抛异常时记录日志并跳过，不影响后续步骤。
        """
        all_notifications = []

        for step in self.steps:
            if not step.enabled:
                continue
            try:
                notifications = step.handler(state, minutes)
                if notifications:
                    all_notifications.extend(notifications)
            except Exception as e:
                logger.error(f"[PIPELINE] Step '{step.name}' failed: {e}", exc_info=True)
                # 继续执行后续步骤

        return all_notifications
