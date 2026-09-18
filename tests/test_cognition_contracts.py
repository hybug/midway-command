"""S3.0 认知契约测试（红灯先行）。

验收（s3-staff-cognition-system-plan.md Phase S3.0）：
- 建模测试全绿：ActorProfile / JudgmentTask / Hypothesis / JudgmentResult /
  JudgmentMemory / JudgmentAuditRecord 六模型 schema 与边界
- 稳定判断键：同输入同键、证据集变化换键
- JudgmentEngine 接口存在且 runtime 可检
- 珊瑚海名册（Fletcher 玩家 + Fitch + 情报参谋 + 作战参谋）与角色证据权限；
  名册与可见信息不含 actual_enemy
- 中途岛现有 NPC 不回归（MechanicalPolicy 仍为 S2 默认）
"""
from datetime import datetime, timezone

import pytest

from src.intel.contracts import ActorRole
from src.intel.judgment import EvidenceView
from src.intel.policy import DEFAULT_POLICY, MechanicalPolicy
from src.state import GameState


# ── 契约层 ──

def test_task_type_enum_covers_five_task_kinds():
    from src.cognition.contracts import TaskType
    assert {t.value for t in TaskType} == {
        "assess", "predict", "recommend", "compare", "decide",
    }


def test_confidence_band_is_three_tier():
    from src.cognition.contracts import ConfidenceBand
    assert {b.value for b in ConfidenceBand} == {"low", "medium", "high"}


def test_error_type_covers_dimensions_and_none():
    from src.cognition.contracts import ErrorType
    assert {e.value for e in ErrorType} == {
        "none", "identity", "count", "position", "course", "speed",
    }


# ── 模型层 ──

def _profile(**overrides):
    from src.cognition.models import ActorProfile
    data = dict(
        actor_id="tf17_intel",
        role="TF17 情报参谋",
        domain="intelligence",
        attributes={
            "competence": 6, "risk_tolerance": 3, "imagination": 3,
            "initiative": 4, "autonomy": 3,
        },
        profile_version="coral-sea-v1",
        persona_prompt_ref="cognition/personas/tf17_intel.md",
    )
    data.update(overrides)
    return ActorProfile(**data)


def test_actor_profile_five_active_dimensions_validated():
    p = _profile()
    assert p.attributes["competence"] == 6
    with pytest.raises(ValueError):
        _profile(attributes={**p.attributes, "competence": 11})
    with pytest.raises(ValueError):
        _profile(attributes={**p.attributes, "risk_tolerance": -1})


def test_actor_profile_requires_all_five_active_dimensions():
    from src.cognition.models import ActorProfile
    with pytest.raises(ValueError):
        ActorProfile(actor_id="x", attributes={"competence": 5})


def test_judgment_task_stable_key_stable_and_sensitive():
    from src.cognition.contracts import compute_stable_key
    from src.cognition.models import JudgmentTask
    t1 = JudgmentTask(
        task_type="assess", domain="intelligence", actor_id="tf17_intel",
        question="这份米西马方向接触报告是否足以支持立即放飞全力攻击？",
        evidence_ids=["EV-000001", "EV-000002"], context_version=1,
    )
    t2 = JudgmentTask(
        task_type="assess", domain="intelligence", actor_id="tf17_intel",
        question="这份米西马方向接触报告是否足以支持立即放飞全力攻击？",
        evidence_ids=["EV-000002", "EV-000001"], context_version=1,
    )
    t3 = JudgmentTask(
        task_type="assess", domain="intelligence", actor_id="tf17_intel",
        question="同一问题", evidence_ids=["EV-000001"], context_version=2,
    )
    assert t1.stable_key and t1.stable_key == t2.stable_key  # 证据顺序无关
    assert t3.stable_key != t1.stable_key                    # 证据集/上下文变化换键
    # compute_stable_key 纯函数与模型字段计算一致
    assert compute_stable_key(
        actor_id=t1.actor_id, task_type=t1.task_type, domain=t1.domain,
        question_normalized=t1.question_normalized,
        evidence_ids=t1.evidence_ids, context_version=t1.context_version,
    ) == t1.stable_key


def test_judgment_task_question_normalized_strips_whitespace():
    from src.cognition.models import JudgmentTask
    t = JudgmentTask(
        task_type="assess", domain="intelligence", actor_id="a",
        question="  报告是否可靠？  ", evidence_ids=["EV-000001"],
        context_version=1,
    )
    assert t.question_normalized == "报告是否可靠？"


