/**
 * chartRenderer.js — 设计图 A1「地图主图」程序化绘制（docs/plans/ui-replication-plan.md）
 * 旧海图纸底图 + 中途岛环礁 + 距离环 + 经纬网 + 罗盘 + 比例尺。
 * 色值必须与 style.css 的 :root token 保持一致（tests/test_ui_assets.py 守卫）。
 */

const CHART_STYLE = {
  paper: '#f5edd6', paperDark: '#e8dcc8', paperEdge: '#d4c8a8',
  ink: '#2a2218', inkFade: '#6b5d4a', inkFaint: '#a89878',
  lagoon: '#b8d4c8', reef: '#8aaa98', sand: '#d4c4a0', eastern: '#c8b890',
  enemyRed: '#8b2500',
  gridLine: 'rgba(160,140,110,0.35)',
  fontTypewriter: "'Special Elite', monospace",
};

// 图面中心 = 环礁中心（与 mapRenderer.js 的 REF_LAT/REF_LON 一致）
const CHART_CENTER = { lat: 28.2, lon: -177.4 };
// 距离环用 [标签, 数值] 对——标签字面量受 tests/test_ui_assets.py 守卫（控制裁定 R1）
const RING_NM = [["20nm", 20], ["25nm", 25], ["40nm", 40], ["60nm", 60]];

// 图面标注字面量（同受测试守卫；Task 7.5/7.6 绘制环礁与距离环标注时取用）
const CHART_LABELS = {
  atoll: "MIDWAY ATOLL",
  atollCoords: "28°12'N 177°21'W",
  sandIsland: "SAND ISLAND",
  easternIsland: "EASTERN ISLAND",
};

// 65nm 半径必须完整落在图面内（留 40px 边距）
function chartNmToPx(nm, w, h) {
  return (nm / 65) * (Math.min(w, h) / 2 - 40);
}

// 环礁图面中心——环礁、双岛与距离环共享的绘制基准（fix: 距离环与环礁共心）
function atollCenter(w, h) {
  return { x: w * 0.44, y: h * 0.46 };
}

function latLonToChartPx(lat, lon, w, h) {
  const pxPerDegLat = chartNmToPx(60, w, h); // 1° 纬度 ≈ 60nm
  const pxPerDegLon = pxPerDegLat * Math.cos(28.2 * Math.PI / 180);
  return {
    x: w / 2 + (lon - CHART_CENTER.lon) * pxPerDegLon,
    y: h / 2 - (lat - CHART_CENTER.lat) * pxPerDegLat,
  };
}

// Task 7.3 → 保真度修正 B1：纸张底图——米黄底色 + AI 纸纹 createPattern 平铺（SVG 水渍回退）+ 噪点颗粒
function drawChartBase(ctx, w, h) {
  ctx.fillStyle = CHART_STYLE.paper;
  ctx.fillRect(0, 0, w, h);
  const tex = getIcon('paper_tex');
  if (tex) {
    const pattern = ctx.createPattern(tex, 'repeat');
    if (pattern) { ctx.fillStyle = pattern; ctx.fillRect(0, 0, w, h); }
  } else {
    const stains = getIcon('paper_base');
    if (stains) ctx.drawImage(stains, 0, 0, w, h);
  }
  const grain = getIcon('noise');
  if (grain) { ctx.globalAlpha = 0.3; ctx.drawImage(grain, 0, 0, w, h); ctx.globalAlpha = 1; }
}

// Task 7.4：度分格式化（北纬 / 西经，如 28°30'N、177°30'W）
function fmtLat(lat) {
  const d = Math.floor(lat), m = Math.round((lat - d) * 60);
  return `${d}°${m}'N`;
}
function fmtLon(lon) {
  const a = Math.abs(lon), d = Math.floor(a), m = Math.round((a - d) * 60);
  return `${d}°${m}'W`;
}

// Task 7.4：0.5° 虚线经纬网 + 纬度（左）/经度（顶）度分标注
function drawLatLonGrid(ctx, w, h) {
  ctx.save();
  ctx.strokeStyle = CHART_STYLE.gridLine;
  ctx.fillStyle = CHART_STYLE.inkFade;
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  ctx.lineWidth = 1;
  for (let lat = 26.0; lat <= 30.01; lat += 0.5) {
    const y = latLonToChartPx(lat, CHART_CENTER.lon, w, h).y;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillText(fmtLat(lat), 6, y - 3);
  }
  for (let lon = -183; lon <= -172; lon += 0.5) {
    if (lon < -180) continue;
    const x = latLonToChartPx(CHART_CENTER.lat, lon, w, h).x;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillText(fmtLon(lon), x + 3, 26); // y=26 下移避让左上角 .chart-label div（fix round 3）
  }
  ctx.restore();
}

