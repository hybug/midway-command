"""FastAPI server — replaces Streamlit as the frontend backend.

Serves the static HTML/CSS/JS frontend and exposes REST APIs
for game state, NPC chat, time advancement, and suggestion management.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.initial_state import build_initial_state
from src.agents.browning import BrowningNPC
from src.agents.murray import MurrayNPC
from src.agents.mitscher import MitscherNPC
from src.agents.radio_officer import RadioOfficerNPC
from src.agents.intel_officer import IntelOfficerNPC
from src.agents.navigator import NavigatorNPC
from src.npc_config import NPC_REGISTRY
from src.pipeline import build_default_pipeline
from src.ap import consume_ap, has_ap, get_ap_status
from src.mission import plan_mission, confirm_mission, reject_mission
from src.aircraft import recall_air_group
from src.state import GamePhase
from src.routes import (
    PendingRoute,
    PendingRouteStatus,
    Route,
    RouteKind,
    RouteStatus,
    Waypoint,
    pending_to_route,
)
from src.tools import handle_execute_action

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("midway.server")

app = FastAPI(title="中途岛指挥官")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ── Global game state (single-user prototype) ──
game_state = build_initial_state()
pipeline = build_default_pipeline()

# ── Theater context (CHART_SYSTEM.md §三/§四/§九决议6：后端单一下发) ──
from src.theater import load_theater

# fail-fast：战区包损坏则拒绝启动
theater_ctx = load_theater(BASE_DIR / "theaters" / "midway")

npcs: dict = {
    "browning": BrowningNPC(),
    "murray": MurrayNPC(),
    "mitscher": MitscherNPC(),
    "radio_officer": RadioOfficerNPC(),
    "intel_officer": IntelOfficerNPC(),
    "navigator": NavigatorNPC(theater=theater_ctx),
}

NPC_DISPLAY = {
    "browning": {"label": "参谋长", "sender": "布朗宁（BROWNING）· 参谋长", "role": "参谋长"},
    "murray": {"label": "企业号舰长", "sender": "默里（MURRAY）· 企业号舰长", "role": "企业号舰长"},
    "mitscher": {"label": "大黄蜂舰长", "sender": "米切尔（MITSCHER）· 大黄蜂舰长", "role": "大黄蜂舰长"},
    "radio_officer": {"label": "通信官", "sender": "通信官 · TBS", "role": "通信官"},
    "intel_officer": {"label": "情报官", "sender": "情报官 · 情报参谋", "role": "情报参谋"},
    "navigator": {"label": "航海参谋", "sender": "航海参谋 · NAVIGATOR", "role": "航海参谋"},
}


# ── Request models ──

class ChatRequest(BaseModel):
    npc_id: str
    message: str


class AdvanceRequest(BaseModel):
    minutes: int = 15


class SuggestionAction(BaseModel):
    pass


class CreateRouteRequest(BaseModel):
    kind: RouteKind
    owner: str
    waypoints: list[Waypoint]


class NavigatorProposeRequest(BaseModel):
    message: str


class RouteCommentRequest(BaseModel):
    feedback: str


class NewGameRequest(BaseModel):
    theater_id: str


# ── Routes ──

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


@app.get("/state")
async def get_state():
    """Return full game state as JSON."""
    ap = get_ap_status(game_state)
    # S2.4（§十一迁移）：known_enemy 下发已批准标图公共视图（无批准标图时
    # 直通 legacy 列表——迁移期兼容，不破坏既有 UI/测试）
    from src.intel import service as intel_service
    known_enemy_public = [
        {
            "description": e.description,
            "confidence": e.confidence,
            "source": e.source,
            "position": {"lat": e.position.lat, "lon": e.position.lon},
        }
        for e in intel_service.known_enemy_compat_view(game_state)
    ]
    # O.3：全舰队序列化（珊瑚海双盟军舰队 YOR/LEX；单舰队包不受影响）
    return {
        "clock": {
            "game_time": game_state.clock.game_time.isoformat(),
        },
        # 战区摘要（顶栏日期/Z 时区显示用；无军情坐标）
        "theater": {
            "id": theater_ctx.id,
            "name": theater_ctx.name,
            "timezone_offset": theater_ctx.theater_raw.get("timezone_offset", 0),
        },
        "task_forces": [
            {
                "name": tf.name,
                "course": tf.course,
                "speed": tf.speed,
                "carriers": [
                    {
                        "name": c.name,
                        "position": {"lat": c.position.lat, "lon": c.position.lon},
                        "course": c.course,
                        "speed": c.speed,
                        "cap_strength": c.cap_strength,
                        "damage_level": c.damage_level,
                        "air_groups": [
                            {
                                "type": ag.type.value,
                                "count": ag.count,
                                "status": ag.status.value,
                                "fuel_pct": ag.fuel_pct,
                                "ammo_pct": ag.ammo_pct,
                                "squadron_name": ag.squadron_name,
                            }
                            for ag in c.air_groups
                        ],
                    }
                    for c in tf.carriers
                ],
            }
            for tf in game_state.task_forces
        ],
        "known_enemy": known_enemy_public,
        "active_scouts": [
            {
                "id": s.id,
                "direction": s.direction,
                "heading": s.heading,
                "aircraft_count": s.aircraft_count,
                "eta_minutes": s.eta_minutes,
                "status": s.status,
                "launched_at": s.launched_at.isoformat(),
                "search_bearing_min": s.search_bearing_min,
                "search_bearing_max": s.search_bearing_max,
                "phase": s.phase.value,
                "fuel_pct": s.fuel_pct,
                "aircraft_lost": s.aircraft_lost,
                "loss_reasons": s.loss_reasons,
                "position": {"lat": s.position.lat, "lon": s.position.lon} if s.position else None,
                "search_pattern": s.search_pattern.value,
            }
            for s in game_state.active_scouts
        ],
        "aircraft_losses": [
            {
                "scout_id": l.scout_id,
                "aircraft_number": l.aircraft_number,
                "reason": l.reason,
                "time": l.time.isoformat(),
            }
            for l in game_state.aircraft_losses
        ],
        "pending_reports": [
            {
                "scout_id": pr.scout_id,
                "detected_at": pr.detected_at.isoformat(),
                "arrive_at": pr.arrive_at.isoformat(),
            }
            for pr in game_state.pending_reports
        ],
        "pending_suggestions": [
            {
                "index": i,
                "npc": s.npc,
                "action_type": s.action_type,
                "details": s.details,
            }
            for i, s in enumerate(game_state.pending_suggestions)
        ],
        "incoming_messages": game_state.incoming_messages,
        "ap": ap,
        "game_phase": game_state.game_phase.value,
    }


@app.get("/npcs")
async def get_npcs():
    """Return NPC registry for frontend tab building."""
    return {
        npc_id: {
            "label": info["label"],
            "sender": info["sender"],
            "role": info["role"],
        }
        for npc_id, info in NPC_DISPLAY.items()
    }


@app.get("/npc/{npc_id}/history")
async def get_npc_history(npc_id: str):
    """Return conversation history for an NPC."""
    if npc_id not in npcs:
        raise HTTPException(404, f"NPC '{npc_id}' not found")
    return {"messages": npcs[npc_id].messages}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Send a message to an NPC and get a response."""
    if req.npc_id not in npcs:
        raise HTTPException(404, f"NPC '{req.npc_id}' not found")
    if not has_ap(game_state):
        raise HTTPException(400, "AP 已耗尽，请推进时间。")

    consume_ap(game_state, "message")
    npc = npcs[req.npc_id]

    def wrap_handler(handler):
        def wrapped(**kwargs):
            return handler(game_state, **kwargs)
        return wrapped

    try:
        response = npc.chat(
            player_input=req.message,
            state=game_state,
            tools=npc.tools,
            tool_handlers={n: wrap_handler(h) for n, h in npc.tool_handlers.items()},
        )
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(500, f"通信错误: {e}")

    return {
        "text": response.text,
        "mood": response.mood,
        "urgency": response.urgency,
        "ap": get_ap_status(game_state),
    }


