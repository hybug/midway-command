/**
 * 中途岛指挥官 — Canvas 海图渲染器
 * 参考：1942年美军太平洋海图风格
 *
 * 动画系统：requestAnimationFrame 循环 + lerp 平滑过渡
 * 交互系统：点击确认敌军标记、悬停提示
 * 视觉效果：Perlin noise 手绘线条、脉冲动画
 */

// ── Constants ──
const HEX_SIZE = 12;
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
  confirmGold: '#c8a020',
};

// ── Perlin Noise (简化版) ──
class PerlinNoise {
  constructor(seed = 0) {
    this.seed = seed;
    this.p = [];
    for (let i = 0; i < 256; i++) this.p[i] = i;
    // Fisher-Yates shuffle with seed
    let s = seed;
    for (let i = 255; i > 0; i--) {
      s = (s * 16807 + 0) % 2147483647;
      const j = s % (i + 1);
      [this.p[i], this.p[j]] = [this.p[j], this.p[i]];
    }
    this.p = this.p.concat(this.p);
  }
  noise2d(x, y) {
    const X = Math.floor(x) & 255, Y = Math.floor(y) & 255;
    x -= Math.floor(x); y -= Math.floor(y);
    const u = x * x * (3 - 2 * x), v = y * y * (3 - 2 * y);
    const A = this.p[X] + Y, B = this.p[X + 1] + Y;
    const lerp = (t, a, b) => a + t * (b - a);
    return lerp(v,
      lerp(u, this._grad(this.p[A], x, y), this._grad(this.p[B], x - 1, y)),
      lerp(u, this._grad(this.p[A + 1], x, y - 1), this._grad(this.p[B + 1], x - 1, y - 1))
    );
  }
  _grad(hash, x, y) {
    return (hash & 1) === 0 ? x + y : -x + y;
  }
}

