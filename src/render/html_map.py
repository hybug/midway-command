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
<html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Caveat:wght@400;700&display=swap" rel="stylesheet">
<style>
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
const REF_LAT = 28.2, REF_LON = -177.4;

// ── WWII Chart palette ──
const PAPER   = '#f5edd6';
const PAPER_D = '#e8dcc8';
const INK     = '#2a2218';
const INK_L   = '#6b5d4a';
const INK_LL  = '#a89878';
const RED     = '#8b2500';
const RED_L   = 'rgba(139,37,0,0.15)';
const BLUE    = '#1a3a5c';
const GRID_C  = '#c4b89a';
const WATER   = '#d4cbb4';

function hexToPixel(q, r) {
    return [HEX_SIZE * (SQRT3 * q + SQRT3/2 * r), HEX_SIZE * (3/2 * r)];
}

function resize() {
    const w = canvas.parentElement ? canvas.parentElement.clientWidth : 520;
    canvas.width = w;
    canvas.height = Math.round(w * 0.75);
    draw();
}
window.addEventListener('resize', resize);

// ── Paper texture ──
function drawPaper(W, H) {
    ctx.fillStyle = PAPER;
    ctx.fillRect(0, 0, W, H);
    // Grain noise
    for (let i = 0; i < 8000; i++) {
        const nx = Math.random() * W, ny = Math.random() * H;
        const v = Math.random() * 0.04;
        ctx.fillStyle = 'rgba(42,34,24,' + v + ')';
        ctx.fillRect(nx, ny, 1, 1);
    }
    // Age stains
    for (let i = 0; i < 5; i++) {
        const sx = Math.random() * W, sy = Math.random() * H, sr = 30 + Math.random() * 60;
        const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, sr);
        grad.addColorStop(0, 'rgba(180,160,120,0.06)');
        grad.addColorStop(1, 'rgba(180,160,120,0)');
        ctx.fillStyle = grad;
        ctx.fillRect(sx - sr, sy - sr, sr * 2, sr * 2);
    }
    // Edge darkening
    const edge = ctx.createLinearGradient(0, 0, 0, H);
    edge.addColorStop(0, 'rgba(42,34,24,0.08)');
    edge.addColorStop(0.05, 'rgba(42,34,24,0)');
    edge.addColorStop(0.95, 'rgba(42,34,24,0)');
    edge.addColorStop(1, 'rgba(42,34,24,0.08)');
    ctx.fillStyle = edge;
    ctx.fillRect(0, 0, W, H);
}

// ── Compass rose ──
function drawCompassRose(x, y, size) {
    ctx.save();
    ctx.translate(x, y);
    // Outer circle
    ctx.strokeStyle = INK_L;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(0, 0, size, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, size * 0.85, 0, Math.PI * 2); ctx.stroke();
    // Inner star
    ctx.lineWidth = 0.8;
    for (let i = 0; i < 8; i++) {
        const a = i * Math.PI / 4;
        const r1 = i % 2 === 0 ? size * 0.85 : size * 0.5;
        const r2 = size * 0.15;
        ctx.beginPath();
        ctx.moveTo(Math.sin(a) * r2, -Math.cos(a) * r2);
        ctx.lineTo(Math.sin(a) * r1, -Math.cos(a) * r1);
        ctx.strokeStyle = i % 2 === 0 ? INK : INK_L;
        ctx.stroke();
    }
    // Labels
    ctx.fillStyle = INK;
    ctx.font = 'bold 11px Caveat, cursive';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('N', 0, -size - 8);
    ctx.fillText('S', 0, size + 12);
    ctx.fillText('E', size + 10, 0);
    ctx.fillText('W', -size - 10, 0);
    // Small ticks
    ctx.font = '8px Caveat, cursive';
    ctx.fillStyle = INK_L;
    ctx.fillText('NE', size * 0.7, -size * 0.7);
    ctx.fillText('SE', size * 0.7, size * 0.7);
    ctx.fillText('SW', -size * 0.7, size * 0.7);
    ctx.fillText('NW', -size * 0.7, -size * 0.7);
    ctx.restore();
}

