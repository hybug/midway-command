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
from src.cognition.persona import render_report
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

# ── S4 运行名册（theaters/<id>/roster.json；换战区热替换）──
from src.staff.roster import MIDWAY_THEATER_ID, load_run_roster, set_active_roster

staff_roster = load_run_roster(MIDWAY_THEATER_ID)
set_active_roster(staff_roster)

# ── Theater context (CHART_SYSTEM.md §三/§四/§九决议6：后端单一下发) ──
from src.theater import load_theater

# fail-fast：战区包损坏则拒绝启动
theater_ctx = load_theater(BASE_DIR / "theaters" / "midway")

from src.staff import service as staff_service

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
    """DEPRECATED（AS.1/R2）：地图点击确认敌情的公共旁路已关闭。

    正式接触只能经 PlotProposal → CommanderDecision → ApprovedPlot（INTEL 审图）；
    旧调用一律拒绝，不迁移数据。
    """
    raise HTTPException(
        410, "confirm-contact 旁路已关闭（AS.1/R2）：接触确认走 PlotProposal → INTEL 审图。")


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


# ── S8 UI.4 STAFF 参谋工作台（M8.5：名册/正式判断/极简档案）──


def _make_generator(actor):
    """候选生成工厂：LLM 可用则人物化生成；不可用由调用方降级（测试可替换）。"""
    from src.cognition.persona import LLMCandidateGenerator
    return LLMCandidateGenerator(actor)


def _render_for(actor, task, result, hypotheses, client=None):
    """人物化渲染（测试可替换）；无 LLM 时 render_report 内部走机械降级。"""
    from src.cognition.persona import render_report
    if client is None:
        try:
            from src.llm import get_client
            client = get_client()
        except Exception:
            client = None
    return render_report(actor, task, result, hypotheses, client=client)


def _result_public(r):
    return {
        "id": r.id,
        "task_id": r.task_id,
        "actor_id": r.actor_id,
        "chosen_hypothesis_id": r.chosen_hypothesis_id,
        "plausible_hypothesis_ids": r.plausible_hypothesis_ids,
        "confidence_band": r.confidence_band,
        "error_type": r.error_type,
        "error_severity": r.error_severity,
        "recommendation": r.recommendation,
        "assumptions": r.assumptions,
        "change_my_mind": r.change_my_mind,
        "refusal_reason": r.refusal_reason,
        "created_at": _iso(r.created_at),
        "supersedes_result_id": r.supersedes_result_id,
    }


def _hypotheses_public(audit):
    return [
        {
            "id": h.get("id"), "text": h.get("text"),
            "predicted_class": h.get("predicted_class"),
            "assumptions": h.get("assumptions", []),
        }
        for h in (audit.hypotheses if audit else [])
    ]


@app.get("/staff/roster")
async def staff_roster():
    """参谋名册（M8.5.1/M8.5.5 极简档案）：身份/状态/关注/最近互动。

    白名单红线：不输出 competence 等内部参数、不输出他人私有判断记忆。
    """
    from src.cognition.roster import CORAL_SEA_ACTORS
    staff = []
    for actor_id, display in NPC_DISPLAY.items():
        staff.append({
            "actor_id": actor_id,
            "display_name": display["sender"],
            "role": display["role"],
            "source": "chat",
            "dossier": {
                "status_line": "在舱待命",
                "current_focus": "—",
                "recent": [],
            },
        })
    for actor in CORAL_SEA_ACTORS:
        if actor.is_player:
            # 玩家本人不进名册（指挥官不给自己写档案）
            continue
        memories = [m for m in reversed(game_state.judgment_memories)
                    if m.actor_id == actor.actor_id]
        open_mem = next((m for m in memories
                         if m.status == "open" and m.selected_hypothesis), None)
        last_feedback = next((m for m in memories if m.commander_decision), None)
        status_line = "在舱待命"
        if last_feedback and memories and memories[0] is last_feedback:
            status_line = f"指挥官已{FEEDBACK_CN.get(last_feedback.commander_decision, '回应')}其最新建议"
        elif open_mem:
            status_line = "已呈报判断，待指挥官指示"
        elif memories:
            status_line = "判断已被修订，观察新证据"
        current_focus = "—"
        if open_mem:
            result = next((r for r in game_state.judgment_results
                           if r.id == open_mem.result_id), None)
            task = next((t for t in game_state.judgment_tasks
                         if t.id == (result.task_id if result else "")), None)
            if task:
                current_focus = task.question_normalized[:40]
        recent = []
        # S3.7：指挥权变化（OTC）入档案（自然语言，非数值）
        for entry in game_state.intel_audit:
            if entry.action == "otc_change" and entry.target_id == actor.actor_id:
                recent.append({
                    "at": _iso(entry.at),
                    "kind": "otc",
                    "note": entry.reason or "被指定为战术指挥官（OTC）",
                })
        if last_feedback:
            recent.append({
                "at": _iso(last_feedback.created_at),
                "kind": "feedback",
                "note": f"指挥官{FEEDBACK_CN.get(last_feedback.commander_decision, '反馈')}其对「"
                        f"{(last_feedback.revision_reason or '此前判断')[:24]}」的处理",
            })
        if open_mem:
            recent.append({
                "at": _iso(open_mem.created_at),
                "kind": "judgment",
                "note": "就当前关注呈报正式判断",
            })
        staff.append({
            "actor_id": actor.actor_id,
            "display_name": actor.display_name,
            "role": actor.role,
            "domain": actor.domain,
            "source": "judgment",
            "dossier": {
                "status_line": status_line,
                "current_focus": current_focus,
                "recent": recent[:2],        # 极简档案：最近两次互动
            },
        })
    return {"staff": staff}


