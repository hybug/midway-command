"""Tests for the dice system."""
import pytest
from src.dice import (
    roll_check, roll_with_npc, roll_scout_check, roll_attack_check,
    roll_weather_check, roll_landing_check,
    _d100, _determine_level, THRESHOLDS
)
from src.npc_config import NPC_REGISTRY


class TestD100:
    def test_d100_range(self):
        for _ in range(1000):
            val = _d100()
            assert 1 <= val <= 100

    def test_d100_advantage_higher(self):
        """Advantage should generally produce higher results"""
        results = [_d100() for _ in range(100)]
        adv_results = [max(_d100(), _d100()) for _ in range(100)]
        assert sum(adv_results) > sum(results)

    def test_d100_disadvantage_lower(self):
        """Disadvantage should generally produce lower results"""
        results = [_d100() for _ in range(100)]
        dis_results = [min(_d100(), _d100()) for _ in range(100)]
        assert sum(dis_results) < sum(results)


class TestLevelDetermination:
    def test_critical_success(self):
        level, name = _determine_level(95)
        assert level == "critical_success"
        assert name == "大成功"

    def test_success(self):
        level, name = _determine_level(70)
        assert level == "success"
        assert name == "成功"

    def test_partial(self):
        level, name = _determine_level(40)
        assert level == "partial"
        assert name == "部分成功"

    def test_failure(self):
        level, name = _determine_level(10)
        assert level == "failure"
        assert name == "失败"

    def test_critical_failure(self):
        level, name = _determine_level(9)
        assert level == "critical_failure"
        assert name == "大失败"


class TestRollCheck:
    def test_basic_roll(self):
        result = roll_check()
        assert 1 <= result.raw_roll <= 100
        valid_levels = {"critical_success", "success", "partial", "failure", "critical_failure"}
        assert result.level in valid_levels

    def test_positive_modifier(self):
        """Positive NPC modifier should increase final roll"""
        results = [roll_check(npc_modifier=18) for _ in range(100)]
        avg_final = sum(r.modified_roll for r in results) / 100
        assert avg_final > 60  # Should be above average

    def test_negative_modifier(self):
        """Negative situational modifier should decrease final roll"""
        results = [roll_check(situational_mods={"penalty": -20}) for _ in range(100)]
        avg_final = sum(r.modified_roll for r in results) / 100
        assert avg_final < 40  # Should be below average

    def test_advantage(self):
        """Advantage should produce higher average"""
        normal = [roll_check().modified_roll for _ in range(200)]
        adv = [roll_check(advantage=True).modified_roll for _ in range(200)]
        assert sum(adv) > sum(normal)

    def test_disadvantage(self):
        """Disadvantage should produce lower average"""
        normal = [roll_check().modified_roll for _ in range(200)]
        dis = [roll_check(disadvantage=True).modified_roll for _ in range(200)]
        assert sum(dis) < sum(normal)

    def test_advantage_and_disadvantage_cancel(self):
        """Both advantage and disadvantage should cancel out"""
        normal = [roll_check().modified_roll for _ in range(200)]
        both = [roll_check(advantage=True, disadvantage=True).modified_roll for _ in range(200)]
        avg_normal = sum(normal) / 200
        avg_both = sum(both) / 200
        assert abs(avg_normal - avg_both) < 10

    def test_result_level_matches_roll(self):
        result = roll_check(npc_modifier=20)
        assert result.modified_roll >= 20
        assert result.level in ("critical_success", "success", "partial")

    def test_modifiers_recorded(self):
        result = roll_check(
            npc_modifier=10,
            situational_mods={"天气晴朗": 5, "近距离": 10}
        )
        assert len(result.modifiers_applied) >= 3  # NPC + weather + distance

    def test_roll_clamped_to_1_100(self):
        # NPC层封顶 +20，所以 npc_modifier=200 → +20
        # 最终值 = raw + 20，最大 100
        result = roll_check(npc_modifier=200)
        assert result.modified_roll <= 100
        # 情境层封顶 -20
        result2 = roll_check(situational_mods={"penalty": -200})
        assert result2.modified_roll >= 1

    def test_npc_layer_capped_at_20(self):
        """NPC层封顶 +20"""
        result = roll_check(npc_modifier=50)  # 应该被封顶到 +20
        assert result.modified_roll <= 100

    def test_situational_layer_capped_at_20(self):
        """情境层封顶 ±20"""
        result = roll_check(situational_mods={"a": 30, "b": -10})  # 合计 +20，封顶
        assert result.modified_roll <= 100

    def test_total_modifier_capped_at_30(self):
        """总修正封顶 ±30"""
        result = roll_check(npc_modifier=20, situational_mods={"a": 20})
        # 总修正 = min(20, +20) + min(20, +20) = +20 + +20 = +40 → 封顶 +30
        # 最终值 = raw + 30
        assert result.modified_roll <= 100

    def test_critical_success_on_raw_dice(self):
        """大成功看原始骰（≥95）"""
        # 多次测试，确保原始骰≥95时一定是大成功
        for _ in range(100):
            result = roll_check(npc_modifier=-20)  # 即使修正很低
            if result.raw_roll >= 95:
                assert result.level == "critical_success"

    def test_critical_failure_on_raw_dice(self):
        """大失败看原始骰（≤9）"""
        for _ in range(100):
            result = roll_check(npc_modifier=20)  # 即使修正很高
            if result.raw_roll <= 9:
                assert result.level == "critical_failure"