@app.post("/advance")
async def advance(req: AdvanceRequest):
    """Advance the game clock by N minutes via the Pipeline."""
    if game_state.game_phase == GamePhase.GAME_OVER:
        return {
            "notifications": ["Game is already over."],
            "ap": get_ap_status(game_state),
            "game_over": True,
        }
    notifications = pipeline.execute(game_state, req.minutes)
    return {
        "notifications": notifications,
        "ap": get_ap_status(game_state),
        "game_over": game_state.game_phase == GamePhase.GAME_OVER,
    }


@app.post("/suggestion/{index}/approve")
async def approve_suggestion(index: int):
    """Approve and execute a pending suggestion."""
    if index < 0 or index >= len(game_state.pending_suggestions):
        raise HTTPException(404, "方案不存在。")

    sug = game_state.pending_suggestions[index]
    result = handle_execute_action(game_state, sug.action_type, sug.details)
    game_state.pending_suggestions.pop(index)
    return {"result": result}


@app.post("/suggestion/{index}/reject")
async def reject_suggestion(index: int):
    """Reject a pending suggestion."""
    if index < 0 or index >= len(game_state.pending_suggestions):
        raise HTTPException(404, "方案不存在。")

    game_state.pending_suggestions.pop(index)
    return {"result": "方案已驳回。"}



@app.post("/plan-strike")
async def plan_strike_endpoint(enemy_report_id: int = 0):
    """Create a strike plan from a known enemy report."""
    if enemy_report_id < 0 or enemy_report_id >= len(game_state.known_enemy):
        raise HTTPException(404, "Enemy report not found.")
    enemy = game_state.known_enemy[enemy_report_id]
    enemy_report = {
        "position": {"lat": enemy.position.lat, "lon": enemy.position.lon},
        "course": 110,
        "speed": 20,
        "description": enemy.description,
        "confidence": enemy.confidence,
    }
    plan = plan_mission(game_state, enemy_report)
    return {
        "plan_id": plan.id,
        "feasible": plan.feasible,
        "npc_briefing_data": plan.npc_briefing_data,
        "warnings": plan.warnings,
    }


