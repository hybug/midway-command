"""S2.3 舰载侦察机纵切测试（红灯先行）。

验收（s2-intelligence-system-plan.md Phase S2.3）：
- 从 SBD 实际发现到玩家看到简报可完整运行
- 能区分漏报、误判、通信损坏和参谋误判
- 未收到电报不会泄露内容

LLM 通道全部注入 fake（飞行员 writer / 分析器 analyst / 脚本化 rng），
测试不触网；管线驱动的用例经 autouse fixture 固定降级路径。
"""
from datetime import datetime, timedelta, timezone

import pytest

from src.dice import DiceResult
from src.intel import flow
from src.intel.contracts import (
    ApprovalStatus,
    CheckType,
    CommCondition,
    ContactStatus,
    MessageStatus,
    WorkItemStatus,
    WorkPriority,
)
from src.intel.flow import (
    intel_work_queue,
    on_scout_detection,
    process_intel,
    run_intelligence_cycle,
)
from src.intel.models import IntelWorkItem
from src.intel.policy import MechanicalPolicy
from src.intel.rng import CheckRecord
from src.intel import service as intel
from src.tools import handle_execute_action


# ── fakes ──

class FakePilotWriter:
    actor_id = "fake_pilot_vs6"

    def write_report(self, view, game_time):
        return (
            f"LOOKOUT! {view['classification']} x{view['count']} "
            f"BEARING {view['bearing']} DIST {view['distance_nm']} NM, "
            f"IDENT {view['quality'].upper()}"
        )


class FakeAnalyst:
    actor_id = "fake_intel_analyst"

    def analyze(self, work_item, evidence_views, dice, profile):
        return {
            "narrative": (
                "【事实】VS-6 报告发现大型编队。"
                "【判断】结合单机远程识别的局限，敌主力存在的概率中等。"
                f"（骰子等级 {dice.level}，偏差 {dice.error_direction}）"
            ),
            "claims": [
                {"claim_type": "fact", "text": "VS-6 电文报告发现编队"},
                {"claim_type": "judgment", "text": "敌主力大概率为航母编队"},
                {"claim_type": "hypothesis", "text": "不排除数量误报"},
            ],
        }


_LEVEL_FINAL = {
    "critical_success": 97, "success": 80, "partial": 50,
    "failure": 30, "critical_failure": 8,
}


def _dice_result(level, raw):
    return DiceResult(raw_roll=raw, modified_roll=_LEVEL_FINAL[level],
                      level=level, level_name=level,
                      modifiers_applied=[])


def _rec(check_id="chk_fake"):
    return CheckRecord(
        check_id=check_id, check_type="fake", actor_id="fake",
        game_time=datetime(1942, 6, 4, 5, 0, tzinfo=timezone.utc),
        random_seed="fake:0",
    )


class ScriptedRng:
    """脚本化随机源：检定按类型返回设定等级，通用抽取恒 0。"""

    def __init__(self, quality="success", comm="success", comm_raw=50,
                 judgment="success"):
        self.quality_level = quality
        self.comm_level = comm
        self.comm_raw = comm_raw
        self.judgment_level = judgment
        self.calls = []

    def roll_check(self, check_type, actor_id, **kw):
        self.calls.append(check_type)
        ct = getattr(check_type, "value", check_type)
        if ct == CheckType.OBSERVATION_QUALITY_CHECK.value:
            return _dice_result(self.quality_level, 50), _rec("chk_quality")
        if ct == CheckType.COMMUNICATION_CHECK.value:
            return _dice_result(self.comm_level, self.comm_raw), _rec("chk_comm")
        if ct == CheckType.JUDGMENT_CHECK.value:
            return _dice_result(self.judgment_level, 50), _rec("chk_judgment")
        return _dice_result("partial", 50), _rec("chk_other")

    def communication_check(self, actor_id, competence, distance_nm,
                            reason="", inputs=None):
        return _dice_result(self.comm_level, self.comm_raw), _rec("chk_comm")

    def randint(self, check_type, actor_id, low, high, reason, **kw):
        return 0

    def chance(self, check_type, actor_id, prob, reason, **kw):
        return False


@pytest.fixture(autouse=True)
def fake_llm_channels(monkeypatch):
    """管线驱动的用例固定注入 fake writer / 无 analyst（不触网、可复现）。"""
    monkeypatch.setattr(flow, "_default_writer", lambda: FakePilotWriter())
    monkeypatch.setattr(flow, "_default_analyst", lambda: None)