# ── S4 参谋班子（联络名单/主动提醒/指挥链报告；M8.5 数据源升级）──


def _channel_public(ch):
    return {
        "actor_id": ch.actor_id,
        "display_name": ch.display_name,
        "rank": ch.rank,
        "role": ch.role,
        "flagship": ch.flagship,
        "contact_permission": ch.contact_permission.value,
        "can_be_summoned": ch.can_be_summoned,
        "can_initiate": ch.can_initiate,
        "evidence_grade": ch.evidence_grade,
        "source_ids": list(ch.source_ids),
        "note": ch.note,
    }


@app.get("/staff/channels")
async def staff_channels():
    """直接沟通名单（S4.1）：scenario roster 决定；含未处理通知 id。"""
    open_by_actor = {n.actor_id: n.id for n in staff_service.open_notices(game_state)}
    return {"channels": [
        {**_channel_public(ch), "active_notice_id": open_by_actor.get(ch.actor_id)}
        for ch in staff_roster.contact_channels
    ]}


@app.get("/staff/notices")
async def staff_notices():
    """主动提醒（S4.3）：全部非关闭通知（open/acknowledged/deferred）。"""
    return {"notices": [
        {
            "id": n.id,
            "actor_id": n.actor_id,
            "topic": n.topic,
            "priority": n.priority.value,
            "reason": n.notice_reason.value,
            "state": n.state.value,
            "created_at": _iso(n.created_at),
            "cooldown_until": _iso(n.cooldown_until),
            "source_type": n.source_type,
            "source_id": n.source_id,
        }
        for n in game_state.staff_notices
        if n.state not in ("resolved", "expired")
    ]}


@app.post("/staff/notices/{notice_id}/{action}")
async def staff_notice_action(notice_id: str, action: str):
    """接见/暂缓/忽略/关闭（固定动作枚举，AS 语义）。"""
    notice = next((n for n in game_state.staff_notices if n.id == notice_id), None)
    if notice is None:
        raise HTTPException(404, "通知不存在。")
    try:
        staff_service.dismiss_notice(game_state, staff_roster, notice,
                                     action=action, by="fletcher")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"notice": {"id": notice.id, "state": notice.state.value,
                       "cooldown_until": _iso(notice.cooldown_until)}}


@app.get("/staff/visit-events")
async def staff_visit_events():
    """STAFF_VISIT 通知源（s4Adapter 消费；open 通知 → 事件形状）。"""
    return {"visits": staff_service.visit_events(game_state)}


@app.get("/staff/reports")
async def staff_reports():
    """指挥链报告（S4.2）：只显示已送达（未送达不暴露）。"""
    return {"reports": [
        {
            "id": r.id,
            "origin_actor_id": r.origin_actor_id,
            "current_holder_id": r.current_holder_id,
            "state": r.state.value,
            "source_type": r.source_type,
            "source_id": r.source_id,
            "summary": r.summary,
            "priority": r.priority,
            "at": _iso(r.at),
            "delivered_at": _iso(r.delivered_at),
            "annotations": list(r.annotations),
            "route": list(r.route),
        }
        for r in staff_service.delivered_reports(game_state)
    ]}