@app.post("/confirm-strike")
async def confirm_strike_endpoint(plan_id: str):
    """Confirm a strike plan and create an AirGroup."""
    ag = confirm_mission(game_state, plan_id)
    if not ag:
        raise HTTPException(400, "Cannot confirm strike (no ready aircraft or plan not feasible).")
    return {"group_id": ag.id, "status": ag.status.value}


@app.post("/reject-strike")
async def reject_strike_endpoint(plan_id: str):
    """Reject a strike plan."""
    reject_mission(game_state, plan_id)
    return {"status": "cancelled"}


@app.post("/recall")
async def recall_endpoint(group_id: str):
    """Recall an airborne air group."""
    notifications = recall_air_group(game_state, group_id)
    if not notifications:
        raise HTTPException(404, "Air group not found or not airborne.")
    return {"status": "returning", "notifications": notifications}


@app.post("/confirm-contact/{index}")
async def confirm_contact(index: int):
    """确认待确认的敌军标记（海图圈出确认）。

    将 pending_reports 中的指定报告转为 known_enemy。
    """
    from src.render.chart import confirm_contact as chart_confirm
    success = chart_confirm(game_state, index)
    if not success:
        raise HTTPException(404, "报告不存在或已确认。")
    return {"success": True, "message": "敌情已确认"}


# ── S2 情报接口（计划 §十：玩家查询；白名单序列化，无规则侧真值）──


def _iso(dt):
    return dt.isoformat() if dt else None


@app.get("/intel/inbox")
async def intel_inbox():
    """旗舰收报室（D1）：只含真正送达的电文（RECEIVED 及之后；LOST 永不出现）。

    S8 UI.2：补充电文详情白名单字段（时间链/路由/转述链/勘误引用）与
    关联跳转（引用该电文证据的简报与判断）。
    """
    from src.intel import service as intel_service
    # 电文 → 证据 → 简报/判断 关联索引（跳转数据，玩家可读面）
    ev_by_message: dict[str, list[str]] = {}
    for e in game_state.evidence:
        ev_by_message.setdefault(e.message_id, []).append(e.id)
    briefs_by_evidence: dict[str, list[str]] = {}
    for b in game_state.intel_briefs:
        if b.status == "draft":
            continue
        for ev_id in b.new_evidence_ids:
            briefs_by_evidence.setdefault(ev_id, []).append(b.id)
    assessments_by_evidence: dict[str, list[str]] = {}
    for a in game_state.assessments:
        for ev_id in a.based_on_evidence_ids:
            assessments_by_evidence.setdefault(ev_id, []).append(a.id)
    return {
        "messages": [
            {
                "id": m.id,
                "sender": m.sender_call_sign or m.sender_id,
                "kind": m.message_kind,
                "priority": m.priority.value,
                "status": m.status.value,
                "condition": m.condition.value,
                "observed_at": _iso(m.observed_at),
                "filed_at": _iso(m.filed_at),
                "received_at": _iso(m.received_at),
                "raw_text": m.raw_text,
                "supersedes_message_id": m.supersedes_message_id,
                # UI.2 电文详情与关联跳转（白名单）
                "origin_sender": m.origin_sender,
                "relay_chain": list(m.relay_chain),
                "routed_to": list(m.routed_to),
                "related_brief_ids": sorted({b for ev in ev_by_message.get(m.id, [])
                                             for b in briefs_by_evidence.get(ev, [])}),
                "related_assessment_ids": sorted(
                    {a for ev in ev_by_message.get(m.id, [])
                     for a in assessments_by_evidence.get(ev, [])}),
            }
            for m in intel_service.player_inbox(game_state)
        ]
    }


# ── S8 UI.3 INTEL 情报工作台（M8.4：SITREP/EVIDENCE 白名单视图）──


@app.get("/intel/sitrep")
async def intel_sitrep():
    """SITREP 态势摘要（M8.4.1）：已批准接触/最近更新/未决冲突/待处理简报。

    全部由玩家可读对象派生（ApprovedPlot/冲突登记/已呈报简报）——
    不含规则侧真值。
    """
    from src.intel.contracts import ApprovalStatus
    active_plots = [p for p in game_state.approved_plots if p.state == "active"]
    latest_approved = max(
        (p.approved_at for p in active_plots if p.approved_at), default=None)
    open_conflicts = [
        {"id": c.id, "kind": c.kind, "note": c.note, "severity": c.severity}
        for c in game_state.evidence_conflicts if c.status == "open"
    ]
    pending_briefs = [
        b for b in game_state.intel_briefs
        if b.status in (ApprovalStatus.PROPOSED.value,
                        ApprovalStatus.REVISION_REQUESTED.value,
                        ApprovalStatus.PARTIALLY_APPROVED.value)
    ]
    return {
        "approved_contacts": len(active_plots),
        "latest_approved_at": _iso(latest_approved),
        "open_conflicts": open_conflicts,
        "pending_briefs": len(pending_briefs),
        "latest_brief": next(
            ({"id": b.id, "author": b.author_actor_id,
              "narrative": b.narrative,
              "at": _iso(b.created_at)}
             for b in sorted(game_state.intel_briefs,
                             key=lambda x: x.created_at or NOW_FALLBACK(),
                             reverse=True)
             if b.status != "draft"),
            None),
    }


