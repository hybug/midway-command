"""S2.7 推理与不确定度工具（§M2.7）。

强制约束：
- 工具只对已收到且当前 NPC 有权限的证据计算。
- 输出是候选几何关系（candidates），不是唯一真值。
- 是否采用由情报参谋判断并写入简报——系统不自动调用：
  没有参谋工具调用时，不产生不确定区域/交叉点等派生认识（D12/D15）。
- 全部确定性纯函数：相同输入 ⇒ 相同输出（可回放）。
- 每次调用落 ToolCallRecord（谁/何时/用什么证据/算出什么），复盘可查。
"""
import math
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.intel.contracts import ActorRole, EvidenceStatus
from src.intel import service as intel
from src.intel.models import Evidence

# 允许使用推理工具的角色（工具层权限，prompt 之外再次校验）
_TOOL_ROLES = {
    "intel_officer": ActorRole.INTEL_OFFICER,
    "chief_of_staff": ActorRole.CHIEF_OF_STAFF,
}


class ToolCallRecord(BaseModel):
    """推理工具调用审计（M2.7.9）。"""
    id: str = ""
    at: Optional[datetime] = None
    actor_id: str
    tool_name: str
    inputs: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


def _actor_role(actor_id: str) -> ActorRole:
    role = _TOOL_ROLES.get(actor_id)
    if role is None:
        raise PermissionError(f"{actor_id} 无推理工具权限")
    return role


def _visible_evidence_by_ids(state, actor_id: str, evidence_ids: list[str]) -> list[Evidence]:
    role = _actor_role(actor_id)
    out = []
    for ev in state.evidence:
        if ev.id in evidence_ids:
            if role not in ev.access_policy:
                raise PermissionError(f"{actor_id} 无权读取证据 {ev.id}")
            if ev.status == EvidenceStatus.ACTIVE:
                out.append(ev)
    return out


def _record(state, *, actor_id: str, tool_name: str, inputs: dict,
            outputs: dict, evidence_ids: list[str]) -> ToolCallRecord:
    rec = ToolCallRecord(
        id=intel.next_id(state, "TOOL"),
        at=intel.now(state),
        actor_id=actor_id,
        tool_name=tool_name,
        inputs=inputs,
        outputs=outputs,
        evidence_ids=evidence_ids,
    )
    state.tool_calls.append(rec)
    intel._audit(state, actor_id=actor_id, action="tool_call",
                 target_id=rec.id, reason=tool_name,
                 evidence_ids=evidence_ids)
    return rec


# ── 几何内核（纯函数，局部平面近似：1° lat = 60nm，lon × cos(lat)）──

def _to_local_nm(origin: tuple, point: tuple) -> tuple:
    dy = (point[0] - origin[0]) * 60.0
    dx = (point[1] - origin[1]) * 60.0 * math.cos(math.radians(origin[0]))
    return (dx, dy)


def _from_local_nm(origin: tuple, dx: float, dy: float) -> tuple:
    lat = origin[0] + dy / 60.0
    lon = origin[1] + dx / (60.0 * math.cos(math.radians(origin[0])))
    return (lat, lon)


def _intersect_lines(p1: tuple, theta1: float, p2: tuple,
                     theta2: float) -> Optional[tuple]:
    """两直线交点（局部平面坐标，nm）；近平行返回 None。

    方位角约定：0°=北=+y，90°=东=+x，方向向量 d(θ)=(sinθ, cosθ)。
    p1 + t·d1 = p2 + u·d2 ⇒ t = (wy·sinθ2 - wx·cosθ2) / sin(θ2-θ1)
    """
    t1 = math.radians(theta1)
    t2 = math.radians(theta2)
    det = math.sin(t2 - t1)
    if abs(det) < 0.05:  # 近平行（<3°）无稳定交点
        return None
    wx, wy = p2[0] - p1[0], p2[1] - p1[1]
    s = (wy * math.sin(t2) - wx * math.cos(t2)) / det
    return (p1[0] + s * math.sin(t1), p1[1] + s * math.cos(t1))


# ── 工具 1：多方位线交叉（M2.7.1/2.7.3）──