FEEDBACK_CN = {
    "approve": "批准", "reject": "驳回", "defer": "暂缓",
    "request_revision": "要求修订", "partial_approve": "部分批准",
}


class JudgmentTaskRequest(BaseModel):
    actor_id: str
    question: str
    domain: str = ""          # 缺省用角色 domain
    evidence_ids: list[str] = []   # 缺省=该角色权限内全部


def _run_judgment(actor, question: str, domain: str = "",
                  evidence_ids: Optional[list[str]] = None,
                  revision_reason: str = "",
                  supersedes_task_id: Optional[str] = None,
                  context_version: int = 1):
    """创建 JudgmentTask 并经规则引擎执行（恰好一次检定），返回 (task, result)。"""
    from src.cognition import context as cognition
    from src.cognition.memory import recall_relevant_memories
    from src.cognition.models import JudgmentContext, JudgmentTask
    from src.cognition.rule_engine import RuleJudgmentEngine
    views = cognition.actor_evidence_views(game_state, actor)
    if evidence_ids:
        allow = set(evidence_ids)
        views = [v for v in views if v.evidence_id in allow]
    memories = recall_relevant_memories(
        game_state, actor.actor_id,
        evidence_ids=[v.evidence_id for v in views])
    ctx = JudgmentContext(
        actor=actor, evidence=views, memories=memories,
        now=game_state.clock.game_time,
        duty_boundary=list(actor.duty_boundary),
    )
    task = JudgmentTask(
        task_type="assess", domain=domain or actor.domain,
        actor_id=actor.actor_id, question=question,
        evidence_ids=[v.evidence_id for v in views],
        context_version=context_version,
        source="revision" if supersedes_task_id else "commander",
        supersedes_task_id=supersedes_task_id,
        revision_reason=revision_reason or None,
    )
    engine = RuleJudgmentEngine(game_state, _make_generator(actor))
    return task, engine.assess(task, ctx)


@app.post("/judgment/tasks")
async def create_judgment_task(req: JudgmentTaskRequest):
    """指挥官要求正式判断（§7.3 用户流程）：JudgmentTask → 结果 + 人物化报告。"""
    from src.cognition.roster import get_actor
    try:
        actor = get_actor(req.actor_id)
    except KeyError:
        raise HTTPException(404, f"参谋 '{req.actor_id}' 不在名册中。")
    if not req.question.strip():
        raise HTTPException(400, "判断问题不能为空。")
    task, result = _run_judgment(actor, req.question.strip(), domain=req.domain,
                                 evidence_ids=req.evidence_ids)
    audit = next((a for a in game_state.judgment_audits
                  if a.result_id == result.id), None)
    report = _render_for(actor, task, result, _hypotheses_public(audit))
    game_state.judgment_reports[result.id] = report
    return {
        "result": _result_public(result),
        "hypotheses": _hypotheses_public(audit),
        "report": report,
    }


@app.get("/judgment/results/{result_id}")
async def judgment_result_detail(result_id: str):
    result = next((r for r in game_state.judgment_results if r.id == result_id), None)
    if result is None:
        raise HTTPException(404, "判断结果不存在。")
    audit = next((a for a in game_state.judgment_audits
                  if a.result_id == result_id), None)
    return {
        "result": _result_public(result),
        "hypotheses": _hypotheses_public(audit),
        "report": game_state.judgment_reports.get(result_id, ""),
    }


@app.get("/npcs/{npc_id}/judgments")
async def npc_judgments(npc_id: str):
    """某参谋的正式判断历史（旧版本完整保留，追加制）。"""
    results = [r for r in game_state.judgment_results if r.actor_id == npc_id]
    audits = {a.result_id: a for a in game_state.judgment_audits}
    return {
        "judgments": [
            {
                "result": _result_public(r),
                "hypotheses": _hypotheses_public(audits.get(r.id)),
                "report": game_state.judgment_reports.get(r.id, ""),
            }
            for r in results
        ]
    }


class ReconsiderRequest(BaseModel):
    reason: str = ""
    new_evidence_ids: list[str] = []