def NOW_FALLBACK():
    return game_state.clock.game_time


@app.get("/intel/evidence")
async def intel_evidence():
    """EVIDENCE 已呈报证据链（M8.4.4）：只显示已呈报（简报/已批准标图）引用的证据。

    玩家权限语义与 cognition.context 的 briefed/approved 装配一致；
    附使用该证据的判断（跳转数据），不含未呈报证据与规则侧真值。
    """
    from src.intel.contracts import ApprovalStatus
    briefed: set[str] = set()
    for b in game_state.intel_briefs:
        if b.status == ApprovalStatus.DRAFT.value:
            continue
        briefed.update(b.new_evidence_ids)
        for a in game_state.assessments:
            if a.id in b.changed_judgments:
                briefed.update(a.based_on_evidence_ids)
    approved_plot_ev: set[str] = set()
    approved_plot_ids = {p.plot_id for p in game_state.approved_plots}
    for p in game_state.plot_proposals:
        if p.plot_id in approved_plot_ids:
            approved_plot_ev.update(p.based_on_evidence_ids)
    visible_ids = briefed | approved_plot_ev
    used_by: dict[str, list[str]] = {}
    for a in game_state.assessments:
        for ev_id in a.based_on_evidence_ids:
            used_by.setdefault(ev_id, []).append(a.id)
    in_plots: dict[str, list[str]] = {}
    for p in game_state.plot_proposals:
        for ev_id in p.based_on_evidence_ids:
            in_plots.setdefault(ev_id, []).append(p.plot_id)
    out = []
    for e in game_state.evidence:
        if e.id not in visible_ids:
            continue
        out.append({
            "id": e.id,
            "source": e.source_id,
            "source_type": e.source_type.value,
            "received_at": _iso(e.received_at),
            "observed_at": _iso(e.observed_at),
            "summary": e.summary,
            "status": e.status.value,
            "corroboration": list(e.corroboration),
            "supersedes_evidence_id": e.supersedes_evidence_id,
            "used_by_assessment_ids": sorted(set(used_by.get(e.id, []))),
            "used_in_plot_ids": sorted(set(in_plots.get(e.id, []))),
        })
    return {"evidence": out}


# ── S8 UI.2 COMMS 收报室（M8.3：频道分区/发报草稿确认）──


def _comms_message_public(m):
    return {
        "id": m.id,
        "sender": m.sender_call_sign or m.sender_id,
        "sender_id": m.sender_id,
        "kind": m.message_kind,
        "priority": m.priority.value,
        "status": m.status.value,
        "condition": m.condition.value,
        "observed_at": _iso(m.observed_at),
        "filed_at": _iso(m.filed_at),
        "received_at": _iso(m.received_at),
        "raw_text": m.raw_text,
        "supersedes_message_id": m.supersedes_message_id,
        "origin_sender": m.origin_sender,
        "relay_chain": list(m.relay_chain),
        "routed_to": list(m.routed_to),
    }


@app.get("/comms/channels")
async def comms_channels():
    """收报室频道分区（M8.3.1；全部来自玩家可读电文，在途/丢失不可见）。"""
    from src.intel.contracts import MessageStatus as MS
    channels: dict[str, list] = {"INCOMING": [], "OUTGOING": [],
                                 "TF17_TF11": [], "CORRECTIONS": [], "ARCHIVE": []}
    for m in game_state.messages:
        is_outgoing = m.message_kind == "outgoing" and m.sender_id in ("fletcher", "player")
        # 外发电文是玩家自己的通信产物（FILED 即存档可见）；
        # 其余电文一律以 RECEIVED 起点为准（D1：在途/丢失内容不可见）
        if not is_outgoing and m.status not in intel_service_readable():
            continue
        pub = _comms_message_public(m)
        if is_outgoing:
            channels["OUTGOING"].append(pub)
        elif m.message_kind == "correction":
            channels["CORRECTIONS"].append(pub)
        elif m.relay_chain or m.origin_sender:
            channels["TF17_TF11"].append(pub)
        elif m.status in (MS.ARCHIVED, MS.CORRECTED):
            channels["ARCHIVE"].append(pub)
        else:
            channels["INCOMING"].append(pub)
    return {"channels": channels}


def intel_service_readable():
    """频道分区的可读状态集（D1：玩家可读起点=RECEIVED）。"""
    from src.intel.contracts import MessageStatus as MS
    return {MS.RECEIVED, MS.LOGGED, MS.ROUTED, MS.PROCESSED, MS.ARCHIVED,
            MS.CORRECTED}


class OutgoingDraft(BaseModel):
    raw_text: str
    priority: str = "routine"