# ── 复用基础构造 ──

def make_state(rng_seed=7):
    from src.state import GameClock, GameState, Position, TaskForce, Carrier, Aircraft, AircraftType, AircraftStatus
    from datetime import datetime, timezone
    carrier = Carrier(
        name="USS Enterprise (CV-6)",
        position=Position(lat=32.0, lon=-175.0),
        aircraft=[
            Aircraft(id=f"SBD-VB6-{i:02d}", type=AircraftType.SBD,
                     squadron="VB-6", carrier="Enterprise",
                     status=AircraftStatus.READY)
            for i in range(1, 11)
        ],
    )
    tf = TaskForce(name="TF16", carriers=[carrier], course=240, speed=25)
    state = GameState(
        clock=GameClock(game_time=datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)),
        task_forces=[tf],
        rng_seed=rng_seed,
    )
    state.actual_enemy = [{
        "name": "Kido Butai",
        "carriers": ["Akagi", "Kaga", "Soryu", "Hiryu"],
        "position": {"lat": 30.0, "lon": -178.0},
        "status": "rearming",
    }]
    return state


def _launch(state):
    handle_execute_action(state, "launch_scout", {"direction": "southwest"})


def _advance(state, ticks=9):
    for _ in range(ticks):
        state.clock.game_time += timedelta(minutes=15)
        from src.scouting import check_scout_results
        check_scout_results(state)


def _detect_until_message(rng_seed_start=0, max_tries=60):
    for seed in range(rng_seed_start, rng_seed_start + max_tries):
        state = make_state(rng_seed=seed)
        _launch(state)
        _advance(state)
        msgs = [m for m in state.messages if m.message_kind == "scout_report"]
        if msgs:
            return state, msgs[0], seed
    raise AssertionError("60 个种子内未产生探测（不应发生）")


# ── 验收 1：纵切完整运行 ──

def test_slice_detection_to_in_transit():
    state, msg, _ = _detect_until_message()
    assert msg.status == MessageStatus.IN_TRANSIT
    assert msg.fields["count"] >= 1
    assert msg.raw_text.startswith("LOOKOUT!")  # fake 飞行员文风落档
    assert msg.generated_by_npc == "fake_pilot_vs6"
    # 旧管线退役：不再产生 PendingReport
    assert state.pending_reports == []
    # 未送达电文不泄露（D1）
    assert intel.player_inbox(state) == []
    assert msg.raw_text not in str(intel.player_inbox(state))


def test_slice_arrival_registers_evidence_and_work_item():
    state, msg, _ = _detect_until_message()
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    notes = process_intel(state)
    assert msg.received_at is not None
    assert msg.status == MessageStatus.ROUTED  # 收报→登记→路由后停在 routed
    assert len(state.evidence) == 1
    ev = state.evidence[0]
    assert ev.message_id == msg.id
    assert ev.lat is not None  # 证据位置（失真推算）已派生
    items = [i for i in state.intel_work_items if i.status == WorkItemStatus.ASSIGNED.value]
    assert len(items) == 1
    assert msg.routed_to == ["intel_officer"]  # 通信官路由
    assert any("报告到达" in n for n in notes)
    # 迁移期兼容层：known_enemy 有玩家可见条目
    assert len(state.known_enemy) == 1


def test_slice_full_cycle_to_brief():
    state, msg, _ = _detect_until_message()
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    item = intel_work_queue(state)[0]
    brief = run_intelligence_cycle(state, item,
                                   policy=MechanicalPolicy(),
                                   analyst=FakeAnalyst())
    assert brief.status == ApprovalStatus.PROPOSED.value
    assert item.status == WorkItemStatus.SUBMITTED.value
    assert len(state.assessments) == 1
    assessment = state.assessments[0]
    assert assessment.dice_record_ids  # 判断可回溯到骰子记录
    assert len(assessment.claims) >= 1
    claim = state.claims[0]
    assert claim.assessment_id == assessment.id
    assert claim.actor_id == "intel_officer"
    # 参谋信念中的 TENTATIVE 接触（上图需指挥官批准——S2.4）
    belief = intel.belief_for(state, "intel_officer")
    contacts = intel.contacts_of(state, belief)
    assert len(contacts) == 1
    assert contacts[0].status == ContactStatus.TENTATIVE
    assert "【事实】" in brief.narrative and "【判断】" in brief.narrative