@app.post("/npcs/{npc_id}/judgments/{result_id}/reconsider")
async def reconsider_judgment(npc_id: str, result_id: str,
                              req: ReconsiderRequest):
    """要求重判（§十二）：只有新证据或反馈才允许创建新版本（D9/M3.6.4）。"""
    from src.cognition.memory import create_revision_task
    from src.cognition.roster import get_actor
    try:
        actor = get_actor(npc_id)
    except KeyError:
        raise HTTPException(404, f"参谋 '{npc_id}' 不在名册中。")
    result = next((r for r in game_state.judgment_results if r.id == result_id), None)
    if result is None or result.actor_id != npc_id:
        raise HTTPException(404, "判断结果不存在。")
    old_task = next((t for t in game_state.judgment_tasks
                     if t.id == result.task_id), None)
    if old_task is None:
        raise HTTPException(404, "原判断任务不存在。")
    if not req.new_evidence_ids and not req.reason.strip():
        raise HTTPException(400, "重判必须引用新证据或反馈理由。")
    task, new_result = _run_judgment(
        actor, old_task.question, domain=old_task.domain,
        evidence_ids=None,   # 权限内证据全量装配（新证据到达后自然进入视图）
        revision_reason=req.reason.strip() or "新证据到达",
        supersedes_task_id=old_task.id,
        context_version=old_task.context_version + 1,   # 新稳定键（D9 不被缓存绕过）
    )
    # 证据并集已由 create_revision_task 处理？——_run_judgment 直建任务；
    # 此处补修订链语义：新结果记录 supersedes
    new_result.supersedes_result_id = result.id
    audit = next((a for a in game_state.judgment_audits
                  if a.result_id == new_result.id), None)
    report = _render_for(actor, task, new_result, _hypotheses_public(audit))
    game_state.judgment_reports[new_result.id] = report
    return {
        "result": _result_public(new_result),
        "hypotheses": _hypotheses_public(audit),
        "report": report,
    }


# ── S8 UI.6 S3/S4 联动（指挥官反馈端点保留；玩家转述链已按 AS.1/R3 移除）──


class RelayRequest(BaseModel):
    pass


@app.post("/staff/relay")
async def staff_relay(req: RelayRequest):
    """DEPRECATED（AS.1/R3）：玩家转述的公开入口已删除。

    v0 下级信息只按指挥链自动上呈（S4 ChainReport）；跨参谋自由通信、互评、
    复核与分歧均延期。未来若恢复，必须使用固定 intent 与明确权限。
    """
    raise HTTPException(410, "玩家转述入口已移除（AS.1/R3）：下级信息按指挥链上呈（S4）。")


@app.get("/staff/relays")
async def staff_relays():
    """DEPRECATED（AS.1/R3）。"""
    raise HTTPException(410, "玩家转述入口已移除（AS.1/R3）。")


class FeedbackRequest(BaseModel):
    decision: str
    note: str = ""