const perlin = new PerlinNoise(42);

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
    this.labelBounds = [];

    // ── 动画状态 ──
    this._animState = {
      fleetPositions: {},      // {name: {x, y, targetX, targetY}}
      enemyPulse: 0,           // 0-1 脉冲周期
      scoutPositions: {},      // {id: {x, y, targetX, targetY}}
      confirmAnimations: [],   // [{x, y, progress, startTime}]
      sectorProgress: {},      // {id: 0-1 扩展进度}
    };
    this._lastTime = 0;
    this._running = false;

    // ── 交互状态 ──
    this._hoverTarget = null;  // {type, data, x, y}
    this._clickHandlers = [];
    this._setupInteraction();
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

  // ═══════════════════════════════════════════════════════
  // 动画系统
  // ═══════════════════════════════════════════════════════

  startAnimationLoop() {
    if (this._running) return;
    this._running = true;
    this._lastTime = performance.now();
    this._animLoop();
  }

  stopAnimationLoop() {
    this._running = false;
  }

  _animLoop() {
    if (!this._running) return;
    const now = performance.now();
    const dt = (now - this._lastTime) / 1000; // 秒
    this._lastTime = now;

    // 更新动画状态
    this._updateAnimations(dt);

    // 渲染
    if (this._currentState) {
      this.render(this._currentState);
    }

    requestAnimationFrame(() => this._animLoop());
  }

  _updateAnimations(dt) {
    // 敌军标记脉冲（0.5Hz）
    this._animState.enemyPulse = (this._animState.enemyPulse + dt * 0.5) % 1;

    // 确认动画
    this._animState.confirmAnimations = this._animState.confirmAnimations.filter(a => {
      a.progress += dt / 0.7; // 0.7秒完成
      return a.progress < 1;
    });

    // 搜索扇面扩展
    for (const id in this._animState.sectorProgress) {
      const p = this._animState.sectorProgress[id];
      if (p < 1) {
        this._animState.sectorProgress[id] = Math.min(1, p + dt * 0.3);
      }
    }
  }

  _lerp(a, b, t) {
    return a + (b - a) * Math.min(1, t);
  }

  _lerpPos(pos, targetX, targetY, dt, speed = 3) {
    const t = 1 - Math.exp(-speed * dt);
    pos.x = this._lerp(pos.x, targetX, t);
    pos.y = this._lerp(pos.y, targetY, t);
  }

  // ═══════════════════════════════════════════════════════
  // 交互系统
  // ═══════════════════════════════════════════════════════

  _setupInteraction() {
    this.canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
    this.canvas.addEventListener('click', (e) => this._onClick(e));
    this.canvas.style.cursor = 'default';
  }

  _onMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    this._hoverTarget = null;
    this.canvas.style.cursor = 'default';

    if (!this._currentState) return;

    // 检查是否悬停在待确认敌军标记上
    const pending = this._currentState.pending_suggestions || [];
    for (let i = 0; i < pending.length; i++) {
      const sug = pending[i];
      if (sug.action_type !== 'launch_scout') continue;
      const d = sug.details || {};
      const sectorStart = d.sector_start || 280;
      const sectorEnd = d.sector_end || 340;
      const rangeNm = d.range_nm || 200;

      // 计算扇面中心位置
      const midAngle = ((sectorStart + sectorEnd) / 2 - 90) * Math.PI / 180;
      const sectorRadius = rangeNm / CELL_NM * HEX_SIZE * SQRT3 * 0.8;
      const tf = this._currentState.task_forces[0];
      const c1 = tf.carriers[0];
      const [fqr, frr] = this._worldToHex(c1.position.lat, c1.position.lon);
      const [fpx, fpy] = this._hexToPixel(fqr, frr);
      const ox = this.centerX - fpx;
      const oy = this.centerY - fpy;
      const lx = ox + fpx + sectorRadius * 0.6 * Math.cos(midAngle);
      const ly = oy + fpy + sectorRadius * 0.6 * Math.sin(midAngle);

      if (Math.hypot(mx - lx, my - ly) < 20) {
        this._hoverTarget = { type: 'pending_scout', index: i, x: lx, y: ly };
        this.canvas.style.cursor = 'pointer';
        break;
      }
    }

    // 检查是否悬停在已确认敌军标记上
    const enemies = this._currentState.known_enemy || [];
    for (let i = 0; i < enemies.length; i++) {
      const e = enemies[i];
      const [eq, er] = this._worldToHex(e.position.lat, e.position.lon);
      const [epx, epy] = this._hexToPixel(eq, er);
      const tf = this._currentState.task_forces[0];
      const c1 = tf.carriers[0];
      const [fqr, frr] = this._worldToHex(c1.position.lat, c1.position.lon);
      const ox = this.centerX - this._hexToPixel(fqr, frr)[0];
      const oy = this.centerY - this._hexToPixel(fqr, frr)[1];
      const sx = ox + epx;
      const sy = oy + epy;

      if (Math.hypot(mx - sx, my - sy) < 15) {
        this._hoverTarget = { type: 'enemy', index: i, x: sx, y: sy };
        this.canvas.style.cursor = 'pointer';
        break;
      }
    }
  }

  _onClick(e) {
    if (!this._hoverTarget) return;

    if (this._hoverTarget.type === 'pending_scout') {
      // 触发确认回调
      if (this._onConfirmContact) {
        this._onConfirmContact(this._hoverTarget.index);
      }
    }
  }

  onConfirmContact(callback) {
    this._onConfirmContact = callback;
  }

  triggerConfirmAnimation(x, y) {
    this._animState.confirmAnimations.push({ x, y, progress: 0, startTime: performance.now() });
  }

  render(state) {
    this._currentState = state;
    this.resize();
    this.labelBounds = [];
    const ctx = this.ctx;
    const W = this.width, H = this.height;

    // Task 7.8：渲染入口最前部——A1 旧海图底图（纸底/经纬网/环礁/距离环/罗盘/比例尺）
    // 注：传 CSS 像素 W/H（ctx 已按 dpr setTransform，传 canvas.width 设备像素会放大 dpr 倍）
    ChartRenderer.drawAll(ctx, W, H);

    // Task 7.8：旧底图层已被 ChartRenderer.drawAll 取代（保留代码备查）
    // this._drawPaper(ctx, W, H);
    // this._drawChartBorder(ctx, W, H);

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
      // Task 7.8：旧地形/六边形网格/距离环/环礁已被 ChartRenderer.drawAll 取代（保留代码备查）
      // this._drawDepthContours(ctx, fpx, fpy);
      // this._drawGrid(ctx, W, H, ox, oy);
      // this._drawDistanceRings(ctx, fpx, fpy, 8);
      this._drawPendingRecon(ctx, state, fqr, frr);
      this._drawSearchSectors(ctx, state, fqr, frr);
      this._drawScoutAircraft(ctx, state, fqr, frr);
      // this._drawMidway(ctx, 0, 0, 1.5);
      this._drawOwnFleet(ctx, tf);
      this._drawEnemyContacts(ctx, state);

      // 绘制确认动画
      this._drawConfirmAnimations(ctx, ox, oy);

      ctx.restore();
    } else {
      // Task 7.8：旧底图层已被 ChartRenderer.drawAll 取代（保留代码备查）
      // this._drawGrid(ctx, W, H, 0, 0);
      // this._drawMidway(ctx, this.centerX, this.centerY, 1.5);
    }

    // Task 7.8：旧罗盘/比例尺已被 ChartRenderer.drawCompassRose/drawScaleBar 取代（保留代码备查）
    // this._drawCompass(ctx, W - 50, 50, 28);
    // this._drawScaleBar(ctx, W, H);
    // 设计图 A1 地图上无 SECRET 印章（印章属 Task 8.5 军令纸），旧戳与 A1 冲突（方法体保留）
    // this._drawSecretStamp(ctx);

    // 绘制悬停提示
    this._drawTooltip(ctx);
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

      // Task 7.9：舰队标记改由 ChartRenderer.drawTaskForceMarker 绘制
      // （光栅计数牌 ENT/HOR + CSE 航向线 + 虚线引导线）。
      // 字段映射：数据模型无 callsign 字段，沿用既有 name→ENT/HOR 推导；
      // courseDeg 取 TaskForce.course（与旧航向箭头同源）。
      ChartRenderer.drawTaskForceMarker(ctx, { x: px, y: py, callsign: short, courseDeg: tf.course });

      // Task 7.9：旧航母图标/标签/航向箭头由舰队标记取代（保留代码备查）
      // // Try SVG icon first
      // const icon = getIcon('carrier_us');
      // if (icon) {
      //   const iconW = 30, iconH = 16;
      //   ctx.drawImage(icon, px - iconW/2, py - iconH/2, iconW, iconH);
      // } else {
      //   // Fallback: circle + cross
      //   ctx.strokeStyle = COL.inkMain;
      //   ctx.lineWidth = 2;
      //   ctx.beginPath(); ctx.arc(px, py, 10, 0, Math.PI * 2); ctx.stroke();
      //   ctx.lineWidth = 1.2;
      //   ctx.beginPath(); ctx.moveTo(px - 6, py); ctx.lineTo(px + 6, py); ctx.stroke();
      //   ctx.beginPath(); ctx.moveTo(px, py - 6); ctx.lineTo(px, py + 6); ctx.stroke();
      // }
      //
      // // Label (priority: high — fleet is important)
      // this._tryPlaceLabel(ctx, short, px, py - 16, 'bold 13px Caveat, cursive', COL.inkMain,
      //   [[0, -16], [16, -10], [-16, -10], [0, 18]], 3);
      //
      // // Course arrow for this carrier
      // this._drawSingleCourseArrow(ctx, px, py, tf.course);
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
  // Enemy Contacts (脉冲动画 + 手绘线条)
  // ═══════════════════════════════════════════════════════
  _drawEnemyContacts(ctx, state) {
    const pulse = this._animState.enemyPulse;
    const pulseAlpha = 0.3 + 0.2 * Math.sin(pulse * Math.PI * 2);

    state.known_enemy.forEach((e, i) => {
      const [q, r] = this._worldToHex(e.position.lat, e.position.lon);
      const [px, py] = this._hexToPixel(q, r);

      // 脉冲光晕（保留既有动画）
      ctx.save();
      ctx.globalAlpha = pulseAlpha;
      ctx.fillStyle = COL.enemyRed;
      ctx.beginPath();
      ctx.arc(px, py, 18, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // Task 7.9：敌情标记改由 ChartRenderer.drawEnemyContact 绘制
      // （enemy_tag_q 光栅优先，大小随置信度 high 46 / medium 34 / low 26）。
      // 字段映射：known_enemy[].confidence 即置信档字段（'high'|'medium'|'low'，pydantic 默认 "low"；
      // 代码 `|| 'medium'` 仅是字段缺失时的渲染回退）。
      ChartRenderer.drawEnemyContact(ctx, { x: px, y: py, confidence: e.confidence || 'medium' });

      // Task 7.9：旧手绘圈/问号/置信度文字/ENEMY 标签由标记资产取代（ENEMY 字样已内嵌素材，保留代码备查）
      // // 手绘感虚线圈（Perlin noise 抖动）
      // this._drawHandDrawnCircle(ctx, px, py, 12, COL.enemyRed, 1.5);
      //
      // // 问号
      // ctx.fillStyle = COL.enemyRed;
      // ctx.font = 'bold 18px Caveat, cursive';
      // ctx.textAlign = 'center';
      // ctx.textBaseline = 'middle';
      // ctx.fillText('?', px, py);
      //
      // // 置信度指示
      // const conf = e.confidence || 'medium';
      // const confColor = conf === 'high' ? COL.enemyRed : conf === 'medium' ? '#a04000' : COL.inkFaint;
      // ctx.fillStyle = confColor;
      // ctx.font = '8px Caveat, cursive';
      // ctx.fillText(conf.toUpperCase(), px, py + 16);
      //
      // // Label
      // this._tryPlaceLabel(ctx, 'ENEMY', px, py + 24, '10px Caveat, cursive', COL.enemyRed,
      //   [[0, 24], [16, 18], [-16, 18], [0, -26]], 2);
    });
  }

  // ═══════════════════════════════════════════════════════
  // 手绘感圆形（Perlin noise 抖动）
  // ═══════════════════════════════════════════════════════
  _drawHandDrawnCircle(ctx, cx, cy, radius, color, lineWidth) {
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    const steps = 36;
    for (let i = 0; i <= steps; i++) {
      const angle = (i / steps) * Math.PI * 2;
      const noise = perlin.noise2d(cx * 0.01 + Math.cos(angle) * 2, cy * 0.01 + Math.sin(angle) * 2);
      const r = radius + noise * 2;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
  }

  // ═══════════════════════════════════════════════════════
  // 确认动画（画圈效果）
  // ═══════════════════════════════════════════════════════
  _drawConfirmAnimations(ctx, ox, oy) {
    this._animState.confirmAnimations.forEach(anim => {
      const progress = anim.progress;
      const endAngle = progress * Math.PI * 2;
      const radius = 15;

      ctx.save();
      ctx.strokeStyle = COL.confirmGold;
      ctx.lineWidth = 3;
      ctx.globalAlpha = 1 - progress * 0.5;
      ctx.beginPath();
      ctx.arc(anim.x - ox, anim.y - oy, radius, -Math.PI / 2, -Math.PI / 2 + endAngle);
      ctx.stroke();

      // 闪光效果
      if (progress < 0.3) {
        ctx.globalAlpha = (0.3 - progress) * 2;
        ctx.fillStyle = COL.confirmGold;
        ctx.beginPath();
        ctx.arc(anim.x - ox, anim.y - oy, radius * (1 + progress), 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    });
  }

  // ═══════════════════════════════════════════════════════
  // 悬停提示
  // ═══════════════════════════════════════════════════════
  _drawTooltip(ctx) {
    if (!this._hoverTarget) return;

    const { type, x, y } = this._hoverTarget;
    let text = '';
    if (type === 'pending_scout') {
      text = '点击确认敌情';
    } else if (type === 'enemy') {
      text = '已确认敌军';
    }

    if (!text) return;

    ctx.save();
    ctx.font = '11px "Special Elite", monospace';
    const metrics = ctx.measureText(text);
    const tw = metrics.width + 12;
    const th = 20;
    const tx = x - tw / 2;
    const ty = y - th - 10;

    // 背景
    ctx.fillStyle = 'rgba(42, 34, 24, 0.85)';
    ctx.fillRect(tx, ty, tw, th);
    ctx.strokeStyle = COL.confirmGold;
    ctx.lineWidth = 1;
    ctx.strokeRect(tx, ty, tw, th);

    // 文字
    ctx.fillStyle = '#f5edd6';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, x, ty + th / 2);
    ctx.restore();
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
  // Pending Recon Plan (dashed, semi-transparent)
  // ═══════════════════════════════════════════════════════
  _drawPendingRecon(ctx, state, fleetQ, fleetR) {
    const [fx, fy] = this._hexToPixel(fleetQ, fleetR);
    const pending = state.pending_suggestions || [];

    pending.forEach(sug => {
      if (sug.action_type !== 'launch_scout') return;
      const d = sug.details || {};
      const dir = d.direction || 'northwest';
      const count = d.aircraft_count || 4;
      const sectorStart = d.sector_start || 280;
      const sectorEnd = d.sector_end || 340;
      const rangeNm = d.range_nm || 200;
      const pattern = d.pattern || 'sector';

      // Calculate sector angles
      let startRad = ((sectorStart - 90) * Math.PI) / 180;
      let endRad = ((sectorEnd - 90) * Math.PI) / 180;
      const sectorRadius = rangeNm / CELL_NM * HEX_SIZE * SQRT3 * 0.8;

      // Handle sector wrap-around (e.g., 330°-30° crosses 0°)
      let drawStart = startRad;
      let drawEnd = endRad;
      if (sectorStart > sectorEnd) {
        // Sector crosses 0° boundary — need to draw in two arcs or adjust
        drawEnd = endRad + 2 * Math.PI;
      }

      // Calculate midpoint angle (always within the sector)
      const midRad = (startRad + drawEnd) / 2;
      const midAngleDeg = ((midRad * 180 / Math.PI) + 90 + 360) % 360;

      ctx.save();

      // Dashed flight route (goes in the middle of the sector)
      ctx.strokeStyle = 'rgba(200,160,60,0.7)';
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 4]);
      const routeAngle = midRad;
      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.lineTo(fx + sectorRadius * 0.9 * Math.cos(routeAngle),
                 fy + sectorRadius * 0.9 * Math.sin(routeAngle));
      ctx.stroke();
      ctx.setLineDash([]);

      // Sector wedge (dashed border, semi-transparent fill)
      ctx.fillStyle = 'rgba(200,160,60,0.12)';
      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.arc(fx, fy, sectorRadius, drawStart, drawEnd);
      ctx.closePath();
      ctx.fill();

      ctx.strokeStyle = 'rgba(200,160,60,0.5)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 3]);
      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.arc(fx, fy, sectorRadius, drawStart, drawEnd);
      ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);

      // Aircraft icons (SVG or fallback triangles)
      const iconR = sectorRadius * 0.6;
      const iconAngle = midAngle;
      const iconX = fx + iconR * Math.cos(iconAngle);
      const iconY = fy + iconR * Math.sin(iconAngle);

      const svgIcon = getIcon('aircraft_topdown');
      if (svgIcon) {
        // Draw SVG aircraft icons
        const iconSize = 16;
        ctx.globalAlpha = 0.6;
        // Lead aircraft
        ctx.drawImage(svgIcon, iconX - iconSize/2, iconY - iconSize/2, iconSize, iconSize);
        // Wingmen
        if (count > 1) {
          ctx.drawImage(svgIcon, iconX - iconSize/2 - 10, iconY + 3, iconSize * 0.7, iconSize * 0.7);
        }
        if (count > 2) {
          ctx.drawImage(svgIcon, iconX - iconSize/2 + 10, iconY + 3, iconSize * 0.7, iconSize * 0.7);
        }
        ctx.globalAlpha = 1.0;
      } else {
        // Fallback: triangles
        ctx.fillStyle = 'rgba(200,160,60,0.6)';
        ctx.strokeStyle = 'rgba(200,160,60,0.8)';
        ctx.lineWidth = 1;
        const triSize = 5;
        ctx.beginPath();
        ctx.moveTo(iconX, iconY - triSize);
        ctx.lineTo(iconX + triSize * 0.6, iconY + triSize * 0.5);
        ctx.lineTo(iconX - triSize * 0.6, iconY + triSize * 0.5);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        if (count > 1) {
          ctx.beginPath();
          ctx.moveTo(iconX - 8, iconY + 2);
          ctx.lineTo(iconX - 5, iconY + 8);
          ctx.lineTo(iconX - 11, iconY + 8);
          ctx.closePath();
          ctx.fill();
        }
        if (count > 2) {
          ctx.beginPath();
          ctx.moveTo(iconX + 8, iconY + 2);
          ctx.lineTo(iconX + 5, iconY + 8);
          ctx.lineTo(iconX + 11, iconY + 8);
          ctx.closePath();
          ctx.fill();
        }
      }

      // Count label
      ctx.fillStyle = 'rgba(200,160,60,0.8)';
      ctx.font = '10px Caveat, cursive';
      ctx.textAlign = 'center';
      ctx.fillText(count + ' SBD', iconX, iconY + 16);

      // Pattern label
      const patternNames = { sector: '扇形', parallel: '平行', grid: '方格' };
      ctx.font = '9px Caveat, cursive';
      ctx.fillStyle = 'rgba(200,160,60,0.6)';
      ctx.fillText(patternNames[pattern] || pattern, iconX, iconY + 26);

      // PENDING stamp
      ctx.save();
      ctx.translate(fx + 20, fy - 30);
      ctx.rotate(-0.15);
      ctx.strokeStyle = 'rgba(200,160,60,0.5)';
      ctx.lineWidth = 1;
      ctx.strokeRect(-30, -8, 60, 16);
      ctx.fillStyle = 'rgba(200,160,60,0.6)';
      ctx.font = 'bold 10px Caveat, cursive';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('PENDING', 0, 0);
      ctx.restore();

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
