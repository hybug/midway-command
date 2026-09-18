"""人物层：LLM 候选生成与人物化表达（Phase S3.5，计划 §M3.8.7 / §十一）。

职责切分（D2/§十一）：
- LLM 生成有角色特色的候选解释（结构化 raw dict → normalize_candidates 规范化）；
- LLM 按最终 JudgmentResult 写人物化报告（【事实】/【判断】/【推测】 markers）；
- 规则层已锁定 chosen_hypothesis——人物化表达不得改写结构化结论（结构性保证：
  render_report 只消费 result 的只读快照，返回纯文本，不触碰 state）。

防泄漏（D6/D11）：prompt 只装配 context.evidence（权限内 EvidenceView）与
actor 档案/自身记忆；无 actual_enemy / internal_truth_ref 通道。
降级：无 LLM 时 MechanicalCandidates + FallbackRenderer，显式标记
「机械降级·非正式玩法路径」（验收要求）。
"""
import json
from typing import Optional

from src.cognition.models import ActorProfile, JudgmentContext, JudgmentResult, JudgmentTask

_DEGRADED_MARKER = "【机械降级·非正式玩法路径】"


def _extract_json(text: str):
    text = (text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def _persona_block(actor: ActorProfile) -> str:
    lines = [f"你是 {getattr(actor, 'display_name', '') or actor.actor_id}"
             f"（{actor.role}），domain={actor.domain or 'unassigned'}。"]
    focus = getattr(actor, "judgment_focus", "")
    if focus:
        lines.append(f"你的判断重点：{focus}。")
    duty = getattr(actor, "duty_boundary", [])
    for d in duty:
        lines.append(f"职责边界：{d}。")
    return "\n".join(lines)


def _evidence_block(context: JudgmentContext) -> str:
    if not context.evidence:
        return "（无可见证据）"
    lines = []
    for v in context.evidence:
        dims = v.dimensions or {}
        lines.append(
            f"- [{v.evidence_id}] {v.source_label}：{v.summary}"
            f"（来源可靠性 {v.source_reliability}，"
            f"识别精度 {dims.get('identity_precision', '?')}，"
            f"位置精度 {dims.get('position_precision', '?')}）"
        )
    return "\n".join(lines)


def _memory_block(context: JudgmentContext) -> str:
    if not context.memories:
        return ""
    lines = ["你此前相关判断（你自己的记忆，其他参谋不可见）："]
    for m in context.memories[:3]:
        if m.selected_hypothesis:
            lines.append(f"- 曾判断：{m.selected_hypothesis}"
                         f"（置信 {m.confidence}，证据 {','.join(m.evidence_ids) or '无'}）"
                         + (f"；指挥官反馈：{m.commander_decision}" 
                            if m.commander_decision else ""))
    return "\n".join(lines) + "\n"


class LLMCandidateGenerator:
    """候选生成（LLM 实现 CandidateGenerator 协议；S3.1 规范化在其后）。"""

    def __init__(self, actor: ActorProfile, client=None):
        self._actor = actor
        self._client = client

    @property
    def client(self):
        if self._client is None:
            from src.llm import get_client
            self._client = get_client()
        return self._client

    def generate(self, task: JudgmentTask, context: JudgmentContext) -> list[dict]:
        user = f"""{_persona_block(self._actor)}
判断任务（{task.task_type}/{task.domain}）：{task.question}

可见证据（只有这些，不得虚构其他证据）：
{_evidence_block(context)}
{_memory_block(context)}
请生成 1-3 个候选解释。每个候选包含：
- text：一句话解释
- predicted_class：预测舰型（CV/CVL/CA/transport/unknown 或 null）
- predicted_count_range：预测数量区间 [min, max] 或 null
- predicted_position：预测位置 [lat, lon] 或 null
- predicted_course_range / predicted_speed_range：航向/航速区间或 null
- supporting_evidence_ids：支撑证据 id
- assumptions：关键假设
- recommendation：若成立时的行动建议（一句话）
- change_my_mind：什么新信息会让你放弃该候选

若证据不足以形成任何候选，或任务超出你的职责，返回 {{"candidates": [], "refusal": "理由"}}。
只输出 JSON。"""
        reply = self.client.chat(
            messages=[{"role": "user", "content": user}],
            system_prompt=(
                "你是1942年美军特混舰队的参谋军官，正在为指挥官形成正式判断。"
                "只依据给出的证据，严格保持你的职责与人物性格。"),
        )
        return self._candidates_from(_extract_json(reply.text))

    def _candidates_from(self, data) -> list[dict]:
        if not isinstance(data, dict):
            return []
        raw = data.get("candidates")
        if not isinstance(raw, list):
            return []
        return [c for c in raw if isinstance(c, dict) and c.get("text")]


class MechanicalCandidates:
    """无 LLM 降级候选（非玩法路径；显式 degraded 标记）。"""

    def __init__(self, actor: ActorProfile):
        self._actor = actor

    def generate(self, task: JudgmentTask, context: JudgmentContext) -> list[dict]:
        if not context.evidence:
            return []
        first = context.evidence[0]
        return [{
            "text": f"（降级）基于 {first.source_label} 现有证据的保守评估："
                    f"{first.summary}",
            "supporting_evidence_ids": [first.evidence_id],
            "assumptions": ["机械降级产物，非人物化判断"],
            "recommendation": "等待更多证据印证。",
            "change_my_mind": ["获得新证据或勘误时重新研判"],
            "degraded": True,
        }]


def render_report(actor: ActorProfile, task: JudgmentTask, result: JudgmentResult,
                  hypotheses: list[dict], *, client=None) -> str:
    """结构化结果 → 人物化报告文本（只读渲染；不改写 result）。"""
    if client is None:
        return FallbackRenderer()(actor, task, result, hypotheses)
    chosen = next((h for h in hypotheses
                   if h.get("id") == result.chosen_hypothesis_id), None)
    user = f"""{_persona_block(actor)}
判断任务：{task.question}

规则引擎已锁定结论（你不得改写、不得重算、不得另立结论）：
- 选定候选：{chosen.get('text') if chosen else '（拒绝判断）'}
- 置信度：{result.confidence_band}
- 认知错误：{result.error_type}（严重度 {result.error_severity}）
- 建议：{result.recommendation or '无'}
- 关键假设：{'；'.join(result.assumptions) or '无'}
- 何种新信息会改变判断：{'；'.join(result.change_my_mind) or '无'}

全部候选：
{json.dumps(hypotheses, ensure_ascii=False, indent=1)}

请写 3-5 句报告正文。要求：
1. 用【事实】【判断】【推测】前缀区分信息性质；
2. 语气体现你的性格与表达确定性；
3. 不得引入证据清单之外的事实，不得替其他参谋发言。
只输出报告正文。"""
    try:
        return client.chat(
            messages=[{"role": "user", "content": user}],
            system_prompt="你是1942年美军特混舰队参谋军官，正在向指挥官呈报正式判断。",
        ).text.strip()
    except Exception:
        return FallbackRenderer()(actor, task, result, hypotheses)


class FallbackRenderer:
    """机械降级渲染（无 LLM；显式标记非正式玩法路径）。"""

    def __call__(self, actor: ActorProfile, task: JudgmentTask,
                 result: JudgmentResult, hypotheses: list[dict]) -> str:
        chosen = next((h for h in hypotheses
                       if h.get("id") == result.chosen_hypothesis_id), None)
        if result.refusal_reason:
            line = f"（拒绝判断：{result.refusal_reason}）{result.recommendation or ''}"
        elif chosen:
            line = (f"选定判断：{chosen.get('text', '')}（置信 {result.confidence_band}）"
                    f"建议：{result.recommendation or '无'}")
        else:
            line = "（无有效判断）"
        return (f"{_DEGRADED_MARKER}\n"
                f"{getattr(actor, 'display_name', '') or actor.actor_id}"
                f"（{actor.role}）：{line}")