@app.post("/comms/outgoing")
async def comms_outgoing(req: OutgoingDraft):
    """发报草稿与确认（M8.3.7）：指挥官外发电文存档（FILED）。

    外发电文是玩家自己的通信产物，存档即玩家可见（OUTGOING 频道）；
    不触发任何参谋判断或命令执行——正式命令仍走 ISSUE ORDER。
    """
    from src.intel import service as intel_service
    from src.intel.contracts import WorkPriority as WP
    from src.intel.models import MessageEnvelope
    text = req.raw_text.strip()
    if not text:
        raise HTTPException(400, "电文正文不能为空。")
    try:
        priority = WP(req.priority)
    except ValueError:
        priority = WP.ROUTINE
    msg = MessageEnvelope(
        sender_id="fletcher",
        sender_call_sign="CTF-17 FLAG",
        recipient_ids=["TF16 FLAG", "TF11 FLAG"],
        priority=priority,
        message_kind="outgoing",
        observed_at=game_state.clock.game_time,
        raw_text=text,
    )
    intel_service.file_message(game_state, msg, by="fletcher", reason="指挥官外发电报")
    return {"message": _comms_message_public(msg), "result": "已拍发存档"}


@app.get("/intel/briefs")
async def intel_briefs():
    """已呈报情报简报（PROPOSED 及之后；DRAFT 不下发）。"""
    return {
        "briefs": [
            {
                "id": b.id,
                "author": b.author_actor_id,
                "created_at": _iso(b.created_at),
                "briefed_at": _iso(b.briefed_at),
                "priority": b.priority.value,
                "status": b.status,
                "narrative": b.narrative,
                "new_evidence_ids": b.new_evidence_ids,
                "changed_judgments": b.changed_judgments,
                "unresolved_questions": b.unresolved_questions,
                "annotations": b.annotations,
            }
            for b in game_state.intel_briefs
            if b.status != "draft"
        ]
    }


@app.get("/intel/work-items")
async def intel_work_items():
    """情报工作队列（玩家可查看参谋工作状态）。"""
    from src.intel.contracts import WorkItemStatus
    return {
        "work_items": [
            {
                "id": i.id,
                "priority": i.priority.value,
                "status": i.status,
                "assigned_to": i.assigned_to,
                "trigger_message_id": i.trigger_message_id,
                "evidence_ids": i.evidence_ids,
                "created_at": _iso(i.created_at),
                "submitted_at": _iso(i.submitted_at),
                "outcome_assessment_id": i.outcome_assessment_id,
            }
            for i in game_state.intel_work_items
            if i.status not in (WorkItemStatus.CLOSED.value, WorkItemStatus.CANCELLED.value)
        ]
    }


class WorkItemRequest(BaseModel):
    pass


@app.post("/intel/work-items/{item_id}/request")
async def request_work_item(item_id: str):
    """指挥官主动要求研判（§M2.5.7 / §十）。

    情报参谋处理工作项：LLM 分析器可用则产出判断书叙述，
    否则降级为机械策略结构化产物（显式标注，非玩法路径）。
    """
    from src.intel.flow import run_intelligence_cycle
    from src.intel.contracts import WorkItemStatus
    item = next((i for i in game_state.intel_work_items if i.id == item_id), None)
    if item is None:
        raise HTTPException(404, "工作项不存在。")
    if item.status != WorkItemStatus.ASSIGNED.value:
        raise HTTPException(400, f"工作项状态 {item.status} 不可研判。")
    brief = run_intelligence_cycle(game_state, item)
    return {
        "brief_id": brief.id,
        "status": item.status,
        "assessment_id": item.outcome_assessment_id,
    }


@app.get("/intel/after-action")
async def intel_after_action():
    """战后复盘：证据—判断—批准—结果因果链（§M2.8.9，白名单字段）。"""
    from src.intel.contracts import ApprovalStatus
    chains = []
    plot_ids = {p.plot_id for p in game_state.plot_proposals}
    for plot_id in sorted(plot_ids):
        proposals = sorted(
            (p for p in game_state.plot_proposals if p.plot_id == plot_id),
            key=lambda p: p.version,
        )
        decisions = [d for d in game_state.commander_decisions
                     if d.plot_id == plot_id]
        assessment_ids = {a.id for p in proposals for a in game_state.assessments
                          if a.id in p.assessment_ids}
        assessments = [a for a in game_state.assessments
                       if a.id in assessment_ids]
        claims = [c for c in game_state.claims
                  if c.assessment_id in assessment_ids]
        evidence_ids = {e for a in assessments for e in a.based_on_evidence_ids}
        evidence = [e for e in game_state.evidence if e.id in evidence_ids]
        approved = next((ap for ap in game_state.approved_plots
                         if ap.plot_id == plot_id), None)
        chains.append({
            "plot_id": plot_id,
            "versions": [
                {
                    "version": p.version,
                    "proposal_id": p.id,
                    "status": p.status,
                    "change_summary": p.change_summary,
                    "author": p.author_actor_id,
                    "created_at": _iso(p.created_at),
                    "annotations": p.annotations,
                    "method": p.method,
                }
                for p in proposals
            ],
            "decisions": [
                {
                    "id": d.id, "at": _iso(d.at), "action": d.action,
                    "proposal_id": d.proposal_id, "comment": d.comment,
                }
                for d in decisions
            ],
            "assessments": [
                {
                    "id": a.id, "author": a.author_actor_id,
                    "narrative": a.narrative,
                    "confidence": a.confidence_dimensions,
                    "dice_record_ids": a.dice_record_ids,
                    "conflict_ids": a.conflict_ids,
                }
                for a in assessments
            ],
            "claims": [
                {"id": c.id, "type": c.claim_type, "text": c.text,
                 "actor": c.actor_id}
                for c in claims
            ],
            "evidence": [
                {"id": e.id, "source": e.source_id, "summary": e.summary,
                 "status": e.status.value, "received_at": _iso(e.received_at)}
                for e in evidence
            ],
            "approved_state": approved.state if approved else None,
            "current_version": approved.current_version if approved else None,
        })
    tool_calls = [
        {"id": t.id, "at": _iso(t.at), "actor": t.actor_id,
         "tool": t.tool_name, "evidence_ids": t.evidence_ids}
        for t in game_state.tool_calls
    ]
    dice = [
        {"id": r.check_id, "type": r.check_type, "actor": r.actor_id,
         "at": _iso(r.game_time), "seed": r.random_seed,
         "final": r.final_roll, "degree": r.degree}
        for r in game_state.check_records
    ]
    return {"chains": chains, "tool_calls": tool_calls, "check_records": dice}


