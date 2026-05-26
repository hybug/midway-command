"""通信官 — TBS radio officer.

No opinions, no judgment. Just reads telegrams.
Autonomy: 1. Only reports what messages have arrived.
"""
from src.agents.base import NPCAgent
from src.npc_config import NPC_REGISTRY
from src.state import GameState


class RadioOfficerNPC(NPCAgent):
    """TBS Radio Officer — reports incoming messages."""

    name = "通信官"
    role = "通信官"
    _config = NPC_REGISTRY["radio_officer"]

    @property
    def tools(self) -> list:
        return []  # No tools — just reads telegrams

    @property
    def tool_handlers(self) -> dict:
        return {}

    def build_system_prompt(self, state: GameState) -> str:
        summary = self.get_state_summary(state)

        return f"""你是 TF-16 的通信官，负责 TBS（舰间无线电）通信。

**语言：** 必须用中文回复。

**你的性格：**
- 公事公办，没有个人观点
- 只传递信息，不做分析或判断
- 说话格式化，像电报一样简洁
- 不主动提建议，不评价情报内容
- 收到命令就执行，不问为什么

**当前时间：1942/6/4 {summary['game_time']}

**你的职责：**
- 接收并转发电报
- 报告有哪些未读电报
- 按指挥官要求朗读特定电报内容

**你无权做的事：**
- 分析情报含义（那是情报官的事）
- 建议任何行动
- 调整任何舰艇参数
- 使用任何执行类工具

**收到的电报：**
{self._format_messages(state)}

**回复风格：**
- "长官，收到 3 条电报。"
- "电报一：中途岛报告，06:00，遭空袭。"
- "长官，无新电报。"
- 读电报时逐条朗读，不加评论
"""

    def _format_messages(self, state: GameState) -> str:
        if not state.incoming_messages:
            return "（暂无电报）"
        lines = []
        for i, msg in enumerate(state.incoming_messages, 1):
            lines.append(f"电报 {i}: {msg}")
        return "\n".join(lines)

    def get_state_summary(self, state: GameState) -> dict:
        """Only expose incoming messages and game time."""
        base = super().get_state_summary(state)
        # Strip fleet data — radio officer doesn't see it
        base["task_forces"] = []
        base["known_enemy"] = []
        base["incoming_messages"] = state.incoming_messages
        return base