def bearing_intersection(state, *, actor_id: str,
                         lines: list[dict]) -> dict:
    """方位线交叉候选点。

    lines: [{lat, lon, bearing_deg, label?, evidence_id?}]（≥2 条）
    输出 candidates：每个交点附 quality（交角越接近 90° 越好）——
    候选关系而非唯一真值，是否采信由参谋写入简报。
    """
    role = _actor_role(actor_id)
    ev_ids = [ln.get("evidence_id") for ln in lines if ln.get("evidence_id")]
    if ev_ids:
        _visible_evidence_by_ids(state, actor_id, ev_ids)
    candidates = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            a, b = lines[i], lines[j]
            o1 = (a["lat"], a["lon"])
            o2 = (b["lat"], b["lon"])
            p_local = _intersect_lines((0.0, 0.0), a["bearing_deg"],
                                       _to_local_nm(o1, o2), b["bearing_deg"])
            if p_local is None:
                continue
            point = _from_local_nm(o1, p_local[0], p_local[1])
            cross = abs((a["bearing_deg"] - b["bearing_deg"] + 180) % 360 - 180)
            quality = "good" if 45 <= cross <= 135 else "poor"
            candidates.append({
                "lat": round(point[0], 4),
                "lon": round(point[1], 4),
                "quality": quality,
                "pair": [a.get("label", f"L{i}"), b.get("label", f"L{j}")],
                "cross_angle_deg": round(cross, 1),
            })
    outputs = {
        "candidates": candidates,
        "note": "候选交叉关系；非唯一真值，采信与否由情报参谋判断",
    }
    _record(state, actor_id=actor_id, tool_name="bearing_intersection",
            inputs={"lines": lines}, outputs=outputs, evidence_ids=ev_ids)
    return outputs


# ── 工具 2：位置年龄与可能移动区域（M2.7.2/2.7.6）──

def possible_area(state, *, actor_id: str, lat: float, lon: float,
                  observed_at, speed_max_kn: float = 25.0,
                  label: str = "contact", evidence_id: Optional[str] = None) -> dict:
    """可能区域：观测时位置 + 年龄 × 最大航速 ⇒ 不确定圆（候选关系）。"""
    ev_ids = []
    if evidence_id:
        _visible_evidence_by_ids(state, actor_id, [evidence_id])
        ev_ids = [evidence_id]
    age_h = (intel.now(state) - observed_at).total_seconds() / 3600.0
    radius = round(4.0 + max(0.0, age_h) * speed_max_kn, 1)  # 4nm 基础误差 + 扩展
    outputs = {
        "candidates": [{
            "lat": lat,
            "lon": lon,
            "radius_nm": radius,
            "age_hours": round(age_h, 2),
            "speed_assumption_kn": f"0-{speed_max_kn}",
            "label": label,
        }],
        "note": "可能移动范围假设（非真值）；随证据年龄增长扩大",
    }
    _record(state, actor_id=actor_id, tool_name="possible_area",
            inputs={"lat": lat, "lon": lon, "observed_at": observed_at.isoformat(),
                    "speed_max_kn": speed_max_kn},
            outputs=outputs, evidence_ids=ev_ids)
    return outputs


# ── 工具 3：搜索覆盖缺口（M2.7.5）──

def coverage_gaps(state, *, actor_id: str, center_lat: float, center_lon: float,
                  radius_nm: float, searched: list[dict],
                  grid_nm: float = 20.0) -> dict:
    """覆盖缺口：期望区域内未被已搜索圆覆盖的网格点（候选关系）。

    searched: [{lat, lon, radius_nm, at?}]（已执行的搜索）
    """
    _actor_role(actor_id)
    gaps = []
    n_steps = max(2, int(radius_nm / grid_nm))
    for iy in range(-n_steps, n_steps + 1):
        for ix in range(-n_steps, n_steps + 1):
            gy = center_lat + iy * grid_nm / 60.0
            gx = center_lon + ix * grid_nm / (60.0 * math.cos(math.radians(center_lat)))
            if math.hypot(ix, iy) * grid_nm > radius_nm:
                continue
            covered = any(
                math.hypot((gx - s["lon"]) * 60.0 * math.cos(math.radians(gy)),
                           (gy - s["lat"]) * 60.0) <= s["radius_nm"]
                for s in searched
            )
            if not covered:
                gaps.append({"lat": round(gy, 3), "lon": round(gx, 3)})
    outputs = {
        "candidates": gaps,
        "grid_nm": grid_nm,
        "note": "未覆盖采样点（候选缺口）；不代表敌舰位置",
    }
    _record(state, actor_id=actor_id, tool_name="coverage_gaps",
            inputs={"center": [center_lat, center_lon], "radius_nm": radius_nm,
                    "searched": searched},
            outputs=outputs, evidence_ids=[])
    return outputs