# ── S2.4 标图审批接口（§十：玩家操作）──


def _proposal_public(p):
    return {
        "id": p.id,
        "plot_id": p.plot_id,
        "version": p.version,
        "author": p.author_actor_id,
        "status": p.status,
        "method": p.method,
        "geometry": p.geometry.model_dump() if p.geometry else None,
        "confidence": p.confidence,
        "change_summary": p.change_summary,
        "supersedes_version": p.supersedes_version,
        "based_on_evidence_ids": p.based_on_evidence_ids,
        "annotations": p.annotations,
        "created_at": _iso(p.created_at),
    }


def _find_proposal(proposal_id: str):
    from src.intel.models import PlotProposal
    for p in game_state.plot_proposals:
        if p.id == proposal_id:
            return p
    raise HTTPException(404, "标图提案不存在。")


@app.get("/intel/plots")
async def intel_plots():
    """标图提案（PROPOSED/REVISION_REQUESTED/PARTIALLY_APPROVED 待审 + 历史）与正式图层。"""
    from src.intel.contracts import ApprovalStatus
    pending = [
        _proposal_public(p) for p in game_state.plot_proposals
        if p.status in (ApprovalStatus.PROPOSED.value,
                        ApprovalStatus.REVISION_REQUESTED.value,
                        ApprovalStatus.PARTIALLY_APPROVED.value,
                        ApprovalStatus.DEFERRED.value)
    ]
    approved = [
        {
            "plot_id": ap.plot_id,
            "current_version": ap.current_version,
            "state": ap.state,
            "approved_at": _iso(ap.approved_at),
            "history": ap.history,
        }
        for ap in game_state.approved_plots
    ]
    return {"pending_proposals": pending, "approved_plots": approved}


@app.get("/intel/plots/{plot_id}/history")
async def intel_plot_history(plot_id: str):
    """标图链版本历史（版本比较）。"""
    from src.intel.plots import plot_chain_history
    return {"plot_id": plot_id, "versions": plot_chain_history(game_state, plot_id)}


class PlotDecisionRequest(BaseModel):
    comment: str = ""
    items_approved: list[str] = []


@app.post("/intel/plots/{proposal_id}/approve")
async def approve_plot(proposal_id: str, req: PlotDecisionRequest | None = None):
    from src.intel import plots as plotsvc
    proposal = _find_proposal(proposal_id)
    comment = req.comment if req else ""
    plotsvc.decide(game_state, proposal, action="approve", by="player",
                   comment=comment)
    return {"proposal": _proposal_public(proposal), "result": "已批准上图"}


@app.post("/intel/plots/{proposal_id}/reject")
async def reject_plot(proposal_id: str, req: PlotDecisionRequest | None = None):
    from src.intel import plots as plotsvc
    proposal = _find_proposal(proposal_id)
    comment = req.comment if req else ""
    plotsvc.decide(game_state, proposal, action="reject", by="player",
                   comment=comment)
    return {"proposal": _proposal_public(proposal), "result": "已驳回"}


@app.post("/intel/plots/{proposal_id}/defer")
async def defer_plot(proposal_id: str, req: PlotDecisionRequest | None = None):
    from src.intel import plots as plotsvc
    proposal = _find_proposal(proposal_id)
    plotsvc.decide(game_state, proposal, action="defer", by="player")
    return {"proposal": _proposal_public(proposal), "result": "已暂缓"}


@app.post("/intel/plots/{proposal_id}/request-revision")
async def request_plot_revision(proposal_id: str, req: PlotDecisionRequest | None = None):
    from src.intel import plots as plotsvc
    proposal = _find_proposal(proposal_id)
    comment = req.comment if req else ""
    plotsvc.decide(game_state, proposal, action="request_revision", by="player",
                   comment=comment)
    return {"proposal": _proposal_public(proposal), "result": "已要求修订"}


# ── Theater context 下发（CHART_SYSTEM.md §四：前端 ChartEngine 唯一消费者）──


