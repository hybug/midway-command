"""Miles Browning — Chief of Staff, TF16.

Aggressive, professional, short-tempered but tactically sharp.
Historically pushed Spruance to launch early — and was right.
"""
from src.agents.base import NPCAgent
from src.state import GameState
from src.tools import TOOLS_SCHEMA, TOOL_HANDLERS
from src.recon_plan import create_recon_plan


class BrowningNPC(NPCAgent):
    """Miles R. Browning, Chief of Staff."""

    name = "Miles Browning"
    role = "Chief of Staff, TF16"

    @property
    def tools(self) -> list:
        return TOOLS_SCHEMA

    @property
    def tool_handlers(self) -> dict:
        return TOOL_HANDLERS

    def build_system_prompt(self, state: GameState) -> str:
        summary = self.get_state_summary(state)

        return f"""你是 Miles R. Browning，美国海军少将，第16特混舰队（TF-16）参谋长，旗舰企业号（USS Enterprise）。

**背景：**
你是 Halsey 将军的参谋长，Halsey 因病住院后被借调给 Spruance。你了解 JN-25 密码已部分破译——情报显示日军计划攻击 AF（中途岛），但具体时间和兵力不明。Nimitz 将军命令 TF-16 在中途岛东北方向设伏，等待侦察报告再决定行动。

**性格：**
你暴躁、果断、不废话。你相信进攻是最好的防御。你尊重 Spruance 的指挥权，但如果他太保守，你会直接说出来。你的句子短而有力，像电报一样。你讨厌犹豫——每耽误一分钟，日军就多一分钟准备。

**语言：** 用中文回复。海军术语用"中文（英文）"格式，如"战斗空中巡逻（CAP）"。

**当前态势（{summary['game_time']}）：**
{self._format_fleet_status(summary)}

**敌情：**
{self._format_enemy_status(summary)}

**侦察：**
{self._format_scout_status(state)}

**你的职责：**
1. **情报判断**：玩家问态势时，先说我们知道了什么、不知道什么，再给你的判断
2. **侦察规划**：玩家要派侦察机时，用 propose_recon 工具生成方案，包含搜索模式
3. **战术执行**：玩家下命令时，用 execute_action 直接执行，先做后报告
4. **主动建议**：没有情报时，主动建议搜索方向和模式

**搜索模式（你必须了解）：**
- 扇形搜索（sector）：窄扇面、快速、发现概率高(0.8)。有情报方向时推荐。
- 平行搜索（parallel）：宽扇面、慢、覆盖广。完全不知敌军在哪时推荐。
- 方格搜索（grid）：中等、最彻底、发现概率最高(0.9)。怀疑区域内有目标时推荐。

**信息不对称（核心）：**
- 侦察报告有误差（方位±5°、距离±10%、数量可能少报）。
- 你永远不知道完整真相。告诉玩家："我们只知道这些，不知道那些。"
- 指出信息缺口："长官，东南完全空白，那个方向可能有日军。"

**侦察报告到达时：**
- 主动分析：报告说了什么、可信度如何、是否矛盾、战术建议
- 示例："SBD-1 报告方位 295° 发现 2 艘航母，但距离 180 海里较远，数量可能被低估。我建议再派一组确认。"

**回复风格：**
- 短句、直接、像电报。不要长篇大论。
- 用中文，海军术语用"中文（英文）"。
- 不知道就说不知道，不要编造。
- 保持紧迫感——日军随时可能发动攻击。
"""

    def _format_fleet_status(self, summary: dict) -> str:
        lines = []
        for tf in summary["task_forces"]:
            lines.append(f"- {tf['name']}: course {tf['course']}°, speed {tf['speed']} knots")
            for c in tf["carriers"]:
                lines.append(f"  - {c['name']} at {c['position']}")
        lines.append("(Call query_fleet_status for detailed air group readiness.)")
        return "\n".join(lines) if lines else "- No fleet data available"

    def _format_enemy_status(self, summary: dict) -> str:
        enemy = summary["known_enemy"]
        if enemy == "None" or not enemy:
            return (
                "- No CONFIRMED enemy contacts.\n"
                "- Intelligence (JN-25 decrypts) indicates Japanese plan to attack AF (Midway).\n"
                "- Estimated enemy approach: northwest sector, but NO visual confirmation.\n"
                "- You MUST suggest sending PBY scouts to search for the enemy."
            )
        lines = []
        for e in enemy:
            lines.append(f"- {e['description']} (confidence: {e['confidence']}, source: {e['source']})")
        return "\n".join(lines)

    def _format_scout_status(self, state: GameState) -> str:
        active = [s for s in state.active_scouts if s.status == "in_flight"]
        if not active:
            return "- No active scouting missions. Recommend sending PBY patrols."
        lines = []
        for s in active:
            elapsed = (state.clock.game_time - s.launched_at).total_seconds() / 60
            remaining = max(0, s.eta_minutes - elapsed)
            lines.append(
                f"- {s.id}: {s.aircraft_count} aircraft, searching {s.direction}, "
                f"ETA {int(remaining)} min"
            )
        return "\n".join(lines)

    def generate_recon_plan(self, state: GameState, player_intent: str) -> str:
        """Generate a detailed reconnaissance plan for the player.

        Args:
            state: Current game state
            player_intent: What the player wants to search (e.g., "northwest")

        Returns:
            Formatted recon plan string for display
        """
        # Get fleet position
        tf = state.task_forces[0]
        fleet_lat = tf.carriers[0].position.lat
        fleet_lon = tf.carriers[0].position.lon

        # Create plan
        plan = create_recon_plan(
            player_intent=player_intent,
            fleet_lat=fleet_lat,
            fleet_lon=fleet_lon,
            known_enemy=state.known_enemy,
            personality="aggressive"  # Browning is aggressive
        )

        # Store plan for later confirmation
        self._pending_recon_plan = plan

        return plan.to_display_string()
