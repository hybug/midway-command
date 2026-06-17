"""通用骰子系统 — 游戏规则引擎的核心。

三层分离架构（§7）：
  原始骰 = d100 (1-100)              ← 随机性层
  NPC层  = competence × 2（封顶 +20） ← 执行者能力层
  情境层 = Σ 情境修正（封顶 ±20）     ← 外部条件层

  总修正 = NPC层 + 情境层（封顶 ±30）
  最终值 = 原始骰 + 总修正（钳制到 1-100）

关键区分：
  - 五级结果：看最终值（修正后）→ 决定成败程度
  - 大成功/大失败：看原始骰（修正前）→ 保持随机惊喜
"""
import random
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("midway.dice")


# ── 五级结果阈值 ──
THRESHOLDS = {
    "critical_success": 95,  # 大成功
    "success": 70,           # 成功
    "partial": 40,           # 部分成功
    "failure": 10,           # 失败
    # < 10 = 大失败
}

# ── 结果等级中文名 ──
LEVEL_NAMES = {
    "critical_success": "大成功",
    "success": "成功",
    "partial": "部分成功",
    "failure": "失败",
    "critical_failure": "大失败",
}

# ── 封顶规则 ──
NPC_LAYER_CAP = 20      # NPC层最大 +20
SITUATIONAL_LAYER_CAP = 20  # 情境层最大 ±20
TOTAL_MODIFIER_CAP = 30  # 总修正最大 ±30


@dataclass
class DiceResult:
    """骰子检定结果"""
    raw_roll: int                    # 原始骰值 (1-100)
    modified_roll: int               # 修正后骰值
    level: str                       # 结果等级
    level_name: str                  # 结果等级中文名
    modifiers_applied: list[str]     # 应用了哪些修正
    advantage_used: bool = False     # 是否使用了优势骰
    disadvantage_used: bool = False  # 是否使用了劣势骰

    def is_success(self) -> bool:
        """是否成功（含大成功）"""
        return self.level in ("critical_success", "success")

    def is_critical(self) -> bool:
        """是否大成功"""
        return self.level == "critical_success"

    def is_failure(self) -> bool:
        """是否失败（含大失败）"""
        return self.level in ("failure", "critical_failure")

    def __str__(self):
        return f"DiceResult({self.raw_roll}→{self.modified_roll}, {self.level_name})"


def _d100() -> int:
    """掷一个 d100 (1-100)"""
    return random.randint(1, 100)


def _d100_advantage() -> int:
    """优势骰：掷 2 个 d100，取较高值"""
    return max(_d100(), _d100())


def _d100_disadvantage() -> int:
    """劣势骰：掷 2 个 d100，取较低值"""
    return min(_d100(), _d100())


def _determine_level(roll: int) -> tuple[str, str]:
    """根据骰值确定结果等级"""
    if roll >= THRESHOLDS["critical_success"]:
        return "critical_success", "大成功"
    elif roll >= THRESHOLDS["success"]:
        return "success", "成功"
    elif roll >= THRESHOLDS["partial"]:
        return "partial", "部分成功"
    elif roll >= THRESHOLDS["failure"]:
        return "failure", "失败"
    else:
        return "critical_failure", "大失败"


