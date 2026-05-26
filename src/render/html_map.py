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

// ── Hex math (pointy-top) ──
const HEX_SIZE = 22;
const SQRT3 = Math.sqrt(3);

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
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lineWidth || 1; ctx.stroke(); }
}

// ── Colors ──
const COL_FOG     = '#0d1520';
const COL_SCOUTED = '#1a2838';
const COL_SECTOR  = 'rgba(196,162,101,0.12)';
const COL_GRID    = '#253545';
const COL_GOLD    = '#c4a265';
const COL_RED     = '#c45040';
const COL_ISLAND  = '#8a7e5a';

// ── Resize ──
function resize() {
    const w = canvas.parentElement ? canvas.parentElement.clientWidth : 520;
    canvas.width = w;
    canvas.height = w;
    draw();
}
window.addEventListener('resize', resize);

// ── Main draw ──
function draw() {
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;

    // Offset so fleet hex is centered
    const [fpx, fpy] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);

    ctx.fillStyle = '#111a24';
    ctx.fillRect(0, 0, W, H);

    ctx.save();
    ctx.translate(cx - fpx, cy - fpy);

    // ── Draw hexes ──
    for (const h of D.hexes) {
        const [px, py] = hexToPixel(h.q - D.centerQ, h.r - D.centerR);
        const fill = h.scouted ? COL_SCOUTED : COL_FOG;
        drawHex(ctx, px, py, HEX_SIZE - 1, fill, COL_GRID, 0.5);
    }

    // ── Search sectors ──
    for (const sec of D.sectors) {
        for (const c of sec.cells) {
            const [px, py] = hexToPixel(c.q - D.centerQ, c.r - D.centerR);
            drawHex(ctx, px, py, HEX_SIZE - 1, COL_SECTOR, 'rgba(196,162,101,0.2)', 0.5);
        }
    }

    // ── Distance rings ──
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = 'rgba(196,162,101,0.15)';
    ctx.lineWidth = 0.8;
    for (let ring = 2; ring <= D.radius; ring += 2) {
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            const angle = Math.PI / 180 * (60 * i - 30);
            const [qx, qy] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);
            const px = qx + ring * HEX_SIZE * SQRT3 * Math.cos(angle);
            const py = qy + ring * HEX_SIZE * SQRT3 * Math.sin(angle);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();
        // Label
        const [lx, ly] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);
        const labelX = lx + ring * HEX_SIZE * SQRT3 * 0.95;
        const labelY = ly - 4;
        ctx.fillStyle = 'rgba(196,162,101,0.3)';
        ctx.font = '9px monospace';
        ctx.fillText((ring * 10) + 'nm', labelX, labelY);
    }
    ctx.restore();

    // ── Entities ──
    for (const e of D.entities) {
        const [px, py] = hexToPixel(e.q - D.centerQ, e.r - D.centerR);

        if (e.type === 'fleet_us') {
            // Gold filled hex
            drawHex(ctx, px, py, HEX_SIZE - 2, COL_GOLD, '#d4b876', 1.5);
            ctx.fillStyle = '#1a1612';
            ctx.font = 'bold 10px monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(e.label, px, py);
        } else if (e.type === 'fleet_enemy') {
            // Red triangle marker
            drawHex(ctx, px, py, HEX_SIZE - 2, 'rgba(196,80,64,0.3)', COL_RED, 1.5);
            ctx.fillStyle = COL_RED;
            ctx.font = 'bold 12px monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('▲', px, py - 2);
            ctx.font = '8px monospace';
            ctx.fillText(e.label, px, py + 10);
        } else if (e.type === 'island') {
            // Island marker
            drawHex(ctx, px, py, HEX_SIZE - 2, 'rgba(138,126,90,0.3)', COL_ISLAND, 1.5);
            ctx.fillStyle = COL_ISLAND;
            ctx.font = 'bold 10px monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('◆', px, py - 2);
            ctx.font = '8px monospace';
            ctx.fillText(e.label, px, py + 10);
        }
    }

    // ── Course arrow ──
    const [fx, fy] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);
    const arrowLen = HEX_SIZE * 3;
    const rad = (D.course - 90) * Math.PI / 180;
    const ax = fx + arrowLen * Math.cos(rad);
    const ay = fy + arrowLen * Math.sin(rad);
    ctx.strokeStyle = COL_GOLD;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(fx, fy);
    ctx.lineTo(ax, ay);
    ctx.stroke();
    // Arrowhead
    const headLen = 8;
    const headAngle = 0.4;
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - headLen * Math.cos(rad - headAngle), ay - headLen * Math.sin(rad - headAngle));
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - headLen * Math.cos(rad + headAngle), ay - headLen * Math.sin(rad + headAngle));
    ctx.stroke();
    // Course label
    ctx.fillStyle = COL_GOLD;
    ctx.font = 'bold 10px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(D.course + '°', ax + 6, ay);

    ctx.restore();

    // ── Legend ──
    ctx.fillStyle = 'rgba(17,26,36,0.85)';
    ctx.fillRect(6, H - 80, 110, 74);
    ctx.strokeStyle = '#253545';
    ctx.strokeRect(6, H - 80, 110, 74);
    ctx.font = '10px monospace';
    ctx.textAlign = 'left';
    const legend = [
        [COL_GOLD, '■ 己方舰队'],
        [COL_RED,  '▲ 已知敌军'],
        [COL_ISLAND, '◆ 岛屿'],
        ['rgba(196,162,101,0.12)', '░ 搜索扇面'],
        [COL_SCOUTED, '▪ 已侦察'],
    ];
    legend.forEach(([color, text], i) => {
        const y = H - 68 + i * 14;
        ctx.fillStyle = color;
        ctx.fillRect(12, y - 6, 8, 8);
        ctx.fillStyle = '#8a7e6a';
        ctx.fillText(text, 24, y + 1);
    });
}

resize();
</script></body></html>"""