def test_hypothesis_schema_bounds():
    from src.cognition.models import Hypothesis
    h = Hypothesis(
        id="H1", text="发现日军主力航母群，应立即全力攻击。",
        predicted_class="CV", predicted_count_range=(2, 4),
        predicted_position=(-12.2, 157.8),
        predicted_course_range=(100, 140), predicted_speed_range=(16, 22),
        supporting_evidence_ids=["EV-000001"],
        assumptions=["侦察机识别正确"],
        aggressiveness=0.6, novelty=0.2,
    )
    assert h.predicted_count_range == (2, 4)
    with pytest.raises(ValueError):
        Hypothesis(id="H2", text="x", aggressiveness=1.5)
    with pytest.raises(ValueError):
        Hypothesis(id="H3", text="x", novelty=-0.1)
    with pytest.raises(ValueError):
        Hypothesis(id="H4", text="x", predicted_count_range=(4, 2))  # min>max


def test_hypothesis_carries_no_rule_truth():
    """候选不携带规则侧真值字段（LLM 不能自带 fit/评分）。"""
    from src.cognition.models import Hypothesis
    dumped = Hypothesis(id="H1", text="x").model_dump()
    for banned in ("fit", "score", "evidence_fit", "weighted_fit",
                   "actual_enemy", "internal_truth_ref"):
        assert banned not in dumped, f"Hypothesis 不应携带 {banned}"


def test_judgment_result_roundtrip():
    from src.cognition.models import JudgmentResult
    r = JudgmentResult(
        task_id="JT-000001", actor_id="tf17_intel",
        chosen_hypothesis_id="H1",
        plausible_hypothesis_ids=["H1", "H2"],
        dice_record_id="chk_000001",
        error_type="none", error_severity=0.0, confidence_band="medium",
        recommendation="等待第二来源印证",
        assumptions=["单机识别可靠"],
        change_my_mind=["陆军飞机报告航母群时重新研判"],
        formula_version="v0-5dim", result_version=1,
    )
    data = r.model_dump(mode="json")
    assert data["error_type"] == "none"
    r2 = JudgmentResult(**data)          # 序列化往返可重建
    assert r2.task_id == "JT-000001" and r2.plausible_hypothesis_ids == ["H1", "H2"]


def test_judgment_memory_supersedes_chain():
    from src.cognition.models import JudgmentMemory
    m1 = JudgmentMemory(
        actor_id="tf17_intel", task_type="assess", domain="intelligence",
        result_id="JR-000001", selected_hypothesis="H1",
        alternative_hypotheses=["H2"], evidence_ids=["EV-000001"],
        confidence="medium",
    )
    m2 = JudgmentMemory(
        actor_id="tf17_intel", task_type="assess", domain="intelligence",
        result_id="JR-000002", selected_hypothesis="H3",
        alternative_hypotheses=[], evidence_ids=["EV-000002"],
        confidence="high", supersedes_id=m1.id,
        commander_decision="approve",
    )
    assert m2.supersedes_id == m1.id
    assert m2.status in ("open", "revised", "superseded")


def test_judgment_audit_record_snapshot():
    from src.cognition.models import JudgmentAuditRecord
    a = JudgmentAuditRecord(
        task_id="JT-000001", result_id="JR-000001", actor_id="tf17_intel",
        formula_version="v0-5dim",
        attribute_snapshot={"competence": 6, "risk_tolerance": 3},
        candidate_scores={"H1": 0.71, "H2": 0.63},
        plausible_set=["H1", "H2"],
        dice_record_id="chk_000001",
        memory_ids=["JM-000001"], context_version=1, random_seed="20260604:3",
    )
    assert a.candidate_scores["H1"] > a.candidate_scores["H2"]


def test_judgment_engine_protocol_runtime_checkable():
    from src.cognition.engine import JudgmentEngine
    assert isinstance(_RecordingEngine(), JudgmentEngine)


class _RecordingEngine:
    def assess(self, task, context):
        from src.cognition.models import JudgmentResult
        return JudgmentResult(task_id=task.id, actor_id=context.actor.actor_id)


def test_judgment_context_holds_views_and_memories_only():
    from src.cognition.models import JudgmentContext
    actor = _profile()
    view = EvidenceView(evidence_id="EV-000001", summary="s")
    ctx = JudgmentContext(actor=actor, evidence=[view], memories=[])
    assert ctx.evidence[0].evidence_id == "EV-000001"
    assert ctx.memories == []


# ── GameState 容器 ──

def test_game_state_has_judgment_containers():
    s = GameState(clock={"game_time": datetime(1942, 5, 7, 6, 0, tzinfo=timezone.utc)})
    assert s.judgment_tasks == []
    assert s.judgment_results == []
    assert s.judgment_memories == []
    assert s.judgment_audits == []