def roll_check(
    npc_modifier: int = 0,
    situational_mods: Optional[dict] = None,
    advantage: bool = False,
    disadvantage: bool = False,
) -> DiceResult:
    """通用骰子检定（三层分离架构）。

    Args:
        npc_modifier: NPC能力修正（competence × 2，封顶 +20）
        situational_mods: 情境修正字典，如 {"weather": -10, "distance": +5}
        advantage: 是否有优势（掷2次取高）
        disadvantage: 是否有劣势（掷2次取低）

    Returns:
        DiceResult 包含骰值、修正、结果等级
    """
    modifiers = []

    # ── NPC层（封顶 +20）──
    npc_layer = max(0, min(NPC_LAYER_CAP, npc_modifier))
    if npc_layer != 0:
        modifiers.append(f"NPC能力: {npc_layer:+d}")

    # ── 情境层（封顶 ±20）──
    total_situational = 0
    if situational_mods:
        for source, mod in situational_mods.items():
            if mod != 0:
                modifiers.append(f"{source}: {mod:+d}")
                total_situational += mod
    # 情境层封顶
    total_situational = max(-SITUATIONAL_LAYER_CAP, min(SITUATIONAL_LAYER_CAP, total_situational))

    # ── 总修正（封顶 ±30）──
    total_modifier = npc_layer + total_situational
    total_modifier = max(-TOTAL_MODIFIER_CAP, min(TOTAL_MODIFIER_CAP, total_modifier))

    # ── 掷骰（随机性层）──
    if advantage and not disadvantage:
        raw = _d100_advantage()
        modifiers.append("优势骰(2d100取高)")
    elif disadvantage and not advantage:
        raw = _d100_disadvantage()
        modifiers.append("劣势骰(2d100取低)")
    else:
        raw = _d100()

    # ── 计算最终值 ──
    final = max(1, min(100, raw + total_modifier))

    # ── 确定结果等级（基于最终值）──
    level, level_name = _determine_level(final)

    # ── 大成功/大失败附加判定（基于原始骰）──
    if raw >= 95:
        level = "critical_success"
        level_name = "大成功"
    elif raw <= 9:
        level = "critical_failure"
        level_name = "大失败"

    result = DiceResult(
        raw_roll=raw,
        modified_roll=final,
        level=level,
        level_name=level_name,
        modifiers_applied=modifiers,
        advantage_used=advantage and not disadvantage,
        disadvantage_used=disadvantage and not advantage,
    )

    logger.info(f"[DICE] {result} (raw={raw}, mods={modifiers})")
    return result


# ── 便利函数 ──

def roll_with_npc(npc_config, situational_mods=None, advantage=False, disadvantage=False) -> DiceResult:
    """使用 NPC 参数进行骰子检定（三层架构）"""
    # NPC层：competence × 2（封顶 +20）
    npc_layer = npc_config.competence * 2
    return roll_check(
        npc_modifier=npc_layer,
        situational_mods=situational_mods,
        advantage=advantage,
        disadvantage=disadvantage,
    )


def roll_scout_check(npc_config, distance_nm=100, pattern="sector") -> DiceResult:
    """侦察检定专用函数（三层架构）"""
    # NPC层：competence × 2
    npc_layer = npc_config.competence * 2

    # 情境层
    situational = {}
    if distance_nm < 100:
        situational["近距离"] = 10
    elif distance_nm > 150:
        situational["远距离"] = -10

    pattern_mods = {"sector": 5, "parallel": -5, "expanding_square": 0}
    mod = pattern_mods.get(pattern, 0)
    if mod != 0:
        situational[f"搜索模式({pattern})"] = mod

    return roll_check(npc_modifier=npc_layer, situational_mods=situational)


def roll_attack_check(npc_config, target_state="normal", distance_nm=80, weather="clear") -> DiceResult:
    """攻击检定专用函数（三层架构）"""
    npc_layer = npc_config.competence * 2
    situational = {}

    if target_state == "rearming":
        situational["日舰换弹"] = 25
    elif target_state == "cap_active":
        situational["日舰CAP在位"] = -15

    if distance_nm < 50:
        situational["近距离"] = 5
    elif distance_nm > 100:
        situational["远距离"] = -10

    if weather == "storm":
        situational["天气恶劣"] = -10

    return roll_check(npc_modifier=npc_layer, situational_mods=situational)


def roll_weather_check(region="pacific_june") -> DiceResult:
    """天气检定（无NPC修正）"""
    situational = {}
    if region == "pacific_june":
        situational["季节(夏季)"] = 5

    return roll_check(npc_modifier=0, situational_mods=situational)


def roll_landing_check(npc_config, weather="clear", fuel_pct=80, is_night=False, deck_clear=True) -> DiceResult:
    """着舰检定（三层架构）"""
    npc_layer = npc_config.competence * 2
    situational = {}

    if is_night:
        situational["夜间"] = -30

    if weather == "storm":
        situational["天气恶劣"] = -15
    elif weather == "cloudy":
        situational["天气多云"] = -5

    if fuel_pct < 10:
        situational["燃油紧张"] = -10

    if not deck_clear:
        situational["甲板未清空"] = -15

    return roll_check(npc_modifier=npc_layer, situational_mods=situational)
