"""可复现 RNG 服务与 CheckRecord（Phase S2.1）。

设计（s2-intelligence-system-plan.md §九）：
- 游戏级种子：GameState.rng_seed；每次抽取种子 = f"{rng_seed}:{已有记录数}"，
  每次抽取恰好追加一条 CheckRecord ⇒ 同一起始状态 + 同一操作序列 ⇒
  完全一致的抽取序列（可回放，不依赖全局随机状态）。
- 检定型抽取走 src.dice 三层架构（原始骰可注入骰源），结果落 CheckRecord。
- 通用抽取（randint/chance/uniform）同样落 CheckRecord——不得使用未记录的
  random 决定游戏结果。
- LLM 不重算骰子结果；系统提供结构化输出（JudgmentDice 由 S2.3 消费）。
"""
import random
from datetime import datetime
from typing import Callable, Optional

from pydantic import BaseModel, Field

from src.intel.contracts import CheckType


class CheckRecord(BaseModel):
    """单次检定/抽取记录（计划 §6.10）。

    每条记录都能回答：谁（actor_id）在何时（game_time）为什么（context.reason）
    基于什么输入（context/inputs）掷了什么（random_seed/raw_roll/raw_rolls）、
    修正如何（modifiers）、结果几级（degree/final_roll）、产生了什么效果（effects）。
    """
    check_id: str
    check_type: str                     # CheckType 值或 "raw_draw"
    actor_id: str
    game_time: datetime
    random_seed: str
    raw_roll: Optional[int] = None      # d100 型检定的原始骰
    # 全部原始抽取（chance/uniform 为浮点；含优劣势双骰）
    raw_rolls: list[float] = Field(default_factory=list)
    modifiers: dict = Field(default_factory=dict)
    final_roll: Optional[int] = None
    degree: Optional[str] = None        # 五级结果等级（检定型抽取）
    effects: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)


class _SeededRng:
    """单次抽取会话：包装 random.Random 并记录全部原始抽取值。"""

    def __init__(self, seed: str):
        self._r = random.Random(seed)
        self.draws: list[int] = []

    def randint(self, a: int, b: int) -> int:
        v = self._r.randint(a, b)
        self.draws.append(v)
        return v

    def random(self) -> float:
        v = self._r.random()
        self.draws.append(round(v, 6))
        return v

    def uniform(self, a: float, b: float) -> float:
        v = self._r.uniform(a, b)
        self.draws.append(round(v, 6))
        return v


class RNGService:
    """绑定 GameState 的可复现随机源（薄视图：种子与记录存于 state）。"""

    def __init__(self, state):
        self._state = state

    # ── 内部 ──

    def _next_seed(self) -> str:
        return f"{self._state.rng_seed}:{len(self._state.check_records)}"

    def _record(
        self,
        *,
        check_type: str,
        actor_id: str,
        seed: str,
        rng: _SeededRng,
        reason: str,
        inputs: Optional[dict] = None,
        effects: Optional[dict] = None,
        result=None,
    ) -> CheckRecord:
        rec = CheckRecord(
            check_id=f"chk_{len(self._state.check_records) + 1:06d}",
            check_type=check_type,
            actor_id=actor_id,
            game_time=self._state.clock.game_time,
            random_seed=seed,
            raw_rolls=list(rng.draws),
            context={"reason": reason, **(inputs or {})},
            effects=effects or {},
        )
        if result is not None:
            rec.raw_roll = result.raw_roll
            rec.final_roll = result.modified_roll
            rec.degree = result.level
            rec.modifiers = {"applied": list(result.modifiers_applied)}
        self._state.check_records.append(rec)
        return rec

    # ── 通用抽取（记录型）──

    def randint(
        self, check_type: CheckType | str, actor_id: str, low: int, high: int,
        reason: str, inputs: Optional[dict] = None, effects: Optional[dict] = None,
    ) -> int:
        seed = self._next_seed()
        rng = _SeededRng(seed)
        value = rng.randint(low, high)
        self._record(
            check_type=str(check_type.value if hasattr(check_type, "value") else check_type),
            actor_id=actor_id, seed=seed, rng=rng, reason=reason,
            inputs={"low": low, "high": high, **(inputs or {})},
            effects={**(effects or {}), "value": value},
        )
        return value

    def chance(
        self, check_type: CheckType | str, actor_id: str, prob: float,
        reason: str, inputs: Optional[dict] = None,
    ) -> bool:
        seed = self._next_seed()
        rng = _SeededRng(seed)
        roll = rng.random()
        hit = roll < prob
        self._record(
            check_type=str(check_type.value if hasattr(check_type, "value") else check_type),
            actor_id=actor_id, seed=seed, rng=rng, reason=reason,
            inputs={"prob": prob, **(inputs or {})},
            effects={"roll": round(roll, 6), "hit": hit},
        )
        return hit

    # ── 检定型抽取（d100 + 三层修正，走 src.dice）──

    def roll_check(
        self,
        check_type: CheckType,
        actor_id: str,
        npc_modifier: int = 0,
        situational_mods: Optional[dict] = None,
        advantage: bool = False,
        disadvantage: bool = False,
        reason: str = "",
        inputs: Optional[dict] = None,
        effects_builder: Optional[Callable] = None,
    ):
        """检定并落 CheckRecord。返回 (DiceResult, CheckRecord)。"""
        seed = self._next_seed()
        rng = _SeededRng(seed)
        result = _roll_with_roller(
            npc_modifier=npc_modifier,
            situational_mods=situational_mods,
            advantage=advantage,
            disadvantage=disadvantage,
            roller=lambda: rng.randint(1, 100),
        )
        effects = effects_builder(result) if effects_builder else {}
        rec = self._record(
            check_type=check_type.value, actor_id=actor_id, seed=seed, rng=rng,
            reason=reason, inputs=inputs, effects=effects, result=result,
        )
        return result, rec

    def detection_check(
        self, unit, distance_nm: float, pattern: str,
        reason: str = "", inputs: Optional[dict] = None,
    ):
        """侦察检定：使用实际执行单位能力（骰子缺口 #3 修复）。"""
        from src.dice import scout_situational_mods
        return self.roll_check(
            check_type=CheckType.DETECTION_CHECK,
            actor_id=unit.name,
            npc_modifier=unit.competence * 2,
            situational_mods=scout_situational_mods(distance_nm, pattern),
            reason=reason or "侦察检定",
            inputs={"distance_nm": round(distance_nm, 1), "pattern": pattern,
                    **(inputs or {})},
        )

    def communication_check(
        self, actor_id: str, competence: int, distance_nm: float,
        reason: str = "", inputs: Optional[dict] = None,
    ):
        """通信检定（S2.3 起接入延迟与完整性效果）。"""
        situational = {}
        if distance_nm > 150:
            situational["远距离通信"] = -5
        return self.roll_check(
            check_type=CheckType.COMMUNICATION_CHECK,
            actor_id=actor_id,
            npc_modifier=competence * 2,
            situational_mods=situational,
            reason=reason or "通信检定",
            inputs={"distance_nm": round(distance_nm, 1), **(inputs or {})},
        )


def _roll_with_roller(npc_modifier, situational_mods, advantage, disadvantage, roller):
    """以注入骰源执行 src.dice.roll_check（保持三层修正管线一致）。"""
    from src.dice import roll_check as dice_roll_check
    return dice_roll_check(
        npc_modifier=npc_modifier,
        situational_mods=situational_mods,
        advantage=advantage,
        disadvantage=disadvantage,
        raw_roller=roller,
    )
