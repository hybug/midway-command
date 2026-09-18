"""JudgmentEngine 接口（Phase S3.0，计划 §十二）。

v0 使用一个通用 JudgmentEngine（D15），不以 NPC 姓名拆分引擎；
人物差异来自 ActorProfile、权限、记忆、prompt 和少量领域策略（D16）。
实现（S3.1-S3.5 逐段落地）禁止读取 EvidenceView 之外的规则侧数据（D6/D11）。
"""
from typing import Protocol, runtime_checkable

from src.cognition.models import JudgmentContext, JudgmentResult, JudgmentTask


@runtime_checkable
class JudgmentEngine(Protocol):
    """判断引擎：JudgmentTask + JudgmentContext → JudgmentResult。"""

    def assess(self, task: JudgmentTask, context: JudgmentContext) -> JudgmentResult: ...