// ── Midway atoll ──
function drawMidway(cx, cy, scale) {
    ctx.save();
    ctx.translate(cx, cy);
    // Lagoon (light blue-green)
    ctx.fillStyle = '#c8d8c8';
    ctx.beginPath();
    ctx.ellipse(0, 0, 12 * scale, 10 * scale, -0.2, 0, Math.PI * 2);
    ctx.fill();
    // Reef ring (dotted)
    ctx.strokeStyle = INK_L;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.ellipse(0, 0, 14 * scale, 12 * scale, -0.2, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    // Sand Island (left, larger)
    ctx.fillStyle = '#c4b080';
    ctx.strokeStyle = INK;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(-5 * scale, -1 * scale, 5 * scale, 3 * scale, -0.3, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();
    // Eastern Island (right, triangular)
    ctx.fillStyle = '#b8a870';
    ctx.beginPath();
    ctx.moveTo(6 * scale, -3 * scale);
    ctx.lineTo(10 * scale, 1 * scale);
    ctx.lineTo(4 * scale, 2 * scale);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    // Runways on Eastern Island (3 lines forming triangle)
    ctx.strokeStyle = INK_L;
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(5 * scale, -2 * scale); ctx.lineTo(9 * scale, 1 * scale); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(9 * scale, 1 * scale); ctx.lineTo(5 * scale, 1.5 * scale); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(5 * scale, 1.5 * scale); ctx.lineTo(5 * scale, -2 * scale); ctx.stroke();
    // Spit Island (small dot)
    ctx.fillStyle = '#c4b080';
    ctx.beginPath();
    ctx.arc(-2 * scale, 6 * scale, 1.5 * scale, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();
    // Labels
    ctx.fillStyle = INK;
    ctx.font = 'bold 10px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.fillText('MIDWAY ATOLL', 0, -16 * scale);
    ctx.font = '8px Caveat, cursive';
    ctx.fillStyle = INK_L;
    ctx.fillText('28\\u00B012\\u2032N 177\\u00B021\\u2032W', 0, -14 * scale + 10);
    ctx.fillText('Sand I.', -5 * scale, 4 * scale);
    ctx.fillText('Eastern I.', 7 * scale, 5 * scale);
    ctx.fillText('Henderson Fld', 7 * scale, 8 * scale);
    ctx.restore();
}

// ── Main draw ──
function draw() {
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    const [fpx, fpy] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);

    drawPaper(W, H);

    ctx.save();
    ctx.translate(cx - fpx, cy - fpy);

    // ── Lat/lon grid ──
    ctx.strokeStyle = GRID_C;
    ctx.lineWidth = 0.3;
    ctx.setLineDash([4, 4]);
    const gridStep = HEX_SIZE * SQRT3 * 2; // ~2 hexes per grid line
    const gridMinX = fpx - cx - gridStep * 2;
    const gridMaxX = fpx + cx + gridStep * 2;
    const gridMinY = fpy - cy - gridStep * 2;
    const gridMaxY = fpy + cy + gridStep * 2;
    for (let gx = Math.floor(gridMinX / gridStep) * gridStep; gx <= gridMaxX; gx += gridStep) {
        ctx.beginPath(); ctx.moveTo(gx, gridMinY); ctx.lineTo(gx, gridMaxY); ctx.stroke();
    }
    for (let gy = Math.floor(gridMinY / gridStep) * gridStep; gy <= gridMaxY; gy += gridStep) {
        ctx.beginPath(); ctx.moveTo(gridMinX, gy); ctx.lineTo(gridMaxX, gy); ctx.stroke();
    }
    ctx.setLineDash([]);
    // Grid labels
    ctx.fillStyle = INK_LL;
    ctx.font = '8px Caveat, cursive';
    ctx.textAlign = 'left';
    for (let gx = Math.floor(gridMinX / gridStep) * gridStep; gx <= gridMaxX; gx += gridStep) {
        const lon = REF_LON + (gx / (HEX_SIZE * SQRT3)) * CELL_NM / 60;
        ctx.fillText(Math.abs(lon).toFixed(1) + '\\u00B0W', gx + 2, gridMinY + 10);
    }
    ctx.textAlign = 'center';
    for (let gy = Math.floor(gridMinY / gridStep) * gridStep; gy <= gridMaxY; gy += gridStep) {
        const lat = REF_LAT - (gy / (HEX_SIZE * 1.5)) * CELL_NM / 60;
        ctx.fillText(lat.toFixed(1) + '\\u00B0N', gridMinX + 20, gy - 2);
    }

    // ── Hex grid (very faint, as chart grid) ──
    ctx.strokeStyle = 'rgba(42,34,24,0.06)';
    ctx.lineWidth = 0.3;
    for (const h of D.hexes) {
        const [px, py] = hexToPixel(h.q - D.centerQ, h.r - D.centerR);
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            const angle = Math.PI / 180 * (60 * i - 30);
            const hx = px + (HEX_SIZE - 1) * Math.cos(angle);
            const hy = py + (HEX_SIZE - 1) * Math.sin(angle);
            if (i === 0) ctx.moveTo(hx, hy); else ctx.lineTo(hx, hy);
        }
        ctx.closePath();
        ctx.stroke();
    }

    // ── Search sectors (hatched) ──
    for (const sec of D.sectors) {
        for (const c of sec.cells) {
            const [px, py] = hexToPixel(c.q - D.centerQ, c.r - D.centerR);
            ctx.save();
            ctx.globalAlpha = 0.08;
            ctx.strokeStyle = INK;
            ctx.lineWidth = 0.4;
            for (let d = -HEX_SIZE; d < HEX_SIZE; d += 4) {
                ctx.beginPath();
                ctx.moveTo(px + d, py - HEX_SIZE);
                ctx.lineTo(px + d + HEX_SIZE, py + HEX_SIZE);
                ctx.stroke();
            }
            ctx.restore();
        }
    }

    // ── Distance rings ──
    const [ox, oy] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);
    ctx.save();
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = 'rgba(42,34,24,0.12)';
    ctx.lineWidth = 0.5;
    for (let ring = 2; ring <= D.radius; ring += 2) {
        const r_px = ring * HEX_SIZE * SQRT3;
        ctx.beginPath(); ctx.arc(ox, oy, r_px, 0, Math.PI * 2); ctx.stroke();
        ctx.fillStyle = 'rgba(42,34,24,0.2)';
        ctx.font = '9px Caveat, cursive';
        ctx.textAlign = 'center';
        ctx.fillText((ring * CELL_NM) + ' nm', ox + r_px, oy - 3);
    }
    ctx.restore();

    // ── Midway ──
    const [mx, my] = hexToPixel(0 - D.centerQ, 0 - D.centerR);
    drawMidway(mx, my, 1.2);

    // ── Entities ──
    for (const e of D.entities) {
        if (e.type === 'island') continue; // Midway drawn separately
        const [px, py] = hexToPixel(e.q - D.centerQ, e.r - D.centerR);

        if (e.type === 'fleet_us') {
            // Ink circle + label
            ctx.strokeStyle = INK;
            ctx.lineWidth = 1.5;
            ctx.beginPath(); ctx.arc(px, py, 8, 0, Math.PI * 2); ctx.stroke();
            // Cross inside
            ctx.lineWidth = 0.8;
            ctx.beginPath(); ctx.moveTo(px - 5, py); ctx.lineTo(px + 5, py); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(px, py - 5); ctx.lineTo(px, py + 5); ctx.stroke();
            // Label
            ctx.fillStyle = INK;
            ctx.font = 'bold 11px Caveat, cursive';
            ctx.textAlign = 'center';
            ctx.fillText(e.label, px, py - 12);
        } else if (e.type === 'fleet_enemy') {
            // Red dashed circle + ?
            ctx.strokeStyle = RED;
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 3]);
            ctx.beginPath(); ctx.arc(px, py, 10, 0, Math.PI * 2); ctx.stroke();
            ctx.setLineDash([]);
            ctx.fillStyle = RED;
            ctx.font = 'bold 14px Caveat, cursive';
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText('?', px, py);
            ctx.font = '9px Caveat, cursive';
            ctx.fillText('ENEMY', px, py + 16);
            ctx.textBaseline = 'alphabetic';
        }
    }

    // ── Course arrow ──
    const [fx, fy] = hexToPixel(D.fleetQ - D.centerQ, D.fleetR - D.centerR);
    const arrowLen = HEX_SIZE * 3;
    const rad = (D.course - 90) * Math.PI / 180;
    const ax = fx + arrowLen * Math.cos(rad);
    const ay = fy + arrowLen * Math.sin(rad);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(fx, fy); ctx.lineTo(ax, ay); ctx.stroke();
    // Arrowhead
    const hl = 8, ha = 0.4;
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - hl * Math.cos(rad - ha), ay - hl * Math.sin(rad - ha));
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - hl * Math.cos(rad + ha), ay - hl * Math.sin(rad + ha));
    ctx.stroke();
    // Dashed extension (projected course)
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = INK_L;
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax + arrowLen * 0.8 * Math.cos(rad), ay + arrowLen * 0.8 * Math.sin(rad));
    ctx.stroke();
    ctx.setLineDash([]);
    // Label
    ctx.fillStyle = INK;
    ctx.font = 'bold 11px Caveat, cursive';
    ctx.textAlign = 'left';
    ctx.fillText('COURSE ' + D.course + '\\u00B0', ax + 6, ay - 2);

    ctx.restore();

    // ── Compass rose (top-right) ──
    drawCompassRose(W - 45, 45, 25);

    // ── Scale bar ──
    const scale_nm = 50;
    const scale_px = (scale_nm / CELL_NM) * HEX_SIZE * SQRT3;
    ctx.strokeStyle = INK;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(W - scale_px - 20, H - 20); ctx.lineTo(W - 20, H - 20); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(W - scale_px - 20, H - 24); ctx.lineTo(W - scale_px - 20, H - 16); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(W - 20, H - 24); ctx.lineTo(W - 20, H - 16); ctx.stroke();
    ctx.fillStyle = INK;
    ctx.font = '9px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.fillText(scale_nm + ' nm', W - scale_px / 2 - 20, H - 25);

    // ── Classification stamp ──
    ctx.save();
    ctx.translate(12, 16);
    ctx.strokeStyle = RED;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(0, 0, 70, 18);
    ctx.fillStyle = RED;
    ctx.font = 'bold 12px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('SECRET', 35, 9);
    ctx.restore();

    // ── Legend ──
    const lx = 10, ly = H - 85;
    ctx.fillStyle = 'rgba(245,237,214,0.92)';
    ctx.fillRect(lx, ly, 120, 78);
    ctx.strokeStyle = INK_L;
    ctx.lineWidth = 0.8;
    ctx.strokeRect(lx, ly, 120, 78);
    ctx.font = '10px Caveat, cursive';
    ctx.textAlign = 'left';
    const legend = [
        [INK,    '\\u25CB OWN FLEET'],
        [RED,    '? ENEMY CONTACT'],
        [INK_L,  '\\u25CC ISLAND'],
        ['rgba(42,34,24,0.08)', '\\u2591 SEARCH SECTOR'],
        [GRID_C, '\\u25AB SCOUTED'],
    ];
    legend.forEach(([color, text], i) => {
        const y = ly + 12 + i * 14;
        ctx.fillStyle = color;
        ctx.fillRect(lx + 6, y - 6, 8, 8);
        ctx.fillStyle = INK;
        ctx.fillText(text, lx + 18, y + 1);
    });
}

resize();
</script></body></html>"""