@app.post("/judgment/results/{result_id}/feedback")
async def judgment_feedback(result_id: str, req: FeedbackRequest):
    """指挥官对判断的反馈（§8.3/D10）：进记忆，不改写原结果。"""
    from src.cognition.memory import record_commander_feedback
    try:
        memory = record_commander_feedback(
            game_state, result_id, req.decision, by="fletcher", note=req.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if memory is None:
        raise HTTPException(404, "判断结果不存在或无对应记忆。")
    return {"memory_id": memory.id, "decision": req.decision,
            "result": "反馈已记录（原结果不变）"}


# ── S8 UI.5 LOG 与复盘（M8.6：时间线/命令链/战后案卷）──


def _actual_reference_dict(state):
    """战后复盘真值参照（D11：只在此构造，产物只有误差结论，无真值字符串）。"""
    for enemy in state.actual_enemy:
        carriers = enemy.get("carriers", [])
        pos = enemy.get("position", {})
        if carriers:
            return {
                "classification": "CV",
                "count": len(carriers),
                "position": (pos.get("lat"), pos.get("lon")),
            }
    return {}


@app.get("/log/timeline")
async def log_timeline():
    """统一事件时间线（M8.6.1）：电报/判断/批准/反馈/OTC/S4 冲突——追加制可回溯。"""
    from src.intel.contracts import MessageStatus
    events = []
    for m in game_state.messages:
        if m.status not in {MessageStatus.RECEIVED, MessageStatus.LOGGED,
                            MessageStatus.ROUTED, MessageStatus.PROCESSED,
                            MessageStatus.ARCHIVED, MessageStatus.CORRECTED}:
            continue
        events.append({
            "at": _iso(m.received_at or m.filed_at),
            "kind": "message",
            "ref_id": m.id,
            "actor": m.sender_call_sign or m.sender_id,
            "text": (m.raw_text or "")[:60],
            "jump": {"workbench": "COMMS", "target": m.id},
        })
    for r in game_state.judgment_results:
        events.append({
            "at": _iso(r.created_at),
            "kind": "judgment",
            "ref_id": r.id,
            "actor": r.actor_id,
            "text": f"正式判断（{r.confidence_band}）"
                    + (f" · {r.refusal_reason}" if r.refusal_reason else ""),
            "jump": {"workbench": "STAFF", "target": r.actor_id},
        })
    for d in game_state.commander_decisions:
        events.append({
            "at": _iso(d.at),
            "kind": "plot_decision",
            "ref_id": d.id,
            "actor": "player",
            "text": f"标图 {d.plot_id} · {d.action} · {d.comment[:40]}",
            "jump": {"workbench": "INTEL", "target": d.plot_id},
        })
    for a in game_state.intel_audit:
        if a.action == "commander_feedback":
            events.append({
                "at": _iso(a.at), "kind": "commander_feedback",
                "ref_id": a.target_id, "actor": a.actor_id,
                "text": a.reason[:60],
                "jump": {"workbench": "STAFF", "target": a.actor_id},
            })
        elif a.action == "otc_change":
            events.append({
                "at": _iso(a.at), "kind": "otc_change",
                "ref_id": a.target_id, "actor": a.actor_id,
                "text": a.reason[:60],
                "jump": {"workbench": "STAFF", "target": a.target_id},
            })
        elif a.action == "player_relay":
            events.append({
                "at": _iso(a.at), "kind": "player_relay",
                "ref_id": a.target_id, "actor": a.actor_id,
                "text": a.reason[:60],
                "jump": {"workbench": "STAFF", "target": a.target_id},
            })
    events.sort(key=lambda e: e["at"] or "")
    # S4 冲突事件（引擎未实施：经前端适配器补充；v0 为空集合，字段契约在案）
    return {"events": events, "s4_events": []}


@app.get("/log/after-action")
async def log_after_action():
    """战后案卷（M8.6.5-6）：S2 因果链 + S3 认知错误/事实误差分离报告。

    真值只在服务端本调用内用于误差计算（D11），下发负载只含误差结论。
    """
    from src.cognition.errors import after_action_error_report
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
    # S3 判断的复盘数据 + 认知/事实误差分离
    judgments = [
        {
            "result": _result_public(r),
            "report": game_state.judgment_reports.get(r.id, ""),
        }
        for r in game_state.judgment_results
    ]
    actual = _actual_reference_dict(game_state)
    error_report = [r.model_dump() for r in
                    after_action_error_report(game_state, actual)]
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
    return {"chains": chains, "judgments": judgments,
            "error_report": error_report,
            "tool_calls": tool_calls, "check_records": dice}


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

    global game_state, theater_ctx, staff_roster
    theater_ctx = load_theater(pack_dir)  # 包校验失败抛 ValueError（fail-fast 同启动语义）
    # O.3：按所选包 scenario 重建（缺省 midway 走既有历史开局路径，多岛包走通用构建）
    game_state = build_initial_state(pack_dir / "scenario.json")
    # S4：运行名册随战区热替换
    staff_roster = load_run_roster(req.theater_id)
    set_active_roster(staff_roster)

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


# ── S5 命令系统（统一 Order；命令端点不直接修改舰队状态——Pipeline 生效）──


class OrderCreateRequest(BaseModel):
    order_type: str
    target_refs: list[str] = []
    parameters: dict = {}
    commander_intent_text: str
    authority_mode: str = "exact"
    priority: str = "routine"
    source_refs: list[str] = []


class OrderIssueRequest(BaseModel):
    supersede_ids: list[str] = []


class OrderUpdateRequest(BaseModel):
    parameters: dict | None = None
    commander_intent_text: str | None = None
    target_refs: list[str] | None = None
    priority: str | None = None


class OrderDraftRequest(BaseModel):
    text: str


@app.get("/orders/catalog")
async def orders_catalog():
    """可用命令目录（AS.0 AvailableAction：UI 不硬编码动作，从后端获取）。"""
    from src.actions.contracts import ActionType, AvailableAction
    catalog = [
        AvailableAction(
            action_type=ActionType.SET_COURSE, label="改变航向（EXACT）",
            required_options=["course"],
            requires_confirmation=True),
        AvailableAction(
            action_type=ActionType.LAUNCH_SCOUT, label="放飞侦察（INTENT）",
            required_options=["search_objective", "search_area",
                              "max_range_nm", "time_window"],
            requires_confirmation=True),
    ]
    return {"actions": [a.model_dump() for a in catalog]}


@app.post("/orders/draft")
async def orders_nl_draft(req: OrderDraftRequest):
    """自然语言 → 可编辑草稿（S5.2）：只能生成草稿，绝不签发或执行。"""
    from src.orders import service as orders_service
    drafts = orders_service.draft_from_text(game_state, req.text)
    return {
        "drafts": [_order_public(d) for d in drafts],
        "note": "草稿需逐条确认签发；文本与参数冲突时请修改后再签发。",
    }


@app.post("/orders")
async def create_order(req: OrderCreateRequest):
    """创建 Order 草稿（表单优先路径）。"""
    from src.orders import service as orders_service
    try:
        order = orders_service.create_draft(
            game_state, order_type=req.order_type, target_refs=req.target_refs,
            parameters=req.parameters,
            commander_intent_text=req.commander_intent_text,
            authority_mode=req.authority_mode, priority=req.priority,
            source_refs=req.source_refs)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"order": _order_public(order)}