@app.get("/theater")
async def get_theater():
    """下发战区包合并 JSON（theater.json + geography.geojson 原样）。"""
    return {
        "theater": theater_ctx.theater_raw,
        "geography": theater_ctx.geography,
    }


# ── 战役选择（O.1：theaters/ 包发现 + 开新局重建）──


def _iter_theater_packs():
    """扫描 theaters/ 目录：含 theater.json + scenario.json 的包目录（id 序）。"""
    root = BASE_DIR / "theaters"
    for pack_dir in sorted(root.iterdir()):
        if pack_dir.is_dir() \
                and (pack_dir / "theater.json").exists() \
                and (pack_dir / "scenario.json").exists():
            yield pack_dir


def _read_theater_json(pack_dir: Path) -> dict:
    return json.loads((pack_dir / "theater.json").read_text(encoding="utf-8"))


def _scenario_summary(scenario: dict) -> dict:
    """scenario.json → 开局层摘要：双方兵力名 + 胜利条件（不含坐标军情）。"""
    enemy = scenario.get("enemy_fleet", {})
    return {
        "friendly_forces": [
            {
                "callsign": tf.get("callsign"),
                "name": tf.get("name"),
                "carriers": [c.get("name") for c in tf.get("carriers", [])],
            }
            for tf in scenario.get("task_forces", [])
        ],
        "enemy_force": {
            "name": enemy.get("name"),
            "carriers": list(enemy.get("carriers", [])),
        },
        "victory": scenario.get("victory", {}),
    }


@app.get("/theaters")
async def list_theaters():
    """战役选择列表：theaters/ 全包摘要（O.2 起珊瑚海等包自动入列）。"""
    theaters = []
    for pack_dir in _iter_theater_packs():
        theater = _read_theater_json(pack_dir)
        scenario = json.loads((pack_dir / "scenario.json").read_text(encoding="utf-8"))
        view = theater.get("view", {})
        theaters.append({
            "id": theater["id"],
            "name": theater["name"],
            "date": theater.get("date"),
            "view": view.get("center"),
            "view_nm": view.get("view_nm"),
            "scenario": _scenario_summary(scenario),
        })
    return {"theaters": theaters}


@app.post("/game/new")
async def new_game(req: NewGameRequest):
    """开新局：按战区包 scenario 重建 GameState（O.1）。

    build_initial_state 每次现读 scenario.json（M.4 布兵唯一来源，可重入）——
    重置即整体重建：时钟/AP/敌情（known+actual）/航线/提案全部回到初始态；
    NPC 会话清空，航海参谋战区上下文热替换。
    """
    pack_dir = None
    for candidate in _iter_theater_packs():
        if _read_theater_json(candidate).get("id") == req.theater_id:
            pack_dir = candidate
            break
    if pack_dir is None:
        raise HTTPException(404, f"战区 '{req.theater_id}' 不存在。")

    global game_state, theater_ctx
    theater_ctx = load_theater(pack_dir)  # 包校验失败抛 ValueError（fail-fast 同启动语义）
    # O.3：按所选包 scenario 重建（缺省 midway 走既有历史开局路径，多岛包走通用构建）
    game_state = build_initial_state(pack_dir / "scenario.json")

    for npc in npcs.values():
        npc.messages = []  # NPC 会话清空（每 NPC 独立 LLM 会话历史）
    # 航海参谋战区热替换（theater 为无 setter 的 property；navigator.py 在本任务白名单外）
    npcs["navigator"]._theater = theater_ctx

    return {
        "ok": True,
        "state": {
            "theater_id": theater_ctx.id,
            "clock": {"game_time": game_state.clock.game_time.isoformat()},
            "ap": get_ap_status(game_state),
            "task_forces": [
                {
                    "name": tf.name,
                    "carriers": [
                        {
                            "name": c.name,
                            "position": {"lat": c.position.lat, "lon": c.position.lon},
                        }
                        for c in tf.carriers
                    ],
                }
                for tf in game_state.task_forces
            ],
        },
    }


# ── Chart routes (CHART_SYSTEM.md §5.1：三类航线 planned/mission/track) ──


def _find_route(route_id: str) -> Route:
    for r in game_state.routes:
        if r.id == route_id:
            return r
    raise HTTPException(404, "航线不存在。")


@app.post("/routes")
async def create_route(req: CreateRouteRequest):
    """创建草案航线（draft）。"""
    route = Route(kind=req.kind, owner=req.owner, waypoints=req.waypoints)
    game_state.routes.append(route)
    return route.model_dump(mode="json")


@app.get("/routes")
async def list_routes():
    """列出全部航线。"""
    return {"routes": [r.model_dump(mode="json") for r in game_state.routes]}


@app.post("/routes/{route_id}/approve")
async def approve_route(route_id: str):
    """批准草案航线（draft → active）。"""
    route = _find_route(route_id)
    if route.status != RouteStatus.DRAFT:
        raise HTTPException(400, "仅草案航线可批准。")
    route.status = RouteStatus.ACTIVE
    return route.model_dump(mode="json")