# ── 珊瑚海名册与权限 ──

def test_coral_sea_roster_core_four_actors():
    from src.cognition.roster import CORAL_SEA_ACTORS
    ids = {a.actor_id for a in CORAL_SEA_ACTORS}
    assert {"fletcher", "fitch", "tf17_intel", "tf17_ops"} <= ids


def test_fletcher_is_player_not_engine_actor():
    from src.cognition.roster import CORAL_SEA_ACTORS, get_actor
    f = get_actor("fletcher")
    assert f.is_player is True
    # 玩家不产生判断（系统不能替参谋形成判断，玩家也不是判断引擎对象）
    assert f.role == "player"


def test_roster_profiles_have_no_unsourced_fiction():
    """人物档案不携带自由虚构事实字段：persona 素材只允许引用已登记史料键。"""
    from src.cognition.roster import CORAL_SEA_ACTORS, HISTORICAL_SOURCES
    for a in CORAL_SEA_ACTORS:
        for ref in a.source_refs:
            assert ref in HISTORICAL_SOURCES, f"{a.actor_id} 引用未登记史料 {ref}"


def test_roster_serialization_contains_no_actual_enemy():
    from src.cognition.roster import CORAL_SEA_ACTORS, permission_matrix
    import json
    blob = json.dumps(
        [a.model_dump() for a in CORAL_SEA_ACTORS] + [permission_matrix()],
        ensure_ascii=False,
    ).lower()
    for banned in ("actual_enemy", "internal_truth_ref", "shokaku", "zuikaku"):
        assert banned not in blob, f"名册可见面泄露 {banned}"


def test_permission_matrix_matches_plan_section_nine():
    """§九 可见信息：情报参谋读权限内证据；Fitch 读已呈报简报；作战参谋读已批准标图。"""
    from src.cognition.roster import get_permission
    p_intel = get_permission("tf17_intel")
    assert p_intel["raw_evidence_roles"] == [ActorRole.INTEL_OFFICER.value]
    assert "briefed" not in (p_intel.get("evidence_via") or [])

    p_fitch = get_permission("fitch")
    assert p_fitch["evidence_via"] == ["briefed", "approved_plots"]

    p_ops = get_permission("tf17_ops")
    assert p_ops["evidence_via"] == ["approved_plots", "briefed"]


def test_actor_evidence_views_filters_by_permission():
    """装配函数按角色裁剪：情报参谋读原始证据；Fitch 只读已呈报简报引用的证据。"""
    from src.cognition.context import actor_evidence_views
    from src.cognition.roster import get_actor
    from src.intel.models import IntelBrief
    from src.intel import service as intel
    from src.intel.models import Evidence, MessageEnvelope

    s = GameState(clock={"game_time": datetime(1942, 5, 7, 6, 0, tzinfo=timezone.utc)})
    msg = MessageEnvelope(sender_id="scout1")
    intel.file_message(s, msg, by="scout1")
    ev = intel.register_evidence(
        s, message=msg, source_id="scout1",
        source_type=__import__("src.intel.contracts", fromlist=["SourceType"]).SourceType.CARRIER_SCOUT,
        access_roles=[ActorRole.INTEL_OFFICER],
        summary="米西马以北报告两艘航母",
    )
    # 简报未呈报前 Fitch 不可见
    views_fitch = actor_evidence_views(s, get_actor("fitch"))
    assert views_fitch == []
    # 情报参谋原始可见
    views_intel = actor_evidence_views(s, get_actor("tf17_intel"))
    assert [v.evidence_id for v in views_intel] == [ev.id]
    # 简报呈报后 Fitch 可见其引用的证据
    s.intel_briefs.append(IntelBrief(
        id="BRF-000001", author_actor_id="tf17_intel",
        new_evidence_ids=[ev.id], status="proposed",
    ))
    views_fitch = actor_evidence_views(s, get_actor("fitch"))
    assert [v.evidence_id for v in views_fitch] == [ev.id]


# ── 中途岛不回归 ──

def test_midway_npc_registry_untouched():
    from src.npc_config import NPC_REGISTRY
    assert set(NPC_REGISTRY) >= {"browning", "murray", "mitscher",
                                 "radio_officer", "intel_officer", "navigator"}
    assert NPC_REGISTRY["browning"].competence == 9


def test_s2_default_policy_still_mechanical():
    """S3 上线不偷换 S2 管线默认策略（迁移方案：S2 纵切保持机械降级语义）。"""
    assert isinstance(DEFAULT_POLICY, MechanicalPolicy)
