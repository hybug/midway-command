"""判断记忆：召回、锚定、修订与反馈（Phase S3.4，计划 §M3.6 / §八 8.2-8.3）。

纪律：
- 记忆按 actor 硬隔离（D7/D8）：召回函数结构性过滤 actor_id，越权读取无入口。
- 记忆只由自身判断、指挥官反馈、新证据和可观察结果更新（D10）。
- 修订必须引用新证据或反馈：create_revision_task 无引用即拒绝（M3.6 验收）。
- 版本链追加制：旧记忆/旧结果只翻状态不删除（M3.6.6）。
"""
from typing import Optional

from src.cognition.models import JudgmentMemory, JudgmentTask
from src.intel import service as intel

# 反馈可取值（与 S2 审批动作同族；反馈不等于修订，§8.3）
COMMANDER_DECISIONS = frozenset({
    "approve", "reject", "defer", "request_revision", "partial_approve",
})

# 锚定加成（v0 设计值，S3.8 消融校准）
ANCHOR_BONUS = 0.06
_MEMORY_CONF_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}


# ── 召回（D7/D8：结构性 actor 隔离）──

def recall_relevant_memories(state, actor_id: str, *,
                             evidence_ids: Optional[list[str]] = None,
                             domain: Optional[str] = None,
                             task_type: Optional[str] = None,
                             limit: int = 5) -> list[JudgmentMemory]:
    """召回该 actor 自己的相关开放/历史记忆（他人记忆永不返回）。"""
    mine = [m for m in state.judgment_memories if m.actor_id == actor_id]
    if domain is not None:
        mine = [m for m in mine if m.domain == domain]
    if task_type is not None:
        mine = [m for m in mine if m.task_type == task_type]
    ev = set(evidence_ids or [])
    if ev:
        mine.sort(key=lambda m: (-len(ev & set(m.evidence_ids)),
                                 -(m.created_at.timestamp() if m.created_at else 0)))
    else:
        mine.sort(key=lambda m: -(m.created_at.timestamp() if m.created_at else 0))
    return mine[:limit]


def latest_open_memory(state, actor_id: str) -> Optional[JudgmentMemory]:
    for m in reversed(state.judgment_memories):
        if m.actor_id == actor_id and m.status == "open":
            return m
    return None


# ── 锚定与坚持（M3.6.3）──

def apply_anchor(scores: dict[str, float], anchor_hypothesis_id: Optional[str],
                 bonus: float) -> dict[str, float]:
    """给锚定候选加分（坚持旧判断）；无锚定原样返回。"""
    if anchor_hypothesis_id is None or anchor_hypothesis_id not in scores:
        return dict(scores)
    out = dict(scores)
    out[anchor_hypothesis_id] = round(out[anchor_hypothesis_id] + bonus, 6)
    return out


def anchor_bonus_for(memory: JudgmentMemory) -> float:
    return ANCHOR_BONUS * _MEMORY_CONF_WEIGHT.get(memory.confidence, 0.3)


# ── 修订任务（M3.6.4：无新证据/反馈不得建版）──

def create_revision_task(state, old_task: JudgmentTask, *,
                         new_evidence_ids: list[str], reason: str = "") -> JudgmentTask:
    """创建修订版任务：证据并集 + 上下文版本 +1 → 新稳定键（允许重判，非重骰）。"""
    if not new_evidence_ids and not reason:
        raise ValueError("修订必须引用新证据或反馈理由（M3.6.4）")
    task = JudgmentTask(
        task_type=old_task.task_type,
        domain=old_task.domain,
        actor_id=old_task.actor_id,
        question=old_task.question,
        evidence_ids=sorted(set(old_task.evidence_ids) | set(new_evidence_ids)),
        context_version=old_task.context_version + 1,
        source="revision",
        supersedes_task_id=old_task.id,
        revision_reason=reason or "新证据到达",
    )
    task.id = intel.next_id(state, "JT")
    task.created_at = intel.now(state)
    state.judgment_tasks.append(task)
    intel._audit(state, actor_id=task.actor_id, action="judgment_task_revise",
                 target_id=task.id, reason=task.revision_reason,
                 evidence_ids=list(new_evidence_ids),
                 details={"supersedes_task": old_task.id})
    return task


# ── 指挥官反馈（§8.3：进记忆，不改写原结果）──

def record_commander_feedback(state, result_id: str, decision: str, *,
                              by: str, note: str = "") -> Optional[JudgmentMemory]:
    if decision not in COMMANDER_DECISIONS:
        raise ValueError(f"非法指挥官反馈: {decision}")
    memory = next((m for m in reversed(state.judgment_memories)
                   if m.result_id == result_id), None)
    if memory is None:
        return None
    memory.commander_decision = decision
    intel._audit(state, actor_id=by, action="commander_feedback",
                 target_id=result_id, reason=note or decision,
                 details={"decision": decision, "memory": memory.id})
    return memory