@app.post("/routes/{route_id}/cancel")
async def cancel_route(route_id: str):
    """撤销航线（draft/active → cancelled）。"""
    route = _find_route(route_id)
    if route.status not in (RouteStatus.DRAFT, RouteStatus.ACTIVE):
        raise HTTPException(400, "该航线不可撤销。")
    route.status = RouteStatus.CANCELLED
    return route.model_dump(mode="json")


@app.post("/routes/{route_id}/comment")
async def comment_route(route_id: str, req: RouteCommentRequest):
    """指挥官提修改意见 → 航海参谋修订提案（N.3 多轮回路）。

    找到该 route 关联的最新 proposed 提案，把 feedback 作为玩家消息
    追加进航海参谋会话；参谋带 feedback 修订（LLM 调用）产出新
    PendingRoute：旧条目置 revised，新条目 proposed 且关联同一
    route_id，feedback_history 累积全量意见。消耗 1 AP（对齐 propose）。
    """
    target = None
    for p in game_state.pending_routes:
        if p.route_id == route_id and p.status == PendingRouteStatus.PROPOSED:
            target = p  # 同链取最新一条 proposed
    if target is None:
        raise HTTPException(404, "该航线无待修订提案。")
    if not has_ap(game_state):
        raise HTTPException(400, "AP 已耗尽，请推进时间。")
    consume_ap(game_state, "comment")

    npc = npcs["navigator"]

    def wrap_handler(handler):
        def wrapped(**kwargs):
            return handler(game_state, **kwargs)
        return wrapped

    existing_ids = {p.id for p in game_state.pending_routes}
    try:
        response = npc.chat(
            player_input=req.feedback,
            state=game_state,
            tools=npc.tools,
            tool_handlers={n: wrap_handler(h) for n, h in npc.tool_handlers.items()},
        )
    except Exception as e:
        logger.error(f"Navigator comment error: {e}", exc_info=True)
        raise HTTPException(500, f"通信错误: {e}")

    # 修订产出：新条目挂到同一 route_id 并累积意见；有产出才置旧条目 revised
    created = [p for p in game_state.pending_routes if p.id not in existing_ids]
    for p in created:
        p.route_id = route_id
        p.feedback_history = [*target.feedback_history, req.feedback]
    if created:
        target.status = PendingRouteStatus.REVISED

    return {
        "text": response.text,
        "mood": response.mood,
        "urgency": response.urgency,
        "revised_pending_id": created[0].id if created else None,
        "pending_routes": [
            p.model_dump(mode="json") for p in game_state.pending_routes
        ],
        "ap": get_ap_status(game_state),
    }


# ── 航海参谋提案审批流（N.3：propose → pending_routes → approve/reject）──


@app.post("/navigator/propose")
async def navigator_propose(req: NavigatorProposeRequest):
    """航海参谋会话端点（真实 LLM）；propose_route 工具写入 pending_routes。"""
    if not has_ap(game_state):
        raise HTTPException(400, "AP 已耗尽，请推进时间。")

    consume_ap(game_state, "message")
    npc = npcs["navigator"]

    def wrap_handler(handler):
        def wrapped(**kwargs):
            return handler(game_state, **kwargs)
        return wrapped

    try:
        response = npc.chat(
            player_input=req.message,
            state=game_state,
            tools=npc.tools,
            tool_handlers={n: wrap_handler(h) for n, h in npc.tool_handlers.items()},
        )
    except Exception as e:
        logger.error(f"Navigator chat error: {e}", exc_info=True)
        raise HTTPException(500, f"通信错误: {e}")

    return {
        "text": response.text,
        "mood": response.mood,
        "urgency": response.urgency,
        "pending_routes": [
            p.model_dump(mode="json") for p in game_state.pending_routes
        ],
        "ap": get_ap_status(game_state),
    }


def _find_pending_route(pending_id: str) -> PendingRoute:
    for p in game_state.pending_routes:
        if p.id == pending_id:
            return p
    raise HTTPException(404, "航线提案不存在。")


@app.get("/pending-routes")
async def list_pending_routes():
    """列出全部航线提案。"""
    return {
        "pending_routes": [
            p.model_dump(mode="json") for p in game_state.pending_routes
        ]
    }


@app.post("/pending-routes/{pending_id}/approve")
async def approve_pending_route(pending_id: str):
    """批准提案：PendingRoute 转 Route 落 state.routes（status=active）。"""
    pending = _find_pending_route(pending_id)
    if pending.status not in (PendingRouteStatus.PROPOSED, PendingRouteStatus.REVISED):
        raise HTTPException(400, "该提案已处理。")
    route = pending_to_route(pending)
    game_state.routes.append(route)
    pending.status = PendingRouteStatus.APPROVED
    return {
        "route": route.model_dump(mode="json"),
        "pending_route": pending.model_dump(mode="json"),
    }


@app.post("/pending-routes/{pending_id}/reject")
async def reject_pending_route(pending_id: str):
    """驳回提案：置 rejected，不产生 Route。"""
    pending = _find_pending_route(pending_id)
    if pending.status not in (PendingRouteStatus.PROPOSED, PendingRouteStatus.REVISED):
        raise HTTPException(400, "该提案已处理。")
    pending.status = PendingRouteStatus.REJECTED
    return pending.model_dump(mode="json")
