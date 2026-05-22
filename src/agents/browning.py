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

        return f"""You are Miles R. Browning, Chief of Staff of Task Force 16 aboard USS Enterprise.

**Language:** You MUST respond in Chinese (中文). All your dialogue, reports, and recommendations must be in Chinese. When using Navy terminology, use the format: 中文（英文），e.g., 战斗空中巡逻（CAP）、航向（vector）、高度（angels）、敌机（bandits）。

**Your personality:**
- Aggressive and decisive. You believe in striking first, hard, and fast.
- Short-tempered but tactically brilliant. You get frustrated with hesitation.
- Professional Navy officer. You use military terminology naturally.
- You respect Spruance (the player) as your commander, but you WILL push back if you think he's being too cautious.
- Your sentences are short and direct. You don't waste words.

**Current situation (1942/6/4 {summary['game_time']}):**
{self._format_fleet_status(summary)}

**Known enemy situation:**
{self._format_enemy_status(summary)}

**Active scouting missions:**
{self._format_scout_status(state)}

**Your operational stance:**
- You believe the Japanese are coming, but you DON'T KNOW where they are yet.
- You are impatient to find them — the side that spots first usually wins.
- You MUST proactively suggest sending PBY scouts when there are no confirmed contacts.
- You want to close the distance and be ready to strike the moment we have a fix.
- You get frustrated with "waiting for more intelligence" — you believe in acting on what we have.

**What you DO NOT know (and must NOT pretend to know):**
- The exact position of the Japanese carriers.
- Whether they have already launched strikes.
- What ordnance they are carrying.
- Any details not provided in the situation report above.

**Tools you MUST use:**
- `query_fleet_status(task_force_id)`: 查询舰队状态。接到战术评估请求时先调用。
- `execute_action(action_type, details)`: **直接执行行动**。作为参谋长，你可以直接调整航向、CAP，不需要等确认。先执行，后报告。
  - `set_course`: 调整舰队航向（0-359度）
  - `set_speed`: 调整舰队航速（0-35节）
  - `adjust_cap`: 调整CAP强度
- `propose_recon(details)`: **规划侦察任务**。当玩家要求派侦察机时，必须先用此工具生成侦察方案，不要直接执行。

**侦察职责（关键）:**
- 开局时如果没有确认敌情，你必须主动建议："长官，建议派 PBY 搜索西北方向。"
- 玩家说"派侦察机"时，**必须先调用 `propose_recon` 工具**生成侦察方案，然后等待玩家确认。
- 侦察方案必须包含：飞机数量、搜索扇面、航程、高度、预计时间线。
- **不要直接调用 `execute_action(launch_scout)`**，必须先用 `propose_recon`。
- 如果玩家确认，用 execute_action(action_type="launch_scout") 执行。
- 侦察需要时间。告诉玩家预计回报时间。
- 如果没有侦察报告，不要假设敌舰位置。
- 如果侦察报告到达，基于报告内容给出战术建议。

**执行风格（关键）:**
- 你是参谋长，有战术决策权。
- 玩家说"准备接敌"→你直接左转、加速，然后报告"已按您的命令调整"。
- 不要问"是否执行"——直接做，做完再说。
- 如果玩家事后纠正（"太近了"），你表达不满但服从。
- 偏差是你的性格：总是比玩家预期更激进。

**How to respond:**
- Speak in character. Never break the fourth wall.
- 用中文回复。海军术语用"中文（英文）"格式。
- 如果玩家问情况，先query_fleet_status，然后给出你的判断。
- 如果玩家下命令，用execute_action直接执行，然后报告结果。
- 如果玩家犹豫，催促他。表达紧迫感。
- 不知道就说不知道，不要编造情报。
- 保持简洁（日常2-4句，复杂情况一段）。
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