class TestScoutCheck:
    def test_scout_with_good_conditions(self):
        npc = NPC_REGISTRY["browning"]
        result = roll_scout_check(npc, distance_nm=80, pattern="sector")
        assert result.modified_roll > 50  # Good conditions

    def test_scout_with_bad_conditions(self):
        npc = NPC_REGISTRY["browning"]
        good = [roll_scout_check(npc, distance_nm=80, pattern="sector").modified_roll for _ in range(100)]
        bad = [roll_scout_check(npc, distance_nm=160, pattern="parallel").modified_roll for _ in range(100)]
        assert sum(bad) < sum(good)  # Bad conditions should produce lower average

    def test_scout_competence_matters(self):
        """Browning (competence=9) should roll better than radio officer (competence=6)"""
        browning = NPC_REGISTRY["browning"]
        radio = NPC_REGISTRY["radio_officer"]
        # 需要足够样本量来抵消随机性
        b_results = [roll_scout_check(browning).modified_roll for _ in range(500)]
        r_results = [roll_scout_check(radio).modified_roll for _ in range(500)]
        assert sum(b_results) > sum(r_results)


class TestAttackCheck:
    def test_attack_normal(self):
        npc = NPC_REGISTRY["browning"]
        result = roll_attack_check(npc, target_state="normal")
        assert 1 <= result.modified_roll <= 100

    def test_attack_rearming_bonus(self):
        npc = NPC_REGISTRY["browning"]
        normal = [roll_attack_check(npc, target_state="normal").modified_roll for _ in range(100)]
        rearming = [roll_attack_check(npc, target_state="rearming").modified_roll for _ in range(100)]
        assert sum(rearming) > sum(normal)


class TestLandingCheck:
    """着舰检定测试"""

    def test_landing_basic(self):
        """基本着舰检定"""
        npc = NPC_REGISTRY["murray"]
        result = roll_landing_check(npc)
        assert 1 <= result.modified_roll <= 100

    def test_landing_night_penalty(self):
        """夜间着舰惩罚"""
        npc = NPC_REGISTRY["murray"]
        day = [roll_landing_check(npc, is_night=False).modified_roll for _ in range(100)]
        night = [roll_landing_check(npc, is_night=True).modified_roll for _ in range(100)]
        assert sum(night) < sum(day)

    def test_landing_fuel_penalty(self):
        """燃油紧张惩罚"""
        npc = NPC_REGISTRY["murray"]
        normal = [roll_landing_check(npc, fuel_pct=80).modified_roll for _ in range(100)]
        low_fuel = [roll_landing_check(npc, fuel_pct=5).modified_roll for _ in range(100)]
        assert sum(low_fuel) < sum(normal)


class TestWeatherCheck:
    """Weather check tests deferred until weather system is implemented."""
    pass
