"""S2.6 舰艇接触与友军电报来源（§M2.1/§M2.2，D18）。

统一证据协议：瞭望/雷达/声呐/巡逻机/友军电报全部经
「观测 → 电文 → 通信链 → 收报 → 证据 → 工作项」，
不走任何旁路（验收：非航空来源不绕过通信和情报流程）。

来源特有质量与误差规则（SENSOR_PROFILES）：
- 瞭望：夜间识别骤降；方位误差中等
- 雷达：方位/距离精度高，但只见回波不见舰型（识别精度最低）
- 声呐：位置粗略，仅水下/大型接触
- 巡逻机（PBY）：识别好于舰载瞭望，弱于舰载侦察机
- 友军电报：保留转述层级与原发送者（转述有损 → 可靠性折减）
"""
from datetime import timedelta
from typing import Optional

from src.intel.contracts import (
    CheckType,
    CommCondition,
    SourceType,
    WorkPriority,
)
from src.intel.rng import RNGService
from src.intel import service as intel
from src.intel.models import MessageEnvelope, SourceObservation
from src.npc_config import UNIT_REGISTRY
from src.scouting import compute_report_delay, distort_bearing, distort_count, distort_distance

# (bearing_err_deg, dist_error_pct, identity_precision, night_identity_factor)
SENSOR_PROFILES = {
    SourceType.VISUAL_LOOKOUT: (6, 0.15, 0.55, 0.5),
    SourceType.RADAR: (3, 0.06, 0.30, 1.0),      # 雷达夜间不受影响，但不见舰型
    SourceType.SONAR: (10, 0.20, 0.20, 1.0),
    SourceType.PATROL_AIR: (4, 0.08, 0.75, 0.6),
    SourceType.FRIENDLY_REPORT: (6, 0.12, 0.50, 1.0),  # 转述有损
}
# 友军转述可靠性折减（每级转述 ×0.9，保留在 evidence.source_reliability）
RELAY_RELIABILITY_FACTOR = 0.9

_MECH_TEXT = {
    SourceType.VISUAL_LOOKOUT: "SIGHTED {count} SHIPS BEARING {bearing} DIST {distance_nm} NM",
    SourceType.RADAR: "RADAR CONTACT {count} SURFACE BLIPS BEARING {bearing} DIST {distance_nm} NM TYPE UNKNOWN",
    SourceType.SONAR: "SONAR CONTACT BEARING {bearing} DIST {distance_nm} NM CLASS UNKNOWN",
    SourceType.PATROL_AIR: "PATROL REPORTS {count} VESSELS BEARING {bearing} DIST {distance_nm} NM",
    SourceType.FRIENDLY_REPORT: "RELAY: {origin} REPORTS CONTACT BEARING {bearing} DIST {distance_nm} NM",
}

_UNIT_NAMES = {
    SourceType.VISUAL_LOOKOUT: "瞭望哨",
    SourceType.RADAR: "雷达室",
    SourceType.SONAR: "声呐室",
    SourceType.PATROL_AIR: "PBY 巡逻机",
    SourceType.FRIENDLY_REPORT: "友军通信台",
}


