"""Captain Marc A. Mitscher — Hornet (CV-8) captain.

Quiet, professional, pilot by background. Speaks sparingly but with authority
on aviation matters.
"""
from src.agents.base import NPCAgent
from src.npc_config import NPC_REGISTRY
from src.state import GameState
from src.tools import TOOLS_SCHEMA, TOOL_HANDLERS


class MitscherNPC(NPCAgent):
    """Marc A. Mitscher, captain of USS Hornet."""

    name = "Marc Mitscher"
    role = "大黄蜂舰长"
    _config = NPC_REGISTRY["mitscher"]

    @property
    def tools(self) -> list:
        allowed = set(self._config.allowed_tools)
        return [t for t in TOOLS_SCHEMA if t["function"]["name"] in allowed]

    @property
    def tool_handlers(self) -> dict:
        allowed = set(self._config.allowed_tools)
        return {k: v for k, v in TOOL_HANDLERS.items() if k in allowed}

    def build_system_prompt(self, state: GameState) -> str:
        summary = self.get_state_summary(state)

        return f"""你是 Marc A. Mitscher，USS Hornet (CV-8) 舰长，海军上校。

**语言：** 必须用中文回复。海军术语用"中文（英文）"格式。

**你的性格：**
- 沉默寡言、专业、飞行员出身
- 说话极简，能一句话说完的不用两句
- 不闲聊，不解释背景，直接报结果
- 在本舰事务上有权威，但不会越权干涉战略决策
- 飞行员出身，对航空作业有深刻理解

**当前态势（1942/6/4 {summary['game_time']}）：**
{self._format_own_carrier(summary)}

**你的职责范围：**
- 大黄蜂号的航行安全
- 大黄蜂号的 CAP 部署
- 大黄蜂号的甲板作业和损管
- 大黄蜂号的航空队状态

**你无权做的事：**
- 调整特混舰队航向/航速
- 发起侦察任务
- 指挥企业号事务

**工具使用：**
- `query_fleet_status(task_force_id)`: 查询状态。你只关注大黄蜂号。
- `execute_action(action_type, details)`: 执行本舰行动。
  - `adjust_cap`: 调整大黄蜂号 CAP 强度

**回复风格：**
- 极简。"CAP 12 架。" "甲板清空。" "收到。"
- 不主动提建议，除非指挥官问
- 报告用短句，不用长段
"""

    def _format_own_carrier(self, summary: dict) -> str:
        for tf in summary["task_forces"]:
            for c in tf["carriers"]:
                if "hornet" in c["name"].lower():
                    lines = [
                        f"- 大黄蜂号位置: {c['position']}",
                        f"- CAP: {c['cap']} 架战斗机",
                    ]
                    for ag in c["air_groups"]:
                        lines.append(
                            f"  - {ag['type']}: {ag['count']} 架 "
                            f"({ag['status']}, 油{ag['fuel']}%, 弹{ag['ammo']}%)"
                        )
                    return "\n".join(lines)
        return "- 大黄蜂号数据不可用"

    def get_state_summary(self, state: GameState) -> dict:
        """Filter to Hornet only."""
        base = super().get_state_summary(state)
        filtered_tfs = []
        for tf in base["task_forces"]:
            filtered_carriers = [
                c for c in tf["carriers"]
                if "hornet" in c["name"].lower()
            ]
            if filtered_carriers:
                filtered_tfs.append({**tf, "carriers": filtered_carriers})
        base["task_forces"] = filtered_tfs
        return base
