"""S2 纵切内置判断策略（Phase S2.3）。

MechanicalPolicy 是 JudgmentPolicy 的机械实现：只做「证据维度 + 骰子误差」
的确定性组合，供测试与无 LLM 降级环境使用。**正式玩法必须由 S3 的
JudgmentPolicy（公式/消融/历史校准）+ LLM 参谋产生判断**——系统不能后台
替代参谋形成结论（D12/D15），机械实现不构成玩法路径。

JudgmentDice 的误差映射（S2 约定，S3 可调整公式但不得绕过骰子）：
- critical_success：无偏差，表达确定性 0.95
- success：轻微偏差（severity 0.1）
- partial：中等偏差（0.3），方向由骰子二次抽取
- failure：严重偏差（0.6）
- critical_failure：严重偏差（0.9）+ 高表达确定性（过度自信——可归因错误）
"""
import random

from src.intel.contracts import ActorRole
from src.intel.judgment import (
    ActorProfile,
    AssessmentDraft,
    EvidenceView,
    JudgmentDice,
    JudgmentPolicy,
)

_SEVERITY = {
    "critical_success": 0.0,
    "success": 0.1,
    "partial": 0.3,
    "failure": 0.6,
    "critical_failure": 0.9,
}

_CERTAINTY = {
    "critical_success": 0.95,
    "success": 0.8,
    "partial": 0.6,
    "failure": 0.5,
    "critical_failure": 0.85,   # 大失败伴随过度自信（历史教训：Browning 乐观）
}


def roll_judgment_dice(rng, *, actor_id: str, level: str,
                       record_id: str) -> JudgmentDice:
    """由骰子结果构造 JudgmentDice（方向由二次抽取决定，全部走记录）。"""
    severity = _SEVERITY.get(level, 0.3)
    direction = None
    if severity > 0:
        pick = rng.randint(
            "raw_draw", actor_id, 0, 2,
            reason="判断偏差方向抽取", inputs={"level": level},
        )
        direction = ["overestimate", "bearing_offset", "underestimate"][pick]
    return JudgmentDice(
        record_id=record_id,
        level=level,
        error_direction=direction,
        error_severity=severity,
        express_certainty=_CERTAINTY.get(level, 0.6),
    )


class MechanicalPolicy:
    """JudgmentPolicy 的机械实现（测试/降级用，非玩法路径）。"""

    def assess(self, work_item, evidence: list[EvidenceView],
               actor: ActorProfile, dice: JudgmentDice) -> AssessmentDraft:
        draft = AssessmentDraft()
        contacts = [e for e in evidence if e.dimensions.get("count_precision", 0) >= 0]
        for ev in contacts:
            # 位置沿误差方向平移（机械规则：severity × 30nm 置信半径）
            shift_nm = dice.error_severity * 30
            confidence = max(0.05, 1.0 - dice.error_severity)
            draft.claims.append({
                "kind": "contact",
                "source_evidence_id": ev.evidence_id,
                "summary": ev.summary,
                "position_radius_nm": 20 + shift_nm,
                "count_estimate": ev.dimensions.get("count_precision", 0.5),
            })
            draft.confidence_dimensions["position"] = confidence
            draft.confidence_dimensions["identity"] = max(
                0.05, (ev.source_reliability or 0.6) - dice.error_severity * 0.5
            )
            draft.confidence_dimensions["freshness"] = 0.9
        if dice.error_direction == "overestimate" and draft.claims:
            draft.alternative_hypotheses.append({
                "hypothesis": "敌方兵力可能被高估——单机远程识别不可靠",
                "trigger": "获得第二来源印证前，把数量估计下调一档",
            })
        draft.change_my_mind.append("收到第二份独立接触报告或勘误电报时重新研判")
        draft.recommended_action = "继续保持搜索压力，等待印证后再请求打击规划"
        draft.notes = f"机械策略产物（dice={dice.record_id}, level={dice.level}）"
        return draft


DEFAULT_POLICY = MechanicalPolicy()
DEFAULT_ACTOR = ActorProfile(actor_id="intel_officer", role="情报参谋",
                             attributes={"competence": 7})
DEFAULT_ROLE = ActorRole.INTEL_OFFICER
