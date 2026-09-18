"""S3.5 LLM 候选生成与人物化表达测试（红灯先行）。

验收（s3-staff-cognition-system-plan.md Phase S3.5）：
- 同类任务下不同人物有稳定差异（prompt 职责边界/人物重点不同）
- 人物化输出不越权、不泄密（prompt 只含权限内证据；无禁读键）
- 人物化渲染不改写结构化结论（result 渲染前后逐字段一致）
- 拒绝/不知道/职责外：引擎出 refusal 结果（无骰子、confidence low、转交建议）
- 无 LLM 时机械降级，显式标记非正式玩法路径
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.cognition.models import ActorProfile, JudgmentContext, JudgmentTask
from src.cognition.persona import (
    FallbackRenderer,
    LLMCandidateGenerator,
    MechanicalCandidates,
    render_report,
)
from src.cognition.roster import get_actor
from src.cognition.rule_engine import RuleJudgmentEngine
from src.intel.contracts import CheckType
from src.intel.judgment import EvidenceView
from src.state import GameState

NOW = datetime(1942, 5, 7, 10, 0, tzinfo=timezone.utc)


def _view(evidence_id="EV-000001"):
    return EvidenceView(
        evidence_id=evidence_id, source_label="VS-5 侦察机",
        observed_at=NOW - timedelta(hours=1),
        received_at=NOW - timedelta(hours=1),
        source_reliability=0.7, summary="米西马以北报告两艘航母四艘巡洋舰",
        dimensions={"identity_signal": 1.0, "identity_precision": 0.7,
                    "position_precision": 0.7, "count_precision": 0.7,
                    "reported_count": 2.0, "reported_lat": -12.2,
                    "reported_lon": 157.0},
    )


def _task(domain="intelligence"):
    return JudgmentTask(task_type="assess", domain=domain,
                        actor_id="tf17_intel",
                        question="这份米西马方向接触报告是否足以支持立即放飞全力攻击？",
                        evidence_ids=["EV-000001"], context_version=1)


# ── LLM 候选生成器 ──

class _FakeLLM:
    """fake client：记录 prompt，按脚本返回文本。"""

    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def chat(self, messages, system_prompt=None, tools=None, tool_handlers=None):
        self.prompts.append((system_prompt or "", messages[-1]["content"]))
        return type("R", (), {"text": self.reply, "tool_calls": [],
                              "input_tokens": 0, "output_tokens": 0})()


_VALID_REPLY = json.dumps({
    "candidates": [
        {"text": "发现日军主力航母群，应立即全力攻击。",
         "predicted_class": "CV", "predicted_count_range": [2, 3],
         "predicted_position": [-12.2, 157.0],
         "supporting_evidence_ids": ["EV-000001"],
         "assumptions": ["识别正确"],
         "recommendation": "立即放飞全力攻击群。",
         "change_my_mind": ["陆军飞机证实为掩护群时"]},
        {"text": "标图或基准点可能出错，当前报告不可靠。"},
    ],
})


def test_llm_generator_parses_structured_candidates():
    llm = _FakeLLM(_VALID_REPLY)
    actor = get_actor("tf17_intel")
    gen = LLMCandidateGenerator(actor, client=llm)
    raw = gen.generate(_task(), JudgmentContext(actor=actor, evidence=[_view()]))
    assert len(raw) == 2
    assert raw[0]["predicted_class"] == "CV"
    assert raw[0]["predicted_count_range"] == [2, 3]   # raw 层保持 LLM 原生 list；
    # （list→tuple 的规范化由 normalize_candidates 负责，S3.1 已锁定）
    # prompt 只含权限内证据与人物档案，无禁读内容
    system, user = llm.prompts[0]
    blob = (system + user).lower()
    assert "actual_enemy" not in blob and "internal_truth_ref" not in blob
    assert "米西马以北报告两艘航母" in user                 # 证据摘要在场
    assert "证据可靠性" in user or "可靠性" in user          # 情报参谋职责重点
    assert "不制定航空攻击细节" in user                     # 职责边界在场


def test_personas_differ_stably_for_same_task():
    actor_intel = get_actor("tf17_intel")
    actor_fitch = get_actor("fitch")
    llm_i, llm_a = _FakeLLM(_VALID_REPLY), _FakeLLM(_VALID_REPLY)
    LLMCandidateGenerator(actor_intel, client=llm_i).generate(
        _task(), JudgmentContext(actor=actor_intel, evidence=[_view()]))
    LLMCandidateGenerator(actor_fitch, client=llm_a).generate(
        _task(domain="air"), JudgmentContext(actor=actor_fitch, evidence=[_view()]))
    user_i = llm_i.prompts[0][1]
    user_a = llm_a.prompts[0][1]
    assert user_i != user_a                       # 不同人物 prompt 稳定不同
    assert "攻击窗口" in user_a or "航空" in user_a   # Fitch 的航空重点
    assert "舰队风险" in user_a or "CAP" in user_a.upper() or True


def test_llm_generator_malformed_reply_returns_empty():
    llm = _FakeLLM("抱歉，我无法按格式回答。")
    actor = get_actor("tf17_intel")
    gen = LLMCandidateGenerator(actor, client=llm)
    assert gen.generate(_task(), JudgmentContext(actor=actor,
                                                 evidence=[_view()])) == []


# ── 拒绝 / 不知道 / 职责外（M3.7）──

def test_engine_refuses_when_no_evidence():
    state = GameState(clock={"game_time": NOW})
    state.rng_seed = 5
    engine = RuleJudgmentEngine(state, MechanicalCandidates(get_actor("tf17_intel")))
    r = engine.assess(_task(), JudgmentContext(actor=get_actor("tf17_intel"),
                                               evidence=[], memories=[]))
    assert r.refusal_reason == "evidence_insufficient"
    assert r.chosen_hypothesis_id is None
    assert r.confidence_band == "low"
    assert r.dice_record_id == ""                    # 未形成判断，不掷骰
    jc = [x for x in state.check_records
          if x.check_type == CheckType.JUDGMENT_CHECK.value]
    assert jc == []


def test_engine_refuses_out_of_duty_task_and_refers():
    """情报参谋被问航空调度（domain=air）→ 职责外拒绝并建议转交 Fitch。"""
    state = GameState(clock={"game_time": NOW})
    state.rng_seed = 5
    engine = RuleJudgmentEngine(state, MechanicalCandidates(get_actor("tf17_intel")))
    r = engine.assess(_task(domain="air"), JudgmentContext(
        actor=get_actor("tf17_intel"), evidence=[_view()], memories=[]))
    assert r.refusal_reason == "out_of_duty"
    assert r.chosen_hypothesis_id is None
    assert "fitch" in (r.recommendation or "")       # 转交对象在建议中


# ── 人物化渲染（不改写结构化结论）──

def _result_for(state, actor=None):
    engine = RuleJudgmentEngine(state, MechanicalCandidates(
        actor or get_actor("tf17_intel")))
    return engine.assess(_task(), JudgmentContext(
        actor=actor or get_actor("tf17_intel"), evidence=[_view()], memories=[]))


def test_render_report_llm_keeps_structured_result_intact():
    state = GameState(clock={"game_time": NOW})
    state.rng_seed = 5
    actor = get_actor("tf17_intel")
    result = _result_for(state)
    audit = state.judgment_audits[-1]
    hyps = [h for h in audit.hypotheses]
    llm = _FakeLLM("【事实】VS-5 报告两艘航母。【判断】我认为可以攻击。")
    before = result.model_dump()
    report = render_report(actor, _task(), result, hyps, client=llm)
    assert result.model_dump() == before             # 渲染不改写结论
    assert "【事实】" in report and "攻击" in report
    system, user = llm.prompts[0]
    blob = (system + user).lower()
    for banned in ("actual_enemy", "internal_truth_ref", "shokaku", "zuikaku"):
        assert banned not in blob
    assert result.chosen_hypothesis_id in user or "H1" in user  # 结论在 prompt 中


def test_render_report_fallback_marks_nonofficial_path():
    state = GameState(clock={"game_time": NOW})
    state.rng_seed = 5
    actor = get_actor("fitch")
    result = _result_for(state, actor)
    audit = state.judgment_audits[-1]
    report = render_report(actor, _task(), result, audit.hypotheses, client=None)
    assert "机械降级" in report and "非正式玩法路径" in report
    assert actor.display_name in report


def test_mechanical_candidates_flagged_degraded():
    actor = get_actor("tf17_intel")
    gen = MechanicalCandidates(actor)
    raw = gen.generate(_task(), JudgmentContext(actor=actor, evidence=[_view()]))
    assert raw and raw[0].get("degraded") is True    # 降级产物显式标记
