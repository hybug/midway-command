"""HTML Canvas hex grid map renderer.

Generates a self-contained HTML+JS Canvas map for Streamlit embedding.
Reuses coordinate.py for hex math; JS mirrors key functions for rendering.
"""
import json
import math
from typing import Optional

from src.render.coordinate import (
    world_to_hex, hex_distance, hex_sector, CELL_SIZE_NM,
)


def render_html_map(
    state,
    center_q: int,
    center_r: int,
    radius: int = 8,
    course: int = 0,
) -> str:
    """Render the tactical map as an HTML Canvas element.

    Args:
        state: GameState
        center_q, center_r: Hex coords to center the view on
        radius: How many hex rings to show
        course: Fleet heading for the course arrow

    Returns:
        Self-contained HTML string with <canvas> and <script>
    """
    hex_data = _build_hex_data(state, center_q, center_r, radius)
    entities = _build_entities(state)
    search_sectors = _build_search_sectors(state, center_q, center_r)
    fleet_hex = _get_fleet_hex(state)

    data_json = json.dumps({
        "hexes": hex_data,
        "entities": entities,
        "sectors": search_sectors,
        "centerQ": center_q,
        "centerR": center_r,
        "radius": radius,
        "fleetQ": fleet_hex[0],
        "fleetR": fleet_hex[1],
        "course": course,
    }, ensure_ascii=False)

    return _HTML_TEMPLATE.replace("__DATA__", data_json)


# ─── Data builders ───────────────────────────────────────────

def _build_hex_data(state, center_q, center_r, radius):
    """Build hex cell data for the visible area."""
    fleet_q, fleet_r = _get_fleet_hex(state)
    cells = []

    for q in range(center_q - radius, center_q + radius + 1):
        for r in range(center_r - radius, center_r + radius + 1):
            dist = hex_distance(q, r, center_q, center_r)
            if dist > radius:
                continue

            # Scouted = within 5 hexes of fleet
            scouted = hex_distance(q, r, fleet_q, fleet_r) <= 5

            cells.append({
                "q": q, "r": r,
                "scouted": scouted,
                "dist": dist,
            })
    return cells


def _build_entities(state):
    """Build entity list (fleets, islands)."""
    entities = []

    # Own fleet
    for tf in state.task_forces:
        for carrier in tf.carriers:
            q, r = world_to_hex(carrier.position.lat, carrier.position.lon)
            short = carrier.name.split("(")[0].strip()
            # Use 3-letter abbreviation
            abbr = {"USS Enterprise": "ENT", "USS Hornet": "HOR"}.get(short, short[:3])
            entities.append({
                "q": q, "r": r,
                "type": "fleet_us",
                "label": abbr,
            })

    # Known enemy
    for enemy in state.known_enemy:
        q, r = world_to_hex(enemy.position.lat, enemy.position.lon)
        entities.append({
            "q": q, "r": r,
            "type": "fleet_enemy",
            "label": "敌",
        })

    # Midway
    mq, mr = world_to_hex(28.2, -177.4)
    entities.append({"q": mq, "r": mr, "type": "island", "label": "中途岛"})

    return entities


def _build_search_sectors(state, center_q, center_r):
    """Build search sector cell lists."""
    fleet_q, fleet_r = _get_fleet_hex(state)
    sectors = []
    for scout in state.active_scouts:
        if scout.status == "in_flight":
            cells = hex_sector(
                fleet_q, fleet_r,
                scout.search_bearing_min, scout.search_bearing_max,
                20,
            )
            sectors.append({
                "cells": [{"q": q, "r": r} for q, r in cells],
                "direction": scout.direction,
            })
    return sectors


def _get_fleet_hex(state):
    """Get the fleet's current hex position."""
    tf = state.task_forces[0]
    c = tf.carriers[0]
    return world_to_hex(c.position.lat, c.position.lon)


# ─── HTML Template ───────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body { margin:0; padding:0; background:transparent; }
canvas { display:block; width:100%; }
</style></head><body>
<canvas id="map"></canvas>
<script>
const D = __DATA__;
const canvas = document.getElementById('map');
const ctx = canvas.getContext('2d');

const HEX_SIZE = 22;
const SQRT3 = Math.sqrt(3);
const CELL_NM = 10;

// ── CRT color palette ──
const COL_BG      = '#0a1628';
const COL_FOG     = '#060e1a';
const COL_SCOUTED = '#0d1a2d';
const COL_GRID    = '#152a40';
const COL_GREEN   = '#4ae04a';
const COL_GREEN_DIM = '#1a5a2a';
const COL_RED     = '#ff4444';
const COL_AMBER   = '#ff8800';
const COL_SECTOR  = 'rgba(74,224,74,0.06)';