// Task 7.5：环礁外缘轮廓——确定性三谐波波浪 + 西南侧礁盘缺口
function atollOutline(cx, cy, rx, ry) {
  const pts = [];
  for (let i = 0; i < 120; i++) {
    const t = (i / 120) * Math.PI * 2;
    const wob = 1 + 0.07 * Math.sin(3 * t + 0.8) + 0.045 * Math.sin(7 * t + 2.1) + 0.03 * Math.sin(11 * t + 4.5);
    const gap = (t > 2.4 && t < 3.4) ? 0.92 : 1.0; // 西南侧礁盘缺口
    pts.push({ x: cx + rx * wob * gap * Math.cos(t), y: cy + ry * wob * gap * Math.sin(t) });
  }
  return pts;
}

function tracePath(ctx, pts) {
  ctx.beginPath();
  pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.closePath();
}

function roundRect(ctx, x, y, w2, h2, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w2, y, x + w2, y + h2, r);
  ctx.arcTo(x + w2, y + h2, x, y + h2, r);
  ctx.arcTo(x, y + h2, x, y, r);
  ctx.arcTo(x, y, x + w2, y, r);
  ctx.closePath();
}

// Task 7.5：双岛——SAND ISLAND 圆角矩形 + EASTERN ISLAND 三角形与三条交叉跑道
function drawIslands(ctx, c, rx, ry) {
  ctx.font = `8px ${CHART_STYLE.fontTypewriter}`;
  // SAND ISLAND — 环礁西侧圆角矩形（下移避让坐标行）
  const sx = c.x - rx * 0.60, sy = c.y + ry * 0.32;
  ctx.fillStyle = CHART_STYLE.paperDark;
  ctx.strokeStyle = CHART_STYLE.ink;
  roundRect(ctx, sx, sy, rx * 0.34, ry * 0.16, 3);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = CHART_STYLE.ink;
  // fix L4-F7: 标签基线对回胶囊内（垂直居中于圆角矩形；原画在框外下方成空框）
  ctx.fillText(CHART_LABELS.sandIsland, sx + 4, sy + ry * 0.16 * 0.72);
  // EASTERN ISLAND — 东南侧三角形 + 三条交叉跑道
  const ex = c.x + rx * 0.28, ey = c.y + ry * 0.52, s = rx * 0.26;
  ctx.beginPath();
  ctx.moveTo(ex, ey - s * 0.55);
  ctx.lineTo(ex + s, ey + s * 0.35);
  ctx.lineTo(ex - s * 0.8, ey + s * 0.45);
  ctx.closePath();
  ctx.fillStyle = CHART_STYLE.eastern;
  ctx.fill(); ctx.stroke();
  const rwy = [[-s * 0.7, s * 0.3, s * 0.9, -s * 0.35],
               [-s * 0.55, -s * 0.4, s * 0.7, s * 0.5],
               [-s * 0.1, -s * 0.55, s * 0.15, s * 0.6]];
  ctx.lineWidth = 2.5;
  rwy.forEach(([x1, y1, x2, y2]) => {
    ctx.beginPath(); ctx.moveTo(ex + x1, ey + y1); ctx.lineTo(ex + x2, ey + y2); ctx.stroke();
  });
  ctx.lineWidth = 1;
  // fix L4-F7: 标注移到三角形右下侧（原坐标被 HOR 计数牌常态遮挡）
  ctx.fillText(CHART_LABELS.easternIsland, ex + s * 0.6, ey + s * 0.8);
}

