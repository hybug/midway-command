"""FastAPI server — replaces Streamlit as the frontend backend.

Serves the static HTML/CSS/JS frontend and exposes REST APIs
for game state, NPC chat, time advancement, and suggestion management.
"""
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
from src.npc_config import NPC_REGISTRY
from src.events import create_midway_events
from src.ap import consume_ap, has_ap, reset_ap, get_ap_status
from src.tools import handle_execute_action

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("midway.server")

app = FastAPI(title="中途岛指挥官")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ── Global game state (single-user prototype) ──
game_state = build_initial_state()
scheduler = create_midway_events()
npcs: dict = {
    "browning": BrowningNPC(),
    "murray": MurrayNPC(),
    "mitscher": MitscherNPC(),
    "radio_officer": RadioOfficerNPC(),
    "intel_officer": IntelOfficerNPC(),
}

NPC_DISPLAY = {
    "browning": {"label": "参谋长", "sender": "布朗宁（BROWNING）· 参谋长", "role": "参谋长"},
    "murray": {"label": "企业号舰长", "sender": "默里（MURRAY）· 企业号舰长", "role": "企业号舰长"},
    "mitscher": {"label": "大黄蜂舰长", "sender": "米切尔（MITSCHER）· 大黄蜂舰长", "role": "大黄蜂舰长"},
    "radio_officer": {"label": "通信官", "sender": "通信官 · TBS", "role": "通信官"},
    "intel_officer": {"label": "情报官", "sender": "情报官 · 情报参谋", "role": "情报参谋"},
}


# ── Request models ──

class ChatRequest(BaseModel):
    npc_id: str
    message: str


class AdvanceRequest(BaseModel):
    minutes: int = 15


class SuggestionAction(BaseModel):
    pass


# ── Routes ──

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


@app.get("/state")
async def get_state():
    """Return full game state as JSON."""
    tf = game_state.task_forces[0]
    ap = get_ap_status(game_state)
    return {
        "clock": {
            "game_time": game_state.clock.game_time.isoformat(),
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
        ],
        "known_enemy": [
            {
                "description": e.description,
                "confidence": e.confidence,
                "source": e.source,
                "position": {"lat": e.position.lat, "lon": e.position.lon},
            }
            for e in game_state.known_enemy
        ],
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
    """Advance the game clock by N minutes."""
    notifications = scheduler.tick(game_state, req.minutes)
    reset_ap(game_state)
    return {
        "notifications": notifications,
        "ap": get_ap_status(game_state),
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
