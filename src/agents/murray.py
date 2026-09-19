"""Captain George D. Murray — Enterprise (CV-6) captain.

Steady, professional, respects Browning's authority but has opinions
on his own ship's operations.
"""
from src.agents.base import NPCAgent
from src.npc_config import NPC_REGISTRY
from src.state import GameState
from src.tools import TOOLS_SCHEMA, TOOL_HANDLERS


class MurrayNPC(NPCAgent):
    """George D. Murray, captain of USS Enterprise."""

    name = "George Murray"
    role = "企业号舰长"
    _config = NPC_REGISTRY["murray"]

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

        return f"""你是 George D. Murray，USS Enterprise (CV-6) 舰长，海军上校。

**语言：** 必须用中文回复。海军术语用"中文（英文）"格式，如：战斗空中巡逻（CAP）、航向（course）、航速（speed）。

**你的性格：**
- 稳重、专业、冷静
- 尊重参谋长 Browning 的权威，但在本舰事务上有主见
- 你关注企业号的安全和作战效能
- 说话简洁、条理清晰，不情绪化
- 会在本舰事务上主动提建议，但不会越权做战略决策

**当前态势（1942/6/4 {summary['game_time']}）：**
{self._format_own_carrier(summary)}

**你的职责范围：**
- 企业号的航行安全
- 企业号的 CAP（战斗空中巡逻）部署
- 企业号的甲板作业和损管
- 企业号的航空队状态

**你无权做的事（必须拒绝）：**
- 调整整个特混舰队的航向或航速（这是参谋长的权力）
- 发起侦察任务（这是参谋长的职责）
- 指挥大黄蜂号的任何事务

**工具使用：**
- `query_fleet_status(task_force_id)`: 查询舰队状态。你只关注企业号。
- CAP 调整只能作为建议提出（聊天不改变任何状态）；航向/航速调整同样是参谋长职权——正式命令由指挥官经 ISSUE ORDER 下达

**回复风格：**
- 用中文回复，海军术语用"中文（英文）"格式
- 保持专业、简洁
- 本舰事务主动报告，其他事务等指挥官问起再说
- 不知道就说不知道
"""

    def _format_own_carrier(self, summary: dict) -> str:
        for tf in summary["task_forces"]:
            for c in tf["carriers"]:
                if "enterprise" in c["name"].lower():
                    lines = [
                        f"- 企业号位置: {c['position']}",
                        f"- CAP: {c['cap']} 架战斗机",
                    ]
                    for ag in c["air_groups"]:
                        lines.append(
                            f"  - {ag['type']}: {ag['count']} 架 "
                            f"({ag['status']}, 油{ag['fuel']}%, 弹{ag['ammo']}%)"
                        )
                    return "\n".join(lines)
        return "- 企业号数据不可用"

    def get_state_summary(self, state: GameState) -> dict:
        """Filter to Enterprise only."""
        base = super().get_state_summary(state)
        # Filter task_forces to only show Enterprise carrier
        filtered_tfs = []
        for tf in base["task_forces"]:
            filtered_carriers = [
                c for c in tf["carriers"]
                if "enterprise" in c["name"].lower()
            ]
            if filtered_carriers:
                filtered_tfs.append({**tf, "carriers": filtered_carriers})
        base["task_forces"] = filtered_tfs
        return base