// Task 7.5：中途岛环礁——礁环沙色 + 泻湖 + SW 斜线阴影 + 双岛 + 中心标注
function drawAtoll(ctx, w, h) {
  const c = atollCenter(w, h);
  const rx = chartNmToPx(23, w, h), ry = chartNmToPx(17, w, h);
  const outer = atollOutline(c.x, c.y, rx, ry);
  const rim = atollOutline(c.x, c.y, rx * 0.94, ry * 0.90);
  const lagoon = atollOutline(c.x, c.y, rx * 0.80, ry * 0.74);
  // 西南海面斜线（先铺后盖：铺在沙色填充之前的海面层）
  ctx.save();
  ctx.beginPath();
  ctx.rect(c.x - rx * 1.5, c.y + ry * 0.15, rx * 1.9, ry * 1.35);
  ctx.clip();
  ctx.strokeStyle = CHART_STYLE.inkFaint;
  ctx.lineWidth = 1;
  for (let d = 0; d < rx * 2.2; d += 7) {
    ctx.beginPath();
    ctx.moveTo(c.x - rx * 1.4 + d, c.y + ry * 1.5);
    ctx.lineTo(c.x - rx * 1.4 + d + ry * 1.2, c.y + ry * 0.15);
    ctx.stroke();
  }
  ctx.restore();
  // 礁环沙色
  tracePath(ctx, outer);
  ctx.fillStyle = CHART_STYLE.sand; ctx.fill();
  // 沙色填充后、泻湖填充前：外轮廓偏移描暗圈（立体投影）
  ctx.save();
  ctx.translate(2, 3);
  tracePath(ctx, outer);
  ctx.strokeStyle = 'rgba(42, 34, 24, 0.5)'; // fix L4-F4: 投影加深（0.35→0.5）
  ctx.lineWidth = 3.5; // fix L4-F4: 投影加粗（2.5→3.5）
  ctx.stroke();
  ctx.restore();
  // 泻湖
  tracePath(ctx, lagoon);
  ctx.fillStyle = CHART_STYLE.lagoon; ctx.fill();
  // 外缘珊瑚礁虚线
  tracePath(ctx, outer);
  ctx.strokeStyle = CHART_STYLE.reef; ctx.lineWidth = 1.5; ctx.setLineDash([5, 3]); ctx.stroke();
  ctx.setLineDash([]);
  // 环礁内缘墨线
  tracePath(ctx, rim);
  ctx.strokeStyle = CHART_STYLE.inkFade; ctx.lineWidth = 1; ctx.stroke();
  drawIslands(ctx, c, rx, ry);
  // 中心标注
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.textAlign = 'center';
  ctx.font = `bold 13px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(CHART_LABELS.atoll, c.x, c.y - 8);
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(CHART_LABELS.atollCoords, c.x, c.y + 20);
  ctx.textAlign = 'left';
}

// Task 7.6：20/25/40/60nm 距离环——虚线圆 + 沿水平半径右侧标注 + 中心 0nm 刻度短线
// 以环礁为圆心（atollCenter 与 drawAtoll 共心，设计图亦如此）
function drawRangeRings(ctx, w, h) {
  const c = atollCenter(w, h);
  ctx.save();
  ctx.strokeStyle = CHART_STYLE.inkFade;
  ctx.fillStyle = CHART_STYLE.inkFade;
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  ctx.lineWidth = 1;
  ctx.setLineDash([6, 5]);
  for (const [label, nm] of RING_NM) {
    const r = chartNmToPx(nm, w, h);
    ctx.beginPath(); ctx.arc(c.x, c.y, r, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
    // fix: 20/25nm 环间距仅 ~27px，25nm 标注移右上 45°（与设计图一致）防重叠
    // fix L4-F1: 20nm 标注改画环内下方位（原水平右侧被环礁右缘遮成 "2nm"）；40/60nm 维持右侧
    if (label === '25nm') ctx.fillText(label, c.x + r * 0.71, c.y - r * 0.71);
    else if (label === '20nm') ctx.fillText(label, c.x + r * 0.72, c.y + r * 0.72 + 12);
    else ctx.fillText(label, c.x + r + 4, c.y - 4);
    ctx.setLineDash([6, 5]);
  }
  // 中心 0nm 刻度短线（设计图中心右侧）
  ctx.setLineDash([]);
  ctx.beginPath(); ctx.moveTo(c.x + 14, c.y - 6); ctx.lineTo(c.x + 26, c.y - 6); ctx.stroke();
  ctx.restore();
}

// Task 7.7：罗盘——右上角光栅罗盘（compass.svg 资产由 svgLoader 提供）
function drawCompassRose(ctx, w, h) {
  // 保真度修正 B3：AI 雕刻罗盘（亮度反转抠图）优先，compass_raster 回退
  const raster = getIcon('compass_engraved') || getIcon('compass_raster');
  if (raster) { ctx.drawImage(raster, w - 150, 20, 110, 110 * (raster.height / raster.width)); return; }
  const icon = getIcon('compass');
  if (icon) ctx.drawImage(icon, w - 150, 24, 110, 110);
}

// Task 7.7：分段比例尺 0-10-25-50nm——右下角黑白相间分段条
function drawScaleBar(ctx, w, h) {
  const x0 = w - 250, y0 = h - 46;
  const pxPerNm = 200 / 50; // 50nm 宽 200px
  const segs = [[0, 10], [10, 25], [25, 50]];
  ctx.save();
  ctx.strokeStyle = CHART_STYLE.ink;
  ctx.lineWidth = 1;
  ctx.font = `8px ${CHART_STYLE.fontTypewriter}`;
  segs.forEach(([a, b], i) => {
    ctx.fillStyle = i % 2 === 0 ? CHART_STYLE.ink : CHART_STYLE.paper;
    ctx.fillRect(x0 + a * pxPerNm, y0, (b - a) * pxPerNm, 6);
    ctx.strokeRect(x0 + a * pxPerNm, y0, (b - a) * pxPerNm, 6);
    ctx.fillStyle = CHART_STYLE.ink;
    ctx.fillText(String(a), x0 + a * pxPerNm - 3, y0 + 16);
  });
  ctx.fillText('50', x0 + 50 * pxPerNm - 6, y0 + 16);
  ctx.fillText('nm', x0 + 50 * pxPerNm + 8, y0 + 16);
  ctx.restore();
}

// Task 7.9：ENT/HOR 舰队标记——光栅计数牌优先（Phase 6 治理产物），缺失时矢量回退；
// CSE 航向线与虚线引导线两模式共用（设计图：CSE 270° + 指向环礁的双虚线）
function drawTaskForceMarker(ctx, tf, w, h, ox = 0, oy = 0) {
  const tag = getIcon(tf.callsign === 'ENT' ? 'fleet_tag_ent'
                    : tf.callsign === 'HOR' ? 'fleet_tag_hor' : 'fleet_counter');
  ctx.save();
  if (tag) {
    // 光栅计数牌（绿幕抠图素材，Phase 6 治理产物）
    ctx.drawImage(tag, tf.x - tag.width / 2, tf.y - tag.height / 2);
  } else {
    // 矢量回退：圆圈标记（设计图 A1 基础样式）
    ctx.strokeStyle = CHART_STYLE.ink;
    ctx.fillStyle = CHART_STYLE.paper;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(tf.x, tf.y, 7, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  }
  // 航向矢量 + CSE 标注（两模式共用，设计图：CSE 270°）
  // 航海约定 0°=北朝上：屏幕坐标 y 向下，需 -90° 修正（与 mapRenderer 旧 _drawSingleCourseArrow 一致）
  const rad = ((tf.courseDeg - 90) * Math.PI) / 180;
  ctx.strokeStyle = CHART_STYLE.ink;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(tf.x, tf.y);
  ctx.lineTo(tf.x + Math.cos(rad) * 34, tf.y + Math.sin(rad) * 34);
  ctx.stroke();
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(`CSE ${Math.round(tf.courseDeg)}°`, tf.x + Math.cos(rad) * 38, tf.y + Math.sin(rad) * 38);
  // 指向环礁的虚线引导线 + 箭头（保真度修正 T3：方向由 atollCenter 计算，替代写死偏移）
  // fix: atollCenter 返回屏幕系坐标，而本函数在 mapRenderer 的 ctx.translate(ox,oy)
  // 舰队本地系内绘制——先减去平移量换算到本地系，否则方向反向（S 级缺陷修复）
  const ac = { x: atollCenter(w, h).x - ox, y: atollCenter(w, h).y - oy };
  const dx = ac.x - tf.x, dy = ac.y - tf.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len;
  ctx.setLineDash([3, 4]);
  ctx.strokeStyle = CHART_STYLE.inkFade;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(tf.x + ux * 12, tf.y + uy * 12);
  ctx.lineTo(tf.x + ux * 64, tf.y + uy * 64);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(tf.x + ux * 68, tf.y + uy * 68);
  ctx.lineTo(tf.x + ux * 58 - uy * 4, tf.y + uy * 58 + ux * 4);
  ctx.lineTo(tf.x + ux * 58 + uy * 4, tf.y + uy * 58 - ux * 4);
  ctx.closePath();
  ctx.fillStyle = CHART_STYLE.inkFade;
  ctx.fill();
  ctx.restore();
}

// Task 7.9：敌情接触标记——红圈 ENEMY 标记，大小随置信度（high 46 / medium 34 / low 26）
function drawEnemyContact(ctx, contact) {
  const size = { high: 46, medium: 34, low: 26 }[contact.confidence] || 26;
  // 优先 Phase 6 光栅 enemy_tag_q（近方形，按素材纵横比绘制防拉伸）
  const raster = getIcon('enemy_tag_q');
  if (raster) {
    const rh = size * (raster.height / raster.width);
    ctx.drawImage(raster, contact.x - size / 2, contact.y - rh / 2, size, rh);
    return;
  }
  // 回退：enemy_marker.svg（120x150，任务书原尺寸 1:1.25）
  const icon = getIcon('enemy_marker');
  if (icon) ctx.drawImage(icon, contact.x - size / 2, contact.y - size / 2, size, size * 1.25);
}

const ChartRenderer = {
  drawAll(ctx, w, h) {
    drawChartBase(ctx, w, h);
    drawLatLonGrid(ctx, w, h);
    drawAtoll(ctx, w, h);
    drawRangeRings(ctx, w, h);
    drawCompassRose(ctx, w, h);
    drawScaleBar(ctx, w, h);
  },
  drawTaskForceMarker,
  drawEnemyContact,
  chartNmToPx,
  latLonToChartPx,
};
window.ChartRenderer = ChartRenderer;
