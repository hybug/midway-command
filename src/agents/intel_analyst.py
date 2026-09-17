"""情报参谋分析 LLM（Phase S2.3）。

把权限内证据视图 + 骰子判定转化为判断书叙述与主张（claims）。
系统不代替参谋下结论：结论文本由本分析器（LLM）产生——没有 client 时
抛错，由 flow 侧降级为 MechanicalPolicy 的结构化产物并显式标注。
"""
from src.llm import LLMClient, get_client


class IntelOfficerAnalyst:
    """情报参谋的分析工作模式（区别于 /chat 的对话模式）。"""

    actor_id = "intel_officer"

    def __init__(self, client: LLMClient | None = None):
        self._client = client

    @property
    def client(self) -> LLMClient:
        if self._client is None:
            self._client = get_client()
        return self._client

    def analyze(self, work_item, evidence_views, dice, profile_dict) -> dict:
        """返回 {narrative, claims: [{claim_type, text, confidence_dimensions}]}。"""
        ev_lines = "\n".join(
            f"- [{e.source_label}] {e.summary}（可靠性 {e.source_reliability}，"
            f"位置精度 {e.dimensions.get('position_precision', '?')}）"
            for e in evidence_views
        )
        prompt = f"""你是情报参谋（Intelligence Officer），正在处理一项情报工作项。

工作项：{getattr(work_item, 'trigger_message_id', '')}
证据：
{ev_lines or '- （无）'}

骰子判定（你不可重算，只能演绎）：等级={dice.level}，偏差方向={dice.error_direction or '无'}，
严重度={dice.error_severity}，你的表达确定性={dice.express_certainty}。

要求：
1. narrative：3-5 句判断书正文。区分【事实】（电文原文说了什么）与【判断】（你认为意味着什么）。
2. claims：1-3 条主张，每条注明 claim_type（fact/judgment/hypothesis）。
3. 你的表达确定性要体现在语气里：不确定就明说不确定。

只输出 JSON：{{"narrative": "...", "claims": [{{"claim_type": "...", "text": "..."}}]}}"""
        result = self.client.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=(
                "你是美军特混舰队情报参谋。你的产出会被登记为正式情报判断书，"
                "必须严格区分事实与判断，不得虚构电文里不存在的证据。"
            ),
        )
        return _parse_analyst_json(result.text)


def _parse_analyst_json(text: str) -> dict:
    import json
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict) and "narrative" in data:
                return data
        except json.JSONDecodeError:
            pass
    return {"narrative": text or "（分析器无输出）",
            "claims": [{"claim_type": "judgment", "text": text}]}