function hexToPixel(q, r) {
    const x = HEX_SIZE * (SQRT3 * q + SQRT3/2 * r);
    const y = HEX_SIZE * (3/2 * r);
    return [x, y];
}

function drawHex(ctx, cx, cy, size, fill, stroke, lineWidth) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
        const angle = Math.PI / 180 * (60 * i - 30);
        const px = cx + size * Math.cos(angle);
        const py = cy + size * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lineWidth || 1; ctx.stroke(); }
}

function resize() {
    const w = canvas.parentElement ? canvas.parentElement.clientWidth : 520;
    canvas.width = w;
    canvas.height = Math.round(w * 0.75);
    draw();
}
window.addEventListener('resize', resize);

function draw() {
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    const [fpx, fpy] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);

    // ── Background with noise ──
    ctx.fillStyle = COL_BG;
    ctx.fillRect(0, 0, W, H);
    // Subtle noise
    for (let i = 0; i < 3000; i++) {
        const nx = Math.random() * W, ny = Math.random() * H;
        ctx.fillStyle = 'rgba(74,224,74,' + (Math.random() * 0.015) + ')';
        ctx.fillRect(nx, ny, 1, 1);
    }

    ctx.save();
    ctx.translate(cx - fpx, cy - fpy);

    // ── Hex grid (dashed, dim) ──
    ctx.setLineDash([2, 3]);
    for (const h of D.hexes) {
        const [px, py] = hexToPixel(h.q - D.centerQ, h.r - D.centerR);
        const fill = h.scouted ? COL_SCOUTED : COL_FOG;
        drawHex(ctx, px, py, HEX_SIZE - 1, fill, COL_GRID, 0.4);
    }
    ctx.setLineDash([]);

    // ── Search sectors (diagonal hatch) ──
    for (const sec of D.sectors) {
        for (const c of sec.cells) {
            const [px, py] = hexToPixel(c.q - D.centerQ, c.r - D.centerR);
            drawHex(ctx, px, py, HEX_SIZE - 1, COL_SECTOR, 'rgba(74,224,74,0.12)', 0.4);
        }
    }

    // ── Distance rings (circular, with compass labels) ──
    const [ox, oy] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);
    ctx.save();
    ctx.setLineDash([3, 5]);
    ctx.strokeStyle = 'rgba(74,224,74,0.12)';
    ctx.lineWidth = 0.6;
    for (let ring = 2; ring <= D.radius; ring += 2) {
        const r_px = ring * HEX_SIZE * SQRT3;
        ctx.beginPath();
        ctx.arc(ox, oy, r_px, 0, Math.PI * 2);
        ctx.stroke();
        // Label at cardinal points
        ctx.fillStyle = 'rgba(74,224,74,0.25)';
        ctx.font = '9px monospace';
        ctx.textAlign = 'center';
        ctx.fillText((ring * CELL_NM) + 'nm', ox + r_px + 0, oy - 3);
    }
    ctx.restore();

    // ── Compass rose ──
    const cr_x = ox, cr_y = oy;
    const cr_r = D.radius * HEX_SIZE * SQRT3 + 15;
    ctx.save();
    ctx.strokeStyle = 'rgba(74,224,74,0.2)';
    ctx.lineWidth = 0.8;
    ctx.setLineDash([2, 4]);
    // N-S line
    ctx.beginPath(); ctx.moveTo(cr_x, cr_y - cr_r); ctx.lineTo(cr_x, cr_y + cr_r); ctx.stroke();
    // E-W line
    ctx.beginPath(); ctx.moveTo(cr_x - cr_r, cr_y); ctx.lineTo(cr_x + cr_r, cr_y); ctx.stroke();
    ctx.setLineDash([]);
    // Cardinal labels
    ctx.fillStyle = 'rgba(74,224,74,0.35)';
    ctx.font = 'bold 11px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', cr_x, cr_y - cr_r - 8);
    ctx.fillText('S', cr_x, cr_y + cr_r + 10);
    ctx.fillText('E', cr_x + cr_r + 10, cr_y);
    ctx.fillText('W', cr_x - cr_r - 10, cr_y);
    ctx.restore();

    // ── Entities ──
    for (const e of D.entities) {
        const [px, py] = hexToPixel(e.q - D.centerQ, e.r - D.centerR);

        if (e.type === 'fleet_us') {
            // Green glow hex + label
            drawHex(ctx, px, py, HEX_SIZE - 2, 'rgba(74,224,74,0.15)', COL_GREEN, 1.2);
            // Glow
            ctx.shadowColor = COL_GREEN;
            ctx.shadowBlur = 6;
            drawHex(ctx, px, py, HEX_SIZE - 2, null, 'rgba(74,224,74,0.4)', 1);
            ctx.shadowBlur = 0;
            ctx.fillStyle = COL_GREEN;
            ctx.font = 'bold 10px monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(e.label, px, py);
        } else if (e.type === 'fleet_enemy') {
            // Red dashed outline + question mark
            ctx.setLineDash([3, 3]);
            drawHex(ctx, px, py, HEX_SIZE - 2, 'rgba(255,68,68,0.08)', COL_RED, 1);
            ctx.setLineDash([]);
            ctx.fillStyle = COL_RED;
            ctx.font = 'bold 14px monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('?', px, py - 1);
            ctx.font = '8px monospace';
            ctx.fillStyle = 'rgba(255,68,68,0.7)';
            ctx.fillText('ENEMY', px, py + 10);
        } else if (e.type === 'island') {
            // Island: simple shape
            drawHex(ctx, px, py, HEX_SIZE - 2, 'rgba(255,136,0,0.08)', COL_AMBER, 1);
            ctx.fillStyle = COL_AMBER;
            ctx.font = 'bold 10px monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('\\u25C6', px, py - 1);
            ctx.font = '8px monospace';
            ctx.fillStyle = 'rgba(255,136,0,0.7)';
            ctx.fillText(e.label, px, py + 10);
        }
    }

    // ── Course arrow ──
    const [fx, fy] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);
    const arrowLen = HEX_SIZE * 3;
    const rad = (D.course - 90) * Math.PI / 180;
    const ax = fx + arrowLen * Math.cos(rad);
    const ay = fy + arrowLen * Math.sin(rad);
    ctx.strokeStyle = COL_GREEN;
    ctx.lineWidth = 1.5;
    ctx.shadowColor = COL_GREEN;
    ctx.shadowBlur = 4;
    ctx.beginPath();
    ctx.moveTo(fx, fy);
    ctx.lineTo(ax, ay);
    ctx.stroke();
    // Arrowhead
    const headLen = 8, headAngle = 0.4;
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - headLen * Math.cos(rad - headAngle), ay - headLen * Math.sin(rad - headAngle));
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - headLen * Math.cos(rad + headAngle), ay - headLen * Math.sin(rad + headAngle));
    ctx.stroke();
    ctx.shadowBlur = 0;
    // Course label
    ctx.fillStyle = COL_GREEN;
    ctx.font = 'bold 10px monospace';
    ctx.textAlign = 'left';
    ctx.fillText('HDG ' + D.course + '\\u00B0', ax + 6, ay);

    ctx.restore();

    // ── Scale bar ──
    const scale_nm = 50;
    const scale_px = (scale_nm / CELL_NM) * HEX_SIZE * SQRT3;
    ctx.strokeStyle = 'rgba(74,224,74,0.3)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(W - scale_px - 20, H - 20);
    ctx.lineTo(W - 20, H - 20);
    ctx.stroke();
    // Ticks
    ctx.beginPath();
    ctx.moveTo(W - scale_px - 20, H - 24); ctx.lineTo(W - scale_px - 20, H - 16); ctx.stroke();
    ctx.moveTo(W - 20, H - 24); ctx.lineTo(W - 20, H - 16); ctx.stroke();
    ctx.fillStyle = 'rgba(74,224,74,0.3)';
    ctx.font = '9px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(scale_nm + 'nm', W - scale_px / 2 - 20, H - 25);

    // ── Legend ──
    ctx.fillStyle = 'rgba(10,22,40,0.9)';
    ctx.fillRect(8, H - 82, 115, 76);
    ctx.strokeStyle = '#1a3a5c';
    ctx.strokeRect(8, H - 82, 115, 76);
    ctx.font = '10px monospace';
    ctx.textAlign = 'left';
    const legend = [
        [COL_GREEN,  '\\u25A0 FRIENDLY'],
        [COL_RED,    '? ENEMY'],
        [COL_AMBER,  '\\u25C6 ISLAND'],
        ['rgba(74,224,74,0.06)', '\\u2591 SECTOR'],
        [COL_SCOUTED,'\\u25AA SCOUTED'],
    ];
    legend.forEach(([color, text], i) => {
        const y = H - 70 + i * 14;
        ctx.fillStyle = color;
        ctx.fillRect(14, y - 6, 8, 8);
        ctx.fillStyle = '#2a7a3a';
        ctx.fillText(text, 26, y + 1);
    });
}

resize();
</script></body></html>"""
