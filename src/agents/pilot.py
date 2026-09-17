"""SBD 侦察机飞行员报告 NPC（Phase S2.3，D16）。

按人物风格撰写电文：侦察中队飞行员的无线电简报风格——简短、
无线电纪律、先方位距离后舰型数量，紧张时口语化。文风由人物设定控制，
不同单位可派生不同风格子类。

测试注入 fake client；无 API key 时由 flow 侧降级为机械拍发（正常游玩
必须接 LLM——降级路径仅在无 key 环境/测试中存在，见 flow._default_writer）。
"""
from src.llm import LLMClient, get_client

# 单位风格档案（D16：文风、重点与习惯由人物决定，非共用模板）
PILOT_PROFILES = {
    "sbd_scout_section": {
        "actor_id": "sbd_scout_pilot",
        "rank": "Liteutenant (jg)",
        "squadron": "VS-6",
        "style": (
            "无线电话纪律：全大写短语、少标点；先方位距离、后舰型数量、"
            "末尾报己方油量。紧张时夹杂口语（如 LOOKOUT!）。"
        ),
    },
}


class PilotReportNPC:
    """侦察机飞行员：从可见观测值撰写电文（不知道规则侧真值）。"""

    def __init__(self, client: LLMClient | None = None,
                 profile_key: str = "sbd_scout_section"):
        self._client = client
        self._profile_key = profile_key
        self.profile = PILOT_PROFILES[profile_key]

    @property
    def client(self) -> LLMClient:
        if self._client is None:
            self._client = get_client()  # 无 key 时抛 ValueError，由调用方降级
        return self._client

    @property
    def actor_id(self) -> str:
        return self.profile["actor_id"]

    def write_report(self, view: dict, game_time: str) -> str:
        """view 为失真后的可见观测值（bearing/distance/count/quality）。"""
        prompt = f"""你是 {self.profile['rank']}，{self.profile['squadron']} 侦察中队飞行员，
驾驶 SBD 无畏式俯冲轰炸机在太平洋上执行搜索任务。

{self.profile['style']}

你在 {game_time}（Zulu）看到以下情况：
- 方位：{view.get('bearing')}°（从舰队位置）
- 距离：约 {view.get('distance_nm')} 海里
- 看到的舰船数量：{view.get('count')}
- 识别置信：{view.get('quality')}（high=清晰识别航母 / standard=大致识别 / low=只看到大型船只）

用 2-4 行电文报告你看到的情况。只输出电文正文，不要任何解释。
记住：你只能报告你亲眼看到的，距离远时不确定就说不确定。"""
        result = self.client.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=(
                "你是1942年美军航母侦察机飞行员，正在用无线电向旗舰拍发接触报告。"
                "严格遵守无线电简报格式。"
            ),
        )
        return result.text.strip() or "NO CONTACT REPORT AVAILABLE"
