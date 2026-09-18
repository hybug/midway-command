"""S3 基础契约（Phase S3.0）。

固定：
- 任务/置信度/错误类型枚举（M3.2.2 / M3.5.7 / M3.5.1-6）
- 稳定判断键 compute_stable_key（M3.2.4，D9：同问题+同证据+同处境不得重骰）
- 有效维度与候选维度登记（D17/D18：v0 只启用五维）

本模块为纯契约层：不导入运行时状态模型。
"""
import hashlib
from enum import Enum


class TaskType(str, Enum):
    """判断任务类型（M3.2.2）。"""
    ASSESS = "assess"        # 评估当前局势
    PREDICT = "predict"      # 预测敌人行动
    RECOMMEND = "recommend"  # 提出行动建议
    COMPARE = "compare"      # 比较候选解释/方案
    DECIDE = "decide"        # 提请决心（仍由玩家决断）


class ConfidenceBand(str, Enum):
    """三档置信度（M3.5.7）：只由证据决定，不由骰子直接指定。"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ErrorType(str, Enum):
    """认知错误类型（M3.5.1-6）：最大距离对应的维度；兼容集合内为 none。"""
    NONE = "none"
    IDENTITY = "identity"
    COUNT = "count"
    POSITION = "position"
    COURSE = "course"
    SPEED = "speed"


class MemoryStatus(str, Enum):
    """判断记忆状态（M3.6）：open 现行 / revised 已修订 / superseded 被替代。"""
    OPEN = "open"
    REVISED = "revised"
    SUPERSEDED = "superseded"


class RefusalReason(str, Enum):
    """拒绝/未知（M3.7）：不把推测自动升级为自信答案。"""
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"   # 证据不足
    EVIDENCE_CONFLICT = "evidence_conflict"           # 证据冲突未决
    OUT_OF_DUTY = "out_of_duty"                       # 超出职责（须转交/说明）


# ── 人物参数维度（D17/D18）──

ACTIVE_ATTRIBUTE_DIMS: tuple[str, ...] = (
    "competence", "risk_tolerance", "imagination", "initiative", "autonomy",
)
CANDIDATE_ATTRIBUTE_DIMS: tuple[str, ...] = (
    "skepticism", "confidence_bias", "stress_sensitivity",
)
ATTRIBUTE_MIN = 0
ATTRIBUTE_MAX = 10


# ── 公式版本（S3.2 起使用；契约层先固定命名）──

FORMULA_VERSION = "v0-5dim"


# ── 稳定判断键（M3.2.4 / D9）──

def normalize_question(question: str) -> str:
    """问题规范化：去首尾空白、压内部连续空白。语义内容不变。"""
    return " ".join(str(question).split())


def compute_stable_key(*, actor_id: str, task_type: str, domain: str,
                       question_normalized: str, evidence_ids: list[str],
                       context_version: int) -> str:
    """稳定判断键：判断者 + 任务类型 + 域 + 规范化问题 + 证据集（顺序无关）+ 上下文版本。

    同一稳定键的重复请求必须返回同一结果（缓存命中，禁止重骰）；
    证据集或上下文变化 → 新键 → 允许新版本判断。
    """
    payload = "|".join([
        actor_id,
        str(task_type),
        domain,
        question_normalized,
        ",".join(sorted(evidence_ids)),
        str(context_version),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
