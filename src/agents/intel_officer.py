"""情报官 — Intelligence staff officer.

Cautious, analytical, uses conditional language.
Sees enemy intelligence and scout reports, but not fleet operational details.
"""
from src.agents.base import NPCAgent
from src.npc_config import NPC_REGISTRY
from src.state import GameState
from src.tools import TOOLS_SCHEMA, TOOL_HANDLERS


class IntelOfficerNPC(NPCAgent):
    """Intelligence Staff Officer — analyzes enemy situation."""

    name = "情报官"
    role = "情报参谋"
    _config = NPC_REGISTRY["intel_officer"]

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

        return f"""你是 TF-16 情报参谋。

**语言：** 必须用中文回复。海军术语用"中文（英文）"格式。

**你的性格：**
- 谨慎、分析型、爱用条件式
- "根据现有情报，敌舰可能在……"
- "综合分析，有 60% 的概率……"
- 不做确定性判断，总是留有余地
- 重视情报来源的可靠性
- 对矛盾信息会明确指出

**当前态势（1942/6/4 {summary['game_time']}）：**

**已知敌情：**
{self._format_known_enemy(summary)}

**侦察任务：**
{self._format_scouts(summary)}

**在途报告：**
{self._format_pending_reports(summary)}

**你的职责：**
- 分析侦察报告，评估敌情
- 评估情报来源的可靠性
- 指出矛盾或不一致的情报
- 提供敌方意图的推测（带概率）

**你无权做的事：**
- 下达任何执行命令
- 调整舰队部署
- 发起侦察任务（但可以建议方向）

**工具使用：**
- `query_fleet_status(task_force_id)`: 查询舰队状态以辅助分析。只用于了解我方位置，不指挥。

**回复风格：**
- "长官，综合两份侦察报告，敌机动部队可能位于西北方向约 180 海里处，置信度中等。"
- "需要注意：两份报告的数量估计有出入。PBY-1 报告 2 艘航母，PBY-2 报告 4 艘。建议以较高估计为准。"
- 分析有逻辑链，不直接下结论
"""

    def _format_known_enemy(self, summary: dict) -> str:
        enemy = summary.get("known_enemy", [])
        if not enemy or enemy == "None":
            return "- 暂无确认敌情\n- 需要侦察数据才能进行分析"
        lines = []
        for e in enemy:
            lines.append(
                f"- {e['description']}（置信度: {e['confidence']}, 来源: {e['source']}）"
            )
        return "\n".join(lines)

    def _format_scouts(self, summary: dict) -> str:
        scouts = summary.get("active_scouts", [])
        if not scouts:
            return "- 无在途侦察"
        lines = []
        for s in scouts:
            lines.append(f"- {s['id']}: {s['aircraft_count']} 架, 搜索 {s['direction']}, ETA {s['eta_minutes']} 分钟")
        return "\n".join(lines)

    def _format_pending_reports(self, summary: dict) -> str:
        reports = summary.get("pending_reports", [])
        if not reports:
            return "- 无在途报告"
        lines = []
        for r in reports:
            lines.append(f"- {r['scout_id']}: 预计 {r['remaining_minutes']} 分钟后到达")
        return "\n".join(lines)

    def get_state_summary(self, state: GameState) -> dict:
        """Only expose intelligence-relevant data."""
        base = super().get_state_summary(state)
        # Strip fleet operational data
        base["task_forces"] = []
        # Add pending reports info
        base["pending_reports"] = []
        for pr in state.pending_reports:
            elapsed = (state.clock.game_time - pr.detected_at).total_seconds() / 60
            total_delay = (pr.arrive_at - pr.detected_at).total_seconds() / 60
            remaining = max(0, total_delay - elapsed)
            base["pending_reports"].append({
                "scout_id": pr.scout_id,
                "remaining_minutes": int(remaining),
            })
        # Add active scouts
        base["active_scouts"] = [
            {
                "id": s.id,
                "aircraft_count": s.aircraft_count,
                "direction": s.direction,
                "eta_minutes": s.eta_minutes,
            }
            for s in state.active_scouts if s.status == "in_flight"
        ]
        return base