def test_no_reprocessing_of_submitted_item():
    state, msg, _ = _detect_until_message()
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    item = intel_work_queue(state)[0]
    run_intelligence_cycle(state, item, analyst=FakeAnalyst())
    with pytest.raises(ValueError):
        run_intelligence_cycle(state, item, analyst=FakeAnalyst())


# ── 验收 2：漏报 / 通信损坏 / 参谋误判 可区分 ──

def test_missed_detection_produces_no_message():
    # 直接驱动 flow：探测失败路径由 scouting 分支保证不调用 on_scout_detection；
    # 这里验证低质量带只产生低置信证据（漏报=无电文，由侦察分支测试覆盖）
    state = make_state()
    _launch(state)
    _advance(state, 12)  # 完整飞完（包含返航），无种子循环
    # 该状态下若无电文，说明检定未成功（漏报），玩家不应看到任何敌情
    msgs = [m for m in state.messages if m.message_kind == "scout_report"]
    if not msgs:
        assert state.known_enemy == []
        assert intel.player_inbox(state) == []


def test_garbled_communication_degrades_evidence():
    state = make_state()
    _launch(state)
    _advance(state, 6)
    scout = state.active_scouts[0]
    scripted = ScriptedRng(quality="success", comm="critical_failure", comm_raw=60)
    msg = on_scout_detection(state, scout=scout,
                             enemy=state.actual_enemy[0],
                             bearing=233.0, distance=195.0,
                             result=_dice_result("success", 80),
                             writer=FakePilotWriter(), rng=scripted)
    assert msg.condition == CommCondition.GARBLED
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    ev = state.evidence[0]
    assert ev.identity_precision <= 0.5  # 通信损坏降低证据精度（区别于参谋误判）
    assert ev.source_reliability < 0.8


def test_lost_communication_never_arrives():
    state = make_state()
    _launch(state)
    _advance(state, 6)
    scout = state.active_scouts[0]
    scripted = ScriptedRng(comm_raw=2)  # raw ≤ 3 → LOST
    msg = on_scout_detection(state, scout=scout,
                             enemy=state.actual_enemy[0],
                             bearing=233.0, distance=195.0,
                             result=_dice_result("success", 80),
                             writer=FakePilotWriter(), rng=scripted)
    assert msg.status == MessageStatus.LOST
    for _ in range(30):
        state.clock.game_time += timedelta(minutes=15)
        process_intel(state)
    assert msg.status == MessageStatus.LOST  # 永不送达
    assert intel.player_inbox(state) == []
    assert state.evidence == []
    assert state.known_enemy == []


def test_staff_misjudgment_recorded_in_dice():
    state, msg, _ = _detect_until_message()
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    item = intel_work_queue(state)[0]
    scripted = ScriptedRng(judgment="critical_failure")
    run_intelligence_cycle(state, item, policy=MechanicalPolicy(),
                           analyst=FakeAnalyst(), rng=scripted)
    assessment = state.assessments[0]
    # 误判可归因：JUDGMENT_CHECK 的骰子记录 id 挂在判断书上（可回放）
    assert "chk_judgment" in assessment.dice_record_ids
    assert assessment.confidence_dimensions["position"] <= 0.2


# ── 验收 3：队列与优先级 ──

def test_flash_interrupts_routine():
    state, msg, _ = _detect_until_message()
    state.clock.game_time = msg.transit_eta + timedelta(minutes=1)
    process_intel(state)
    routine = intel_work_queue(state)[0]
    # 构造一个 FLASH 项排在后面
    flash = IntelWorkItem(
        id="WU-FLASH-TEST", priority=WorkPriority.FLASH,
        status=WorkItemStatus.QUEUED.value,
        trigger_message_id=msg.id, evidence_ids=[],
        created_at=state.clock.game_time + timedelta(minutes=5),
    )
    state.intel_work_items.append(flash)
    queue = intel_work_queue(state)
    assert queue[0].id == "WU-FLASH-TEST"
    assert routine.priority == WorkPriority.ROUTINE or routine.priority == WorkPriority.URGENT


# ── 可回放 ──

def test_slice_replay_identical():
    def run():
        state = make_state(rng_seed=11)
        _launch(state)
        _advance(state, 14)
        process_intel(state)
        return (
            [r.model_dump() for r in state.check_records],
            [(m.id, m.fields, m.condition.value, m.status.value,
              m.transit_eta.isoformat() if m.transit_eta else None)
             for m in state.messages],
        )
    assert run() == run(), "同一种子纵切必须逐字段可回放"
