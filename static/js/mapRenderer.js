/**
 * 中途岛指挥官 — Canvas 海图渲染器
 * Phase 2: 纸张背景 + 网格 + 中途岛 + 罗盘 + 比例尺
 * Phase 3: 动态实体（己方/敌方/扇面/距离环）
 */

// ── Constants ──
const HEX_SIZE = 22;
const SQRT3 = Math.sqrt(3);
const CELL_NM = 10;
const REF_LAT = 28.2;
const REF_LON = -177.4;

// ── Colors (from CSS Variables, hardcoded for Canvas) ──
const COL = {
  paperBase: '#f5edd6',
  paperDark: '#e8dcc8',
  inkMain: '#2a2218',
  inkFade: '#6b5d4a',
  inkFaint: '#a89878',
  enemyRed: '#8b2500',
  gridLine: 'rgba(196, 184, 154, 0.5)',
  lagoon: '#c8d8c8',
  sand: '#c4b080',
  eastern: '#b8a870',
  reef: '#6b5d4a',
  runway: '#6b5d4a',
  secretRed: '#8b2500',
};

// ═══════════════════════════════════════════════════════
// MapRenderer class
// ═══════════════════════════════════════════════════════
class MapRenderer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.dpr = window.devicePixelRatio || 1;
    this.width = 0;
    this.height = 0;
    this.centerX = 0;
    this.centerY = 0;
  }

  resize() {
    const container = this.canvas.parentElement;
    this.width = container.clientWidth;
    this.height = container.clientHeight;
    this.canvas.width = this.width * this.dpr;
    this.canvas.height = this.height * this.dpr;
    this.canvas.style.width = this.width + 'px';
    this.canvas.style.height = this.height + 'px';
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.centerX = this.width / 2;
    this.centerY = this.height / 2;
  }

  render(state) {
    this.resize();
    const ctx = this.ctx;
    const W = this.width, H = this.height;

    this._drawPaper(ctx, W, H);
    this._drawGrid(ctx, W, H);

    if (state) {
      const tf = state.task_forces[0];
      const c1 = tf.carriers[0];
      const [fqr, frr] = this._worldToHex(c1.position.lat, c1.position.lon);
      const [fpx, fpy] = this._hexToPixel(fqr, frr);
      const ox = this.centerX - fpx;
      const oy = this.centerY - fpy;

      ctx.save();
      ctx.translate(ox, oy);

      this._drawDistanceRings(ctx, fpx, fpy, 8);
      this._drawSearchSectors(ctx, state, fqr, frr);
      this._drawMidway(ctx, 0, 0, 1.2);
      this._drawOwnFleet(ctx, tf);
      this._drawCourseArrow(ctx, fpx, fpy, tf.course);
      this._drawEnemyContacts(ctx, state);

      ctx.restore();
    } else {
      // No state yet — just draw Midway at center
      this._drawMidway(ctx, this.centerX, this.centerY, 1.2);
    }

    this._drawCompass(ctx, W - 45, 45, 25);
    this._drawScaleBar(ctx, W, H);
    this._drawSecretStamp(ctx);
  }

  // ═══════════════════════════════════════════════════════
  // Background
  // ═══════════════════════════════════════════════════════
  _drawPaper(ctx, W, H) {
    ctx.fillStyle = COL.paperBase;
    ctx.fillRect(0, 0, W, H);
    // Grain noise
    for (let i = 0; i < 6000; i++) {
      ctx.fillStyle = `rgba(42,34,24,${Math.random() * 0.03})`;
      ctx.fillRect(Math.random() * W, Math.random() * H, 1, 1);
    }
    // Edge darkening (vignette)
    const edge = ctx.createLinearGradient(0, 0, 0, H);
    edge.addColorStop(0, 'rgba(42,34,24,0.06)');
    edge.addColorStop(0.04, 'rgba(42,34,24,0)');
    edge.addColorStop(0.96, 'rgba(42,34,24,0)');
    edge.addColorStop(1, 'rgba(42,34,24,0.06)');
    ctx.fillStyle = edge;
    ctx.fillRect(0, 0, W, H);
    const edgeH = ctx.createLinearGradient(0, 0, W, 0);
    edgeH.addColorStop(0, 'rgba(42,34,24,0.04)');
    edgeH.addColorStop(0.03, 'rgba(42,34,24,0)');
    edgeH.addColorStop(0.97, 'rgba(42,34,24,0)');
    edgeH.addColorStop(1, 'rgba(42,34,24,0.04)');
    ctx.fillStyle = edgeH;
    ctx.fillRect(0, 0, W, H);
    // Age stains
    for (let i = 0; i < 4; i++) {
      const sx = Math.random() * W, sy = Math.random() * H, sr = 20 + Math.random() * 50;
      const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, sr);
      grad.addColorStop(0, 'rgba(180,160,120,0.05)');
      grad.addColorStop(1, 'rgba(180,160,120,0)');
      ctx.fillStyle = grad;
      ctx.fillRect(sx - sr, sy - sr, sr * 2, sr * 2);
    }
  }

  // ═══════════════════════════════════════════════════════
  // Grid
  // ═══════════════════════════════════════════════════════
  _drawGrid(ctx, W, H) {
    const step = HEX_SIZE * SQRT3 * 2;
    ctx.strokeStyle = COL.gridLine;
    ctx.lineWidth = 0.4;
    ctx.setLineDash([5, 5]);
    for (let x = 0; x < W; x += step) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let y = 0; y < H; y += step) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    ctx.setLineDash([]);
    // Degree labels
    ctx.fillStyle = COL.inkFaint;
    ctx.font = '9px Caveat, cursive';
    ctx.textAlign = 'left';
    for (let x = 0; x < W; x += step) {
      ctx.fillText((177 + (x / W) * 2).toFixed(1) + '°W', x + 3, 12);
    }
    ctx.textAlign = 'center';
    for (let y = 0; y < H; y += step) {
      ctx.fillText((28 + (y / H) * 2).toFixed(1) + '°N', 18, y - 3);
    }
  }

  // ═══════════════════════════════════════════════════════
  // Midway Atoll
  // ═══════════════════════════════════════════════════════
  _drawMidway(ctx, cx, cy, scale) {
    ctx.save();
    ctx.translate(cx, cy);

    // Lagoon
    ctx.fillStyle = COL.lagoon;
    ctx.beginPath();
    ctx.ellipse(0, 0, 12 * scale, 10 * scale, -0.2, 0, Math.PI * 2);
    ctx.fill();

    // Reef ring (dotted)
    ctx.strokeStyle = COL.reef;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.ellipse(0, 0, 14 * scale, 12 * scale, -0.2, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Sand Island (left, larger)
    ctx.fillStyle = COL.sand;
    ctx.strokeStyle = COL.inkMain;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(-5 * scale, -1 * scale, 5 * scale, 3 * scale, -0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Eastern Island (triangular)
    ctx.fillStyle = COL.eastern;
    ctx.beginPath();
    ctx.moveTo(6 * scale, -3 * scale);
    ctx.lineTo(10 * scale, 1 * scale);
    ctx.lineTo(4 * scale, 2 * scale);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Runways on Eastern Island
    ctx.strokeStyle = COL.runway;
    ctx.lineWidth = 0.6;
    ctx.beginPath(); ctx.moveTo(5 * scale, -2 * scale); ctx.lineTo(9 * scale, 1 * scale); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(9 * scale, 1 * scale); ctx.lineTo(5 * scale, 1.5 * scale); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(5 * scale, 1.5 * scale); ctx.lineTo(5 * scale, -2 * scale); ctx.stroke();

    // Spit Island
    ctx.fillStyle = COL.sand;
    ctx.strokeStyle = COL.inkMain;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(-2 * scale, 6 * scale, 1.5 * scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Labels
    ctx.fillStyle = COL.inkMain;
    ctx.font = 'bold 10px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.fillText('MIDWAY ATOLL', 0, -16 * scale);
    ctx.font = '8px Caveat, cursive';
    ctx.fillStyle = COL.inkFade;
    ctx.fillText('28°12\'N 177°21\'W', 0, -14 * scale + 10);
    ctx.fillText('Sand I.', -5 * scale, 4 * scale);
    ctx.fillText('Eastern I.', 7 * scale, 5 * scale);
    ctx.fillText('Henderson Fld', 7 * scale, 8 * scale);

    ctx.restore();
  }

  // ═══════════════════════════════════════════════════════
  // Compass Rose
  // ═══════════════════════════════════════════════════════
  _drawCompass(ctx, x, y, size) {
    ctx.save();
    ctx.translate(x, y);

    // Outer circles
    ctx.strokeStyle = COL.inkFade;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(0, 0, size, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, size * 0.85, 0, Math.PI * 2); ctx.stroke();

    // Star lines
    ctx.lineWidth = 0.8;
    for (let i = 0; i < 8; i++) {
      const a = i * Math.PI / 4;
      const r1 = i % 2 === 0 ? size * 0.85 : size * 0.5;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(Math.sin(a) * r1, -Math.cos(a) * r1);
      ctx.strokeStyle = i % 2 === 0 ? COL.inkMain : COL.inkFade;
      ctx.stroke();
    }

    // Labels
    ctx.fillStyle = COL.inkMain;
    ctx.font = 'bold 11px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', 0, -size - 8);
    ctx.fillText('S', 0, size + 12);
    ctx.fillText('E', size + 10, 0);
    ctx.fillText('W', -size - 10, 0);
    ctx.font = '8px Caveat, cursive';
    ctx.fillStyle = COL.inkFade;
    ctx.fillText('NE', size * 0.7, -size * 0.7);
    ctx.fillText('SE', size * 0.7, size * 0.7);
    ctx.fillText('SW', -size * 0.7, size * 0.7);
    ctx.fillText('NW', -size * 0.7, -size * 0.7);

    ctx.restore();
  }

  // ═══════════════════════════════════════════════════════
  // Scale Bar
  // ═══════════════════════════════════════════════════════
  _drawScaleBar(ctx, W, H) {
    const nm = 50;
    const px = (nm / CELL_NM) * HEX_SIZE * SQRT3;
    ctx.strokeStyle = COL.inkMain;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(W - px - 20, H - 20); ctx.lineTo(W - 20, H - 20); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(W - px - 20, H - 24); ctx.lineTo(W - px - 20, H - 16); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(W - 20, H - 24); ctx.lineTo(W - 20, H - 16); ctx.stroke();
    ctx.fillStyle = COL.inkMain;
    ctx.font = '9px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.fillText(nm + ' nm', W - px / 2 - 20, H - 25);
  }

  // ═══════════════════════════════════════════════════════
  // SECRET Stamp
  // ═══════════════════════════════════════════════════════
  _drawSecretStamp(ctx) {
    ctx.strokeStyle = COL.secretRed;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(12, 8, 70, 18);
    ctx.fillStyle = COL.secretRed;
    ctx.font = 'bold 12px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('SECRET', 47, 17);
    ctx.textBaseline = 'alphabetic';
  }

  // ═══════════════════════════════════════════════════════
  // Dynamic Entities (Phase 3)
  // ═══════════════════════════════════════════════════════
  _drawDistanceRings(ctx, fx, fy, radius) {
    ctx.save();
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = 'rgba(42,34,24,0.12)';
    ctx.lineWidth = 0.5;
    for (let ring = 2; ring <= radius; ring += 2) {
      const rpx = ring * HEX_SIZE * SQRT3;
      ctx.beginPath(); ctx.arc(fx, fy, rpx, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = 'rgba(42,34,24,0.2)';
      ctx.font = '9px Caveat, cursive';
      ctx.textAlign = 'center';
      ctx.fillText(ring * CELL_NM + ' nm', fx + rpx, fy - 3);
    }
    ctx.restore();
  }

  _drawOwnFleet(ctx, tf) {
    tf.carriers.forEach(c => {
      const [q, r] = this._worldToHex(c.position.lat, c.position.lon);
      const [px, py] = this._hexToPixel(q, r);
      const short = c.name.includes('Enterprise') ? 'ENT' : 'HOR';
      // Circle + cross
      ctx.strokeStyle = COL.inkMain;
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(px, py, 8, 0, Math.PI * 2); ctx.stroke();
      ctx.lineWidth = 0.8;
      ctx.beginPath(); ctx.moveTo(px - 5, py); ctx.lineTo(px + 5, py); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(px, py - 5); ctx.lineTo(px, py + 5); ctx.stroke();
      // Label
      ctx.fillStyle = COL.inkMain;
      ctx.font = 'bold 11px Caveat, cursive';
      ctx.textAlign = 'center';
      ctx.fillText(short, px, py - 12);
    });
  }

  _drawCourseArrow(ctx, fx, fy, course) {
    const len = HEX_SIZE * 3;
    const rad = (course - 90) * Math.PI / 180;
    const ax = fx + len * Math.cos(rad);
    const ay = fy + len * Math.sin(rad);
    // Main line
    ctx.strokeStyle = COL.inkMain;
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(fx, fy); ctx.lineTo(ax, ay); ctx.stroke();
    // Arrowhead
    const hl = 8, ha = 0.4;
    ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(ax - hl * Math.cos(rad - ha), ay - hl * Math.sin(rad - ha)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(ax - hl * Math.cos(rad + ha), ay - hl * Math.sin(rad + ha)); ctx.stroke();
    // Projected course (dashed)
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = COL.inkFade;
    ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(ax + len * 0.8 * Math.cos(rad), ay + len * 0.8 * Math.sin(rad)); ctx.stroke();
    ctx.setLineDash([]);
    // Label
    ctx.fillStyle = COL.inkMain;
    ctx.font = 'bold 11px Caveat, cursive';
    ctx.textAlign = 'left';
    ctx.fillText('COURSE ' + course + '°', ax + 6, ay - 2);
  }

  _drawEnemyContacts(ctx, state) {
    state.known_enemy.forEach(e => {
      const [q, r] = this._worldToHex(e.position.lat, e.position.lon);
      const [px, py] = this._hexToPixel(q, r);
      ctx.strokeStyle = COL.enemyRed;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.arc(px, py, 10, 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = COL.enemyRed;
      ctx.font = 'bold 14px Caveat, cursive';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('?', px, py);
      ctx.font = '9px Caveat, cursive';
      ctx.fillText('ENEMY', px, py + 16);
      ctx.textBaseline = 'alphabetic';
    });
  }

  _drawSearchSectors(ctx, state, fleetQ, fleetR) {
    state.active_scouts.filter(s => s.status === 'in_flight').forEach(s => {
      const cells = this._getSectorCells(fleetQ, fleetR, s.search_bearing_min, s.search_bearing_max, 20);
      ctx.save();
      ctx.globalAlpha = 0.06;
      ctx.strokeStyle = COL.inkMain;
      ctx.lineWidth = 0.4;
      cells.forEach(([cq, cr]) => {
        const [px, py] = this._hexToPixel(cq, cr);
        for (let d = -HEX_SIZE; d < HEX_SIZE; d += 4) {
          ctx.beginPath();
          ctx.moveTo(px + d, py - HEX_SIZE);
          ctx.lineTo(px + d + HEX_SIZE, py + HEX_SIZE);
          ctx.stroke();
        }
      });
      ctx.restore();
    });
  }

  // ═══════════════════════════════════════════════════════
  // Coordinate utilities
  // ═══════════════════════════════════════════════════════
  _hexToPixel(q, r) {
    return [
      HEX_SIZE * (SQRT3 * q + SQRT3 / 2 * r),
      HEX_SIZE * (3 / 2 * r),
    ];
  }

  _worldToHex(lat, lon) {
    const dlat = lat - REF_LAT;
    const dlon = lon - REF_LON;
    const nmNorth = dlat * 60;
    const nmEast = dlon * 60 * Math.cos(REF_LAT * Math.PI / 180);
    let q = nmEast / CELL_NM;
    let r = nmNorth / CELL_NM;
    const s = -q - r;
    let rq = Math.round(q), rr = Math.round(r), rs = Math.round(s);
    const qd = Math.abs(rq - q), rd = Math.abs(rr - r), sd = Math.abs(rs - s);
    if (qd > rd && qd > sd) rq = -rr - rs;
    else if (rd > sd) rr = -rq - rs;
    return [rq, rr];
  }

  _hexToWorld(q, r) {
    return [
      REF_LAT + (r * CELL_NM) / 60,
      REF_LON + (q * CELL_NM) / (60 * Math.cos(REF_LAT * Math.PI / 180)),
    ];
  }

  _hexBearing(q1, r1, q2, r2) {
    const [lat1, lon1] = this._hexToWorld(q1, r1);
    const [lat2, lon2] = this._hexToWorld(q2, r2);
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const lat1r = lat1 * Math.PI / 180, lat2r = lat2 * Math.PI / 180;
    const y = Math.sin(dLon) * Math.cos(lat2r);
    const x = Math.cos(lat1r) * Math.sin(lat2r) - Math.sin(lat1r) * Math.cos(lat2r) * Math.cos(dLon);
    return ((Math.atan2(y, x) * 180 / Math.PI) + 360) % 360;
  }

  _bearingInSector(b, min, max) {
    return min <= max ? (b >= min && b <= max) : (b >= min || b <= max);
  }

  _getSectorCells(cq, cr, bearingMin, bearingMax, radius) {
    const cells = [];
    for (let q = cq - radius; q <= cq + radius; q++) {
      for (let r = cr - radius; r <= cr + radius; r++) {
        const dist = Math.max(Math.abs(q - cq), Math.abs(r - cr), Math.abs(-(q - cq) - (r - cr)));
        if (dist > radius || dist === 0) continue;
        const bearing = this._hexBearing(cq, cr, q, r);
        if (this._bearingInSector(bearing, bearingMin, bearingMax)) cells.push([q, r]);
      }
    }
    return cells;
  }
}

// Export for main.js
window.MapRenderer = MapRenderer;