def _order_public(o):
    return {
        "id": o.id,
        "order_type": o.order_type.value,
        "target_refs": list(o.target_refs),
        "parameters": dict(o.parameters),
        "commander_intent_text": o.commander_intent_text,
        "authority_mode": o.authority_mode.value,
        "priority": o.priority,
        "status": o.status.value,
        "reported_status": o.reported_status,
        "responsible_role": o.responsible_role,
        "plan": o.plan,
        "result_summary": (o.result or {}).get("summary"),
    }


@app.get("/orders")
async def list_orders():
    """玩家视图：reported_status 与内部 status 分离（§十一）。"""
    from src.orders import service as orders_service
    return {"orders": list(orders_service.player_view(game_state).values())}


@app.get("/orders/{order_id}/audit")
async def order_audit(order_id: str):
    """审计视图（LOG/战后复盘）：真实状态 + 事件链 + 传达链。"""
    from src.orders import service as orders_service
    try:
        return orders_service.order_audit(game_state, order_id)
    except KeyError:
        raise HTTPException(404, "Order 不存在。")


@app.post("/orders/{order_id}")
async def update_order(order_id: str, req: OrderUpdateRequest):
    from src.orders import service as orders_service
    try:
        order = orders_service.update_draft(
            game_state, order_id, parameters=req.parameters,
            commander_intent_text=req.commander_intent_text,
            target_refs=req.target_refs, priority=req.priority)
    except KeyError:
        raise HTTPException(404, "Order 不存在。")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"order": _order_public(order)}


@app.post("/orders/{order_id}/issue")
async def issue_order(order_id: str, req: OrderIssueRequest | None = None):
    """签发：岗位路由 + 冲突检查 + S2 发报。不直接修改舰队状态。"""
    from src.orders import service as orders_service
    supersede = req.supersede_ids if req else []
    try:
        order = orders_service.issue_order(
            game_state, staff_roster, order_id, supersede_ids=supersede)
    except orders_service.OrderConflict as e:
        raise HTTPException(409, {
            "message": str(e),
            "active_order": _order_public(e.active_order),
        })
    except KeyError:
        raise HTTPException(404, "Order 不存在。")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"order": _order_public(order), "result": "已签发（经 S2 传达）"}


@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str):
    from src.orders import service as orders_service
    try:
        orders_service.cancel_order(game_state, orders_service.get_order(game_state, order_id))
    except KeyError:
        raise HTTPException(404, "Order 不存在。")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"result": "已取消（历史保留）"}


@app.post("/orders/{order_id}/approve")
async def approve_order(order_id: str):
    """批准 INTENT 方案（PENDING_APPROVAL → ACTIVE）。"""
    from src.orders import service as orders_service
    try:
        orders_service.approve_order(game_state, orders_service.get_order(game_state, order_id))
    except KeyError:
        raise HTTPException(404, "Order 不存在。")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"result": "已批准，命令生效（执行经 Pipeline）"}


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
