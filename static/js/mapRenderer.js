/**
 * 中途岛指挥官 — Canvas 海图渲染器
 * 参考：1942年美军太平洋海图风格
 */

// ── Constants ──
const HEX_SIZE = 12;  // Reduced to fit 400nm battlefield in canvas
const SQRT3 = Math.sqrt(3);
const CELL_NM = 10;
const REF_LAT = 28.2;
const REF_LON = -177.4;

// ── Colors ──
const COL = {
  paperBase: '#f5edd6',
  inkMain: '#2a2218',
  inkFade: '#6b5d4a',
  inkFaint: '#a89878',
  enemyRed: '#8b2500',
  gridLine: 'rgba(140, 120, 90, 0.55)',
  lagoon: '#a8c8b8',
  reef: '#7a9a88',
  sand: '#d4c4a0',
  eastern: '#c8b890',
  runway: '#5a4d3a',
  depth: 'rgba(80,120,160,0.25)',
  secretRed: '#c0392b',
};

class MapRenderer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.dpr = window.devicePixelRatio || 1;
    this.width = 0;
    this.height = 0;
    this.centerX = 0;
    this.centerY = 0;
    // Label collision detection
    this.labelBounds = [];  // [{x, y, w, h}]
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
    this.labelBounds = [];  // Reset label collision tracker
    const ctx = this.ctx;
    const W = this.width, H = this.height;

    this._drawPaper(ctx, W, H);
    this._drawChartBorder(ctx, W, H);

    if (state) {
      const tf = state.task_forces[0];
      const c1 = tf.carriers[0];
      const [fqr, frr] = this._worldToHex(c1.position.lat, c1.position.lon);
      const [fpx, fpy] = this._hexToPixel(fqr, frr);
      const ox = this.centerX - fpx;
      const oy = this.centerY - fpy;

      ctx.save();
      ctx.translate(ox, oy);

      // Draw layers in order (back to front)
      this._drawDepthContours(ctx, fpx, fpy);
      this._drawGrid(ctx, W, H, ox, oy);
      this._drawDistanceRings(ctx, fpx, fpy, 8);
      this._drawSearchSectors(ctx, state, fqr, frr);
      this._drawScoutAircraft(ctx, state, fqr, frr);
      this._drawMidway(ctx, 0, 0, 1.5);
      this._drawOwnFleet(ctx, tf);
      this._drawEnemyContacts(ctx, state);

      ctx.restore();
    } else {
      this._drawGrid(ctx, W, H, 0, 0);
      this._drawMidway(ctx, this.centerX, this.centerY, 1.5);
    }

    this._drawCompass(ctx, W - 50, 50, 28);
    this._drawScaleBar(ctx, W, H);
    this._drawSecretStamp(ctx);
  }

  // ═══════════════════════════════════════════════════════
  // Paper Background
  // ═══════════════════════════════════════════════════════
  _drawPaper(ctx, W, H) {
    // Base
    ctx.fillStyle = COL.paperBase;
    ctx.fillRect(0, 0, W, H);
    // Subtle grain
    for (let i = 0; i < 4000; i++) {
      ctx.fillStyle = `rgba(42,34,24,${Math.random() * 0.025})`;
      ctx.fillRect(Math.random() * W, Math.random() * H, 1, 1);
    }
    // Age stains
    for (let i = 0; i < 3; i++) {
      const sx = Math.random() * W, sy = Math.random() * H, sr = 25 + Math.random() * 60;
      const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, sr);
      grad.addColorStop(0, 'rgba(170,150,110,0.04)');
      grad.addColorStop(1, 'rgba(170,150,110,0)');
      ctx.fillStyle = grad;
      ctx.fillRect(sx - sr, sy - sr, sr * 2, sr * 2);
    }
  }

  // ═══════════════════════════════════════════════════════
  // Chart Border (double line)
  // ═══════════════════════════════════════════════════════
  _drawChartBorder(ctx, W, H) {
    ctx.strokeStyle = COL.inkFade;
    ctx.lineWidth = 1;
    ctx.strokeRect(8, 8, W - 16, H - 16);
    ctx.lineWidth = 0.5;
    ctx.strokeRect(12, 12, W - 24, H - 24);
  }

  // ═══════════════════════════════════════════════════════
  // Grid (coordinate lines with degree markers)
  // ═══════════════════════════════════════════════════════
  _drawGrid(ctx, W, H, ox, oy) {
    const step = HEX_SIZE * SQRT3 * 3;
    ctx.strokeStyle = COL.gridLine;
    ctx.lineWidth = 0.3;
    ctx.setLineDash([4, 6]);

    // Vertical lines
    for (let x = ox % step; x < W; x += step) {
      ctx.beginPath(); ctx.moveTo(x, 14); ctx.lineTo(x, H - 14); ctx.stroke();
    }
    // Horizontal lines
    for (let y = oy % step; y < H; y += step) {
      ctx.beginPath(); ctx.moveTo(14, y); ctx.lineTo(W - 14, y); ctx.stroke();
    }
    ctx.setLineDash([]);

    // Degree labels at edges
    ctx.fillStyle = COL.inkFaint;
    ctx.font = '8px Caveat, cursive';
    ctx.textAlign = 'center';
    for (let x = ox % step; x < W; x += step) {
      const lonDeg = 177 + ((x - ox) / (HEX_SIZE * SQRT3)) * CELL_NM / 60;
      ctx.fillText(Math.abs(lonDeg).toFixed(0) + '°', x, 10);
      ctx.fillText(Math.abs(lonDeg).toFixed(0) + '°', x, H - 4);
    }
    ctx.textAlign = 'right';
    for (let y = oy % step; y < H; y += step) {
      const latDeg = 28 + ((y - oy) / (HEX_SIZE * 1.5)) * CELL_NM / 60;
      ctx.fillText(latDeg.toFixed(0) + '°', 22, y + 3);
      ctx.textAlign = 'left';
      ctx.fillText(latDeg.toFixed(0) + '°', W - 16, y + 3);
      ctx.textAlign = 'right';
    }
  }

  // ═══════════════════════════════════════════════════════
  // Depth Contours
  // ═══════════════════════════════════════════════════════
  _drawDepthContours(ctx, fx, fy) {
    ctx.save();
    ctx.strokeStyle = COL.depth;
    ctx.lineWidth = 0.6;
    ctx.setLineDash([3, 4]);
    // Concentric irregular circles around Midway (depth contours)
    const depths = [30, 50, 80, 120];
    depths.forEach((d, i) => {
      const r = 25 + i * 18;
      ctx.beginPath();
      ctx.ellipse(0, 0, r * 1.2, r, 0, 0, Math.PI * 2);
      ctx.stroke();
    });
    ctx.setLineDash([]);
    ctx.restore();
  }

  // ═══════════════════════════════════════════════════════
  // Midway Atoll (improved)
  // ═══════════════════════════════════════════════════════
  _drawMidway(ctx, cx, cy, scale) {
    ctx.save();
    ctx.translate(cx, cy);
    const s = scale;

    // Outer reef ring (irregular, organic shape)
    ctx.fillStyle = 'rgba(180,210,195,0.3)';
    ctx.strokeStyle = COL.reef;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    // Organic reef shape using bezier curves
    ctx.moveTo(-14 * s, 2 * s);
    ctx.bezierCurveTo(-14 * s, -8 * s, -8 * s, -13 * s, 0, -12 * s);
    ctx.bezierCurveTo(8 * s, -13 * s, 14 * s, -8 * s, 14 * s, 2 * s);
    ctx.bezierCurveTo(14 * s, 8 * s, 8 * s, 13 * s, 0, 12 * s);
    ctx.bezierCurveTo(-8 * s, 13 * s, -14 * s, 8 * s, -14 * s, 2 * s);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Lagoon (lighter blue-green)
    ctx.fillStyle = COL.lagoon;
    ctx.beginPath();
    ctx.ellipse(0, 0, 10 * s, 8 * s, 0, 0, Math.PI * 2);
    ctx.fill();

    // Sand Island (western, larger, irregular shape)
    ctx.fillStyle = COL.sand;
    ctx.strokeStyle = COL.inkMain;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    // Organic Sand Island shape
    ctx.moveTo(-8 * s, -2 * s);
    ctx.bezierCurveTo(-7 * s, -4 * s, -3 * s, -4 * s, -2 * s, -2 * s);
    ctx.bezierCurveTo(-1 * s, -1 * s, -1 * s, 1 * s, -2 * s, 2 * s);
    ctx.bezierCurveTo(-4 * s, 3 * s, -7 * s, 2 * s, -8 * s, -2 * s);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Eastern Island (triangular, more defined)
    ctx.fillStyle = COL.eastern;
    ctx.beginPath();
    ctx.moveTo(5 * s, -4 * s);
    ctx.bezierCurveTo(8 * s, -3 * s, 11 * s, -1 * s, 10 * s, 1 * s);
    ctx.bezierCurveTo(9 * s, 3 * s, 6 * s, 3 * s, 4 * s, 2 * s);
    ctx.bezierCurveTo(3 * s, 0 * s, 4 * s, -3 * s, 5 * s, -4 * s);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Runways on Eastern Island (triangle pattern)
    ctx.strokeStyle = COL.runway;
    ctx.lineWidth = 0.8;
    // Main runway (NW-SE)
    ctx.beginPath(); ctx.moveTo(5.5 * s, -3 * s); ctx.lineTo(9 * s, 0.5 * s); ctx.stroke();
    // Cross runway (NE-SW)
    ctx.beginPath(); ctx.moveTo(8 * s, -2 * s); ctx.lineTo(5 * s, 1.5 * s); ctx.stroke();
    // Third runway (E-W)
    ctx.beginPath(); ctx.moveTo(5 * s, -0.5 * s); ctx.lineTo(9.5 * s, -0.5 * s); ctx.stroke();

    // Spit Island (small dot SE of Sand Island)
    ctx.fillStyle = COL.sand;
    ctx.strokeStyle = COL.inkMain;
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.ellipse(-1 * s, 5 * s, 2 * s, 1 * s, -0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Channel between islands
    ctx.strokeStyle = COL.reef;
    ctx.lineWidth = 0.5;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(-1 * s, -1 * s);
    ctx.lineTo(4 * s, -1 * s);
    ctx.stroke();
    ctx.setLineDash([]);

    // Labels
    ctx.fillStyle = COL.inkMain;
    ctx.font = 'bold 12px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.fillText('MIDWAY ATOLL', 0, -16 * s);
    ctx.font = '9px Caveat, cursive';
    ctx.fillStyle = COL.inkFade;
    ctx.fillText('28°12\'N  177°21\'W', 0, -14 * s + 12);

    // Island labels (inside ctx.translate context)
    this._tryPlaceLabel(ctx, 'SAND ISLAND', -5 * s, 6 * s, '9px Caveat, cursive', COL.inkMain,
      [[0, 6*s], [0, -6*s], [-8*s, 0]], 2);
    this._tryPlaceLabel(ctx, 'EASTERN ISLAND', 7 * s, 5 * s, '9px Caveat, cursive', COL.inkMain,
      [[0, 6*s], [0, -6*s], [8*s, 0]], 2);
    this._tryPlaceLabel(ctx, 'Henderson Fld', 7 * s, 9 * s, '7px Caveat, cursive', COL.inkFade,
      [[0, 4*s], [0, -8*s]], 1);

    ctx.restore();
  }

  // ═══════════════════════════════════════════════════════
  // Scout Aircraft
  // ═══════════════════════════════════════════════════════
  _drawScoutAircraft(ctx, state, fleetQ, fleetR) {
    const [fx, fy] = this._hexToPixel(fleetQ, fleetR);

    state.active_scouts.forEach(scout => {
      if (scout.status !== 'in_flight') return;

      // Calculate search sector midpoint angle (always needed for direction)
      const midAngle = ((scout.search_bearing_min + scout.search_bearing_max) / 2 - 90) * Math.PI / 180;

      // Use actual position from API if available
      let px, py;
      if (scout.position) {
        const [sq, sr] = this._worldToHex(scout.position.lat, scout.position.lon);
        [px, py] = this._hexToPixel(sq, sr);
      } else {
        // Fallback: estimate from phase
        const dist = scout.search_distance_nm / CELL_NM * HEX_SIZE * SQRT3;
        const progress = scout.phase === 'preparing' ? 0.1 :
                        scout.phase === 'outbound' ? 0.6 :
                        scout.phase === 'searching' ? 0.8 : 0.3;
        px = fx + dist * progress * Math.cos(midAngle);
        py = fy + dist * progress * Math.sin(midAngle);
      }

      ctx.save();
      ctx.translate(px, py);

      // Aircraft symbol (small triangle)
      const isReturning = scout.phase === 'returning';
      const fuelColor = scout.fuel_pct > 30 ? COL.inkMain :
                        scout.fuel_pct > 15 ? '#8a6020' : COL.enemyRed;

      ctx.strokeStyle = isReturning ? COL.inkFade : fuelColor;
      ctx.lineWidth = isReturning ? 1 : 1.5;
      if (isReturning) ctx.setLineDash([2, 2]);

      // Triangle pointing in direction of travel
      const angle = isReturning ? (scout.return_heading - 90) * Math.PI / 180 : midAngle;
      const size = 6;
      ctx.beginPath();
      ctx.moveTo(Math.cos(angle) * size, Math.sin(angle) * size);
      ctx.lineTo(Math.cos(angle + 2.3) * size * 0.6, Math.sin(angle + 2.3) * size * 0.6);
      ctx.lineTo(Math.cos(angle - 2.3) * size * 0.6, Math.sin(angle - 2.3) * size * 0.6);
      ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);

      // Label
      ctx.fillStyle = fuelColor;
      ctx.font = '8px Caveat, cursive';
      ctx.textAlign = 'center';
      const phaseLabel = scout.phase === 'searching' ? 'SEARCH' :
                         scout.phase === 'returning' ? 'RETURN' :
                         scout.phase === 'preparing' ? 'PREP' : 'EN ROUTE';
      ctx.fillText(scout.id, 0, -10);
      ctx.font = '7px Caveat, cursive';
      ctx.fillStyle = COL.inkFade;
      ctx.fillText(`${Math.round(scout.fuel_pct)}% ${phaseLabel}`, 0, 12);
      if (scout.aircraft_lost > 0) {
        ctx.fillStyle = COL.enemyRed;
        ctx.fillText(`-${scout.aircraft_lost}`, 8, 12);
      }

      ctx.restore();
    });
  }

  // ═══════════════════════════════════════════════════════
  // Distance Rings
  // ═══════════════════════════════════════════════════════
  _drawDistanceRings(ctx, fx, fy, radius) {
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.lineWidth = 0.5;
    for (let ring = 2; ring <= radius; ring += 2) {
      const rpx = ring * HEX_SIZE * SQRT3;
      ctx.strokeStyle = ring === 2 ? 'rgba(42,34,24,0.3)' : 'rgba(42,34,24,0.18)';
      ctx.beginPath(); ctx.arc(fx, fy, rpx, 0, Math.PI * 2); ctx.stroke();
      // Label at 3 o'clock
      ctx.fillStyle = 'rgba(42,34,24,0.4)';
      ctx.font = '9px Caveat, cursive';
      ctx.textAlign = 'left';
      ctx.fillText(ring * CELL_NM + 'nm', fx + rpx + 3, fy + 3);
    }
    ctx.setLineDash([]);
    ctx.restore();
  }

  // ═══════════════════════════════════════════════════════
  // Own Fleet (improved)
  // ═══════════════════════════════════════════════════════
  _drawOwnFleet(ctx, tf) {
    tf.carriers.forEach(c => {
      const [q, r] = this._worldToHex(c.position.lat, c.position.lon);
      const [px, py] = this._hexToPixel(q, r);
      const short = c.name.includes('Enterprise') ? 'ENT' : 'HOR';

      // Circle
      ctx.strokeStyle = COL.inkMain;
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(px, py, 10, 0, Math.PI * 2); ctx.stroke();

      // Cross inside
      ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(px - 6, py); ctx.lineTo(px + 6, py); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(px, py - 6); ctx.lineTo(px, py + 6); ctx.stroke();

      // Label (priority: high — fleet is important)
      this._tryPlaceLabel(ctx, short, px, py - 16, 'bold 13px Caveat, cursive', COL.inkMain,
        [[0, -16], [16, -10], [-16, -10], [0, 18]], 3);

      // Course arrow for this carrier
      this._drawSingleCourseArrow(ctx, px, py, tf.course);
    });
  }

  _drawSingleCourseArrow(ctx, fx, fy, course) {
    const len = HEX_SIZE * 2.5;
    const rad = (course - 90) * Math.PI / 180;
    const ax = fx + len * Math.cos(rad);
    const ay = fy + len * Math.sin(rad);

    ctx.strokeStyle = COL.inkMain;
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(fx, fy); ctx.lineTo(ax, ay); ctx.stroke();

    // Arrowhead
    const hl = 8, ha = 0.4;
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - hl * Math.cos(rad - ha), ay - hl * Math.sin(rad - ha));
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - hl * Math.cos(rad + ha), ay - hl * Math.sin(rad + ha));
    ctx.stroke();

    // Projected course (dashed)
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = COL.inkFade;
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax + len * 0.5 * Math.cos(rad), ay + len * 0.5 * Math.sin(rad));
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // ═══════════════════════════════════════════════════════
  // Enemy Contacts (improved)
  // ═══════════════════════════════════════════════════════
  _drawEnemyContacts(ctx, state) {
    state.known_enemy.forEach((e, i) => {
      const [q, r] = this._worldToHex(e.position.lat, e.position.lon);
      const [px, py] = this._hexToPixel(q, r);

      // Dashed circle
      ctx.strokeStyle = COL.enemyRed;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.arc(px, py, 12, 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]);

      // Question mark
      ctx.fillStyle = COL.enemyRed;
      ctx.font = 'bold 18px Caveat, cursive';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('?', px, py);

      // Label (priority: medium — enemy is important but "?" is primary)
      this._tryPlaceLabel(ctx, 'ENEMY', px, py + 20, '10px Caveat, cursive', COL.enemyRed,
        [[0, 20], [16, 14], [-16, 14], [0, -22]], 2);
    });
  }

  // ═══════════════════════════════════════════════════════
  // Search Sectors (wedge-shaped扇形 with hatching)
  // ═══════════════════════════════════════════════════════
  _drawSearchSectors(ctx, state, fleetQ, fleetR) {
    const [fx, fy] = this._hexToPixel(fleetQ, fleetR);
    const sectorRadius = 8 * HEX_SIZE * SQRT3;

    state.active_scouts.filter(s => s.status === 'in_flight').forEach(s => {
      const startRad = ((s.search_bearing_min - 90) * Math.PI) / 180;
      const endRad = ((s.search_bearing_max - 90) * Math.PI) / 180;

      ctx.save();

      // Wedge fill (semi-transparent)
      ctx.fillStyle = 'rgba(160,140,110,0.15)';
      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.arc(fx, fy, sectorRadius, startRad, endRad);
      ctx.closePath();
      ctx.fill();

      // Wedge border
      ctx.strokeStyle = 'rgba(42,34,24,0.3)';
      ctx.lineWidth = 1.2;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.arc(fx, fy, sectorRadius, startRad, endRad);
      ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);

      // Hatching inside wedge
      ctx.strokeStyle = 'rgba(42,34,24,0.12)';
      ctx.lineWidth = 0.6;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.arc(fx, fy, sectorRadius, startRad, endRad);
      ctx.closePath();
      ctx.clip();
      for (let d = -sectorRadius; d < sectorRadius; d += 6) {
        ctx.beginPath();
        ctx.moveTo(fx + d, fy - sectorRadius);
        ctx.lineTo(fx + d + sectorRadius, fy + sectorRadius);
        ctx.stroke();
      }
      ctx.restore();

      // Sector label (priority: low — can be hidden)
      const midAngle = (startRad + endRad) / 2;
      const labelR = sectorRadius * 0.7;
      const lx = fx + labelR * Math.cos(midAngle);
      const ly = fy + labelR * Math.sin(midAngle);
      this._tryPlaceLabel(ctx, s.direction, lx, ly, '10px Caveat, cursive', COL.inkMain,
        [[0, 0], [0, -14], [14, 0], [-14, 0]], 1);

      ctx.restore();
    });
  }

  // ═══════════════════════════════════════════════════════
  // Compass Rose (improved)
  // ═══════════════════════════════════════════════════════
  _drawCompass(ctx, x, y, size) {
    ctx.save();
    ctx.translate(x, y);

    // Outer circles
    ctx.strokeStyle = COL.inkFade;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(0, 0, size, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, size * 0.88, 0, Math.PI * 2); ctx.stroke();

    // Inner decorative circle
    ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.arc(0, 0, size * 0.3, 0, Math.PI * 2); ctx.stroke();

    // Star points (8 directions)
    for (let i = 0; i < 8; i++) {
      const a = i * Math.PI / 4;
      const r1 = i % 2 === 0 ? size * 0.88 : size * 0.55;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(Math.sin(a) * r1, -Math.cos(a) * r1);
      ctx.strokeStyle = i % 2 === 0 ? COL.inkMain : COL.inkFade;
      ctx.lineWidth = i % 2 === 0 ? 1.2 : 0.6;
      ctx.stroke();
    }

    // Cardinal labels
    ctx.fillStyle = COL.inkMain;
    ctx.font = 'bold 12px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', 0, -size - 10);
    ctx.fillText('S', 0, size + 12);
    ctx.fillText('E', size + 12, 0);
    ctx.fillText('W', -size - 12, 0);

    // Intercardinal labels
    ctx.font = '9px Caveat, cursive';
    ctx.fillStyle = COL.inkFade;
    const is = size * 0.72;
    ctx.fillText('NE', is, -is);
    ctx.fillText('SE', is, is);
    ctx.fillText('SW', -is, is);
    ctx.fillText('NW', -is, -is);

    ctx.restore();
  }

  // ═══════════════════════════════════════════════════════
  // Scale Bar
  // ═══════════════════════════════════════════════════════
  _drawScaleBar(ctx, W, H) {
    const nm = 50;
    const px = (nm / CELL_NM) * HEX_SIZE * SQRT3;
    const x = W - px - 30, y = H - 25;

    ctx.strokeStyle = COL.inkMain;
    ctx.lineWidth = 1;
    // Main line
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + px, y); ctx.stroke();
    // Ticks
    ctx.beginPath(); ctx.moveTo(x, y - 4); ctx.lineTo(x, y + 4); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x + px, y - 4); ctx.lineTo(x + px, y + 4); ctx.stroke();
    // Mid tick
    ctx.beginPath(); ctx.moveTo(x + px / 2, y - 2); ctx.lineTo(x + px / 2, y + 2); ctx.stroke();

    // Labels
    ctx.fillStyle = COL.inkMain;
    ctx.font = '10px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.fillText('0', x, y - 8);
    ctx.fillText(nm + ' nm', x + px, y - 8);
  }

  // ═══════════════════════════════════════════════════════
  // Label Placement System
  // ═══════════════════════════════════════════════════════

  _checkOverlap(x, y, w, h, margin = 2) {
    for (const b of this.labelBounds) {
      if (x - margin < b.x + b.w && x + w + margin > b.x &&
          y - margin < b.y + b.h && y + h + margin > b.y) {
        return true;
      }
    }
    return false;
  }

  _clampToCanvas(x, y, w, h, padding = 4) {
    const cx = Math.max(padding, Math.min(this.width - w - padding, x));
    const cy = Math.max(padding, Math.min(this.height - h - padding, y));
    return [cx, cy];
  }

  _drawLeaderLine(ctx, fromX, fromY, toX, toY) {
    ctx.strokeStyle = 'rgba(42,34,24,0.2)';
    ctx.lineWidth = 0.5;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(fromX, fromY);
    ctx.lineTo(toX, toY);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  _tryPlaceLabel(ctx, text, anchorX, anchorY, font, color, offsets, priority = 1) {
    ctx.font = font;
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const metrics = ctx.measureText(text);
    const lw = metrics.width + 6;
    const lh = parseInt(font) + 4;

    for (const [ox, oy] of offsets) {
      const x = anchorX + ox;
      const y = anchorY + oy;
      // Check canvas bounds
      const [cx, cy] = this._clampToCanvas(x - lw/2, y - lh/2, lw, lh);
      // Check overlap
      if (!this._checkOverlap(cx, cy, lw, lh)) {
        ctx.fillText(text, cx + lw/2, cy + lh/2);
        this.labelBounds.push({ x: cx, y: cy, w: lw, h: lh });
        // Draw leader line if offset is significant
        const dist = Math.sqrt(ox*ox + oy*oy);
        if (dist > 20) {
          this._drawLeaderLine(ctx, anchorX, anchorY, cx + lw/2, cy + lh/2);
        }
        return true;
      }
    }
    // Low priority labels can be hidden
    if (priority < 2) return false;
    // High priority: force place at first offset
    const [ox, oy] = offsets[0];
    const x = anchorX + ox;
    const y = anchorY + oy;
    const [cx, cy] = this._clampToCanvas(x - lw/2, y - lh/2, lw, lh);
    ctx.globalAlpha = 0.5;
    ctx.fillText(text, cx + lw/2, cy + lh/2);
    ctx.globalAlpha = 1.0;
    this.labelBounds.push({ x: cx, y: cy, w: lw, h: lh });
    return true;
  }

  // ═══════════════════════════════════════════════════════
  // SECRET Stamp
  // ═══════════════════════════════════════════════════════
  _drawSecretStamp(ctx) {
    ctx.save();
    ctx.translate(24, 24);

    // Border
    ctx.strokeStyle = COL.secretRed;
    ctx.lineWidth = 2;
    ctx.strokeRect(0, 0, 80, 24);

    // Text
    ctx.fillStyle = COL.secretRed;
    ctx.font = 'bold 16px Caveat, cursive';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('SECRET', 40, 12);

    ctx.restore();
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


}

window.MapRenderer = MapRenderer;