def report_surface_observation(
    state, *,
    source_type: SourceType,
    source_unit: str,
    observer_position,
    bearing_true: float,
    distance_nm_true: float,
    target_count: int = 1,
    environment: str = "clear",
    observed_at=None,
    writer=None,
    rng=None,
    priority: WorkPriority = WorkPriority.ROUTINE,
    origin_sender: Optional[str] = None,
    relay_chain: Optional[list[str]] = None,
) -> MessageEnvelope:
    """非舰载机来源的统一观测上报（同一证据协议）。

    observer_position 带 .lat/.lon；radar/sonar 的 classification 恒为
    未识别（传感器物理限制，识别差异可感知）。
    """
    rng = rng or RNGService(state)
    bearing_err, dist_pct, ident, night_factor = SENSOR_PROFILES[source_type]
    if environment in ("night", "storm") and source_type != SourceType.RADAR:
        ident *= night_factor

    unit = UNIT_REGISTRY["sbd_scout_section"]  # 观察质检沿用执行单位能力结构
    quality, q_rec = rng.roll_check(
        check_type=CheckType.OBSERVATION_QUALITY_CHECK,
        actor_id=f"{source_unit} {_UNIT_NAMES[source_type]}",
        npc_modifier=unit.competence * 2,
        situational_mods={"夜间/恶劣海况": -5} if environment in ("night", "storm") else {},
        reason=f"{source_unit} 观察质量检定（{source_type.value}）",
        inputs={"distance_nm": round(distance_nm_true, 1),
                "environment": environment},
    )
    band = "high" if quality.is_critical() else ("standard" if quality.is_success() else "low")

    # 规则侧观测（真值入档）
    obs = SourceObservation(
        id=intel.next_id(state, "OBS"),
        source_id=source_unit,
        source_type=source_type,
        observer_actor_id=source_unit,
        observed_at=observed_at or intel.now(state),
        bearing_true=bearing_true,
        distance_nm_true=distance_nm_true,
        target_name_true="",
        carrier_count_true=target_count,
        sensor_capability=source_type.value,
        environment=environment,
        quality_band=band,
        quality_check_id=q_rec.check_id,
        internal_truth_ref="",
    )
    state.observations.append(obs)

    # 失真后的报告值（传感器特有规则）
    reported_bearing = distort_bearing(bearing_true, max_error=bearing_err, rng=rng)
    reported_distance = distort_distance(distance_nm_true, max_error_pct=dist_pct, rng=rng)
    reported_count = distort_count(target_count, undercount_prob=0.35, rng=rng) \
        if source_type != SourceType.SONAR else target_count
    # 识别差异可感知：雷达/声呐恒未识别（物理限制）；瞭望夜间降级未识别
    if source_type == SourceType.RADAR:
        classification = "雷达接触（未识别舰型）"
    elif source_type == SourceType.SONAR:
        classification = "声呐接触（未识别类别）"
    elif ident < 0.5 or band == "low":
        classification = "大型船只（未识别）"
    else:
        classification = "水面舰艇"

    view = {
        "bearing": int(reported_bearing),
        "distance_nm": int(reported_distance),
        "count": reported_count,
        "quality": band,
        "classification": classification,
        "sensor": source_type.value,
        "identity": round(ident, 2),
        "origin": origin_sender or source_unit,
    }

    generated_by = None
    if writer is not None:
        try:
            raw_text = writer.write_report(
                view, game_time=intel.now(state).strftime("%H:%M"))
            generated_by = getattr(writer, "actor_id", source_unit)
        except Exception:
            generated_by = None
    if generated_by is None:
        raw_text = _MECH_TEXT[source_type].format(**view)

    msg = MessageEnvelope(
        sender_id=origin_sender or source_unit,
        sender_call_sign=source_unit,
        recipient_ids=["TF16 FLAG"],
        priority=priority,
        message_kind="friendly_report" if source_type == SourceType.FRIENDLY_REPORT
        else "sensor_contact",
        observed_at=obs.observed_at,
        raw_text=raw_text,
        fields=dict(view),
        generated_by_npc=generated_by,
        observation_id=obs.id,
        origin_sender=origin_sender,
        relay_chain=list(relay_chain or []),
    )
    intel.file_message(state, msg, by=msg.sender_id, reason="来源观测上报")
    intel.mark_in_transit(state, msg, by="通信链", reason="发往旗舰")

    # 同一通信协议：通信检定决定延迟与完整性（不绕过）
    comm, c_rec = rng.communication_check(
        actor_id=f"{source_unit} 电台",
        competence=unit.competence,
        distance_nm=distance_nm_true,
        reason=f"{source_unit} 通信检定（{source_type.value}）",
    )
    delay = compute_report_delay(distance_nm_true, rng=rng)
    msg.transit_eta = intel.now(state) + timedelta(minutes=delay)
    if comm.raw_roll <= 3:
        intel.lose_message(state, msg, by="通信链", reason="通信检定大失败——电文丢失")
        return msg
    if comm.level == "critical_failure":
        msg.condition = CommCondition.GARBLED
    elif comm.level == "partial":
        msg.condition = CommCondition.PARTIAL
    else:
        msg.condition = CommCondition.COMPLETE
    return msg


def relay_friendly_report(state, *, from_force: str, original_sender: str,
                          observer_position, bearing_true: float,
                          distance_nm_true: float, target_count: int = 1,
                          environment: str = "clear",
                          writer=None, rng=None) -> MessageEnvelope:
    """友军电报（TF16/TF17 等）：保留转述层级与原发送者。

    envelope.sender = 友军司令部（转述者）；origin_sender = 原报告单位；
    relay_chain 记录转述链；证据 source_id 用原发送者（转述有损折减可靠性）。
    """
    msg = report_surface_observation(
        state,
        source_type=SourceType.FRIENDLY_REPORT,
        source_unit=from_force,
        observer_position=observer_position,
        bearing_true=bearing_true,
        distance_nm_true=distance_nm_true,
        target_count=target_count,
        environment=environment,
        writer=writer, rng=rng,
        priority=WorkPriority.URGENT,
        origin_sender=original_sender,
        relay_chain=[from_force],
    )
    # 友军电文以转述体呈现（原发送者在正文与字段都保留）
    if msg.generated_by_npc is None:
        msg.raw_text = (
            f"FROM {original_sender} VIA {from_force}: {msg.raw_text}"
        )
    return msg
