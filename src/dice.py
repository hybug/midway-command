"""通用骰子系统 — 游戏规则引擎的核心。

任何需要"掷骰判定"的场景都通过 roll_check() 函数调用。
支持：五级结果、NPC 参数修正、情境修正、优势/劣势骰。
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
    base_modifier: int = 0,
    situational_mods: Optional[dict] = None,
    advantage: bool = False,
    disadvantage: bool = False,
) -> DiceResult:
    """通用骰子检定。

    Args:
        base_modifier: 基础修正值（来自NPC参数等）
        situational_mods: 情境修正字典，如 {"weather": -10, "distance": +5}
        advantage: 是否有优势（掷2次取高）
        disadvantage: 是否有劣势（掷2次取低）

    Returns:
        DiceResult 包含骰值、修正、结果等级
    """
    modifiers = []

    # 基础修正
    if base_modifier != 0:
        modifiers.append(f"基础修正: {base_modifier:+d}")

    # 情境修正
    total_situational = 0
    if situational_mods:
        for source, mod in situational_mods.items():
            if mod != 0:
                modifiers.append(f"{source}: {mod:+d}")
                total_situational += mod

    # 掷骰
    if advantage and not disadvantage:
        raw = _d100_advantage()
        modifiers.append("优势骰(2d100取高)")
    elif disadvantage and not advantage:
        raw = _d100_disadvantage()
        modifiers.append("劣势骰(2d100取低)")
    else:
        raw = _d100()

    # 计算最终值
    final = max(1, min(100, raw + base_modifier + total_situational))

    # 确定结果等级
    level, level_name = _determine_level(final)

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
    """使用 NPC 参数进行骰子检定"""
    base = int(npc_config.competence * 25)
    return roll_check(
        base_modifier=base,
        situational_mods=situational_mods,
        advantage=advantage,
        disadvantage=disadvantage,
    )


def roll_scout_check(npc_config, weather="clear", distance_nm=100, pattern="sector") -> DiceResult:
    """侦察检定专用函数"""
    # NPC修正
    base = int(npc_config.competence * 25)

    # 情境修正
    situational = {}

    # 天气修正
    if weather == "clear":
        situational["天气晴朗"] = 10
    elif weather == "cloudy":
        situational["天气多云"] = -5
    elif weather == "storm":
        situational["天气暴风雨"] = -20

    # 距离修正
    if distance_nm < 100:
        situational["近距离"] = 10
    elif distance_nm > 150:
        situational["远距离"] = -10

    # 搜索模式修正
    pattern_mods = {"sector": 5, "parallel": -5, "grid": 0}
    mod = pattern_mods.get(pattern, 0)
    if mod != 0:
        situational[f"搜索模式({pattern})"] = mod

    return roll_check(base_modifier=base, situational_mods=situational)


def roll_attack_check(npc_config, target_state="normal", distance_nm=80, weather="clear") -> DiceResult:
    """攻击检定专用函数"""
    base = int(npc_config.competence * 25)
    situational = {}

    # 目标状态修正
    if target_state == "rearming":
        situational["日舰换弹"] = 25
    elif target_state == "cap_active":
        situational["日舰CAP在位"] = -15

    # 距离修正
    if distance_nm < 50:
        situational["近距离"] = 5
    elif distance_nm > 100:
        situational["远距离"] = -10

    # 天气修正
    if weather == "storm":
        situational["天气恶劣"] = -10

    return roll_check(base_modifier=base, situational_mods=situational)


def roll_weather_check(region="pacific_june") -> DiceResult:
    """天气检定（无NPC修正）"""
    # 天气主要由区域和季节决定，骰子影响具体变化
    situational = {}
    if region == "pacific_june":
        situational["季节(夏季)"] = 5  # 夏季太平洋天气相对稳定

    return roll_check(base_modifier=0, situational_mods=situational)


def roll_landing_check(npc_config, weather="clear", fuel_pct=80, deck_clear=True) -> DiceResult:
    """着舰检定"""
    base = int(npc_config.competence * 25)
    situational = {}

    if weather == "storm":
        situational["天气恶劣"] = -15
    elif weather == "cloudy":
        situational["天气多云"] = -5

    if fuel_pct < 20:
        situational["燃油不足"] = -10
    elif fuel_pct < 10:
        situational["燃油危急"] = -20

    if not deck_clear:
        situational["甲板未清空"] = -15

    return roll_check(base_modifier=base, situational_mods=situational)