# ── 工具 4：证据冲突提示（M2.7.7，委托 S2.5 检测并落工具审计）──

def evidence_conflict_report(state, *, actor_id: str,
                             evidence_ids: list[str]) -> dict:
    from src.intel.conflicts import detect_conflicts
    _visible_evidence_by_ids(state, actor_id, evidence_ids)
    found = detect_conflicts(state, evidence_ids, by=actor_id,
                             role=_actor_role(actor_id))
    outputs = {
        "conflicts": [
            {"id": c.id, "kind": c.kind, "note": c.note, "severity": c.severity}
            for c in found
        ],
        "note": "冲突为候选提示；并存不裁决",
    }
    _record(state, actor_id=actor_id, tool_name="evidence_conflict_report",
            inputs={"evidence_ids": evidence_ids}, outputs=outputs,
            evidence_ids=evidence_ids)
    return outputs


# ── 工具 5：判断依赖反查（M2.7.8）──

def what_depends_on(state, *, actor_id: str, assessment_id: str) -> dict:
    """反查某判断书依赖的证据/骰子/工具调用（复盘归因）。"""
    _actor_role(actor_id)
    assessment = next((a for a in state.assessments if a.id == assessment_id), None)
    if assessment is None:
        return {"error": f"判断书 {assessment_id} 不存在"}
    claims = [c for c in state.claims if c.assessment_id == assessment_id]
    outputs = {
        "assessment_id": assessment_id,
        "evidence_ids": assessment.based_on_evidence_ids,
        "dice_record_ids": assessment.dice_record_ids,
        "conflict_ids": assessment.conflict_ids,
        "tool_call_ids": sorted({t for c in claims for t in c.tool_call_ids}),
        "claims": [{"id": c.id, "type": c.claim_type, "text": c.text}
                   for c in claims],
        "note": "判断依赖反查（归因链）",
    }
    _record(state, actor_id=actor_id, tool_name="what_depends_on",
            inputs={"assessment_id": assessment_id}, outputs=outputs,
            evidence_ids=assessment.based_on_evidence_ids)
    return outputs


# ── NPC 工具 schema（OpenAI 格式；LLM 参谋可调用）──

INTEL_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "query_bearing_intersection",
            "description": (
                "Compute candidate intersection points of two or more bearing "
                "lines (from different observers). Returns CANDIDATE relations, "
                "not ground truth. Requires real lat/lon origins."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lines": {
                        "type": "array",
                        "description": "Bearing lines: [{lat, lon, bearing_deg, label}].",
                        "items": {"type": "object"},
                    },
                },
                "required": ["lines"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_possible_area",
            "description": (
                "Estimate the possible area of a contact given its reported "
                "position and observation age (assumed speed 0-25 kn). "
                "Candidate envelope, not truth."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "observed_at": {"type": "string"},
                    "evidence_id": {"type": "string"},
                },
                "required": ["lat", "lon", "observed_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_coverage_gaps",
            "description": (
                "Find uncovered grid points inside an expected area given "
                "already-searched circles. Candidate gaps only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "center_lat": {"type": "number"},
                    "center_lon": {"type": "number"},
                    "radius_nm": {"type": "number"},
                    "searched": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "[{lat, lon, radius_nm}] circles already searched.",
                    },
                },
                "required": ["center_lat", "center_lon", "radius_nm", "searched"],
            },
        },
    },
]


TOOL_HANDLERS = {
    "query_bearing_intersection": bearing_intersection,
    "query_possible_area": possible_area,
    "query_coverage_gaps": coverage_gaps,
}
