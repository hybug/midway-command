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
const RING_NM = [["20nm", 20], ["40nm", 40], ["60nm", 60]];

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

function latLonToChartPx(lat, lon, w, h) {
  const pxPerDegLat = chartNmToPx(60, w, h); // 1° 纬度 ≈ 60nm
  const pxPerDegLon = pxPerDegLat * Math.cos(28.2 * Math.PI / 180);
  return {
    x: w / 2 + (lon - CHART_CENTER.lon) * pxPerDegLon,
    y: h / 2 - (lat - CHART_CENTER.lat) * pxPerDegLat,
  };
}

// Task 7.3：纸张底图——米黄底色 + 水渍纹理 + 噪点颗粒（资产由 svgLoader 提供）
function drawChartBase(ctx, w, h) {
  ctx.fillStyle = CHART_STYLE.paper;
  ctx.fillRect(0, 0, w, h);
  const stains = getIcon('paper_base');
  const grain = getIcon('noise');
  if (stains) ctx.drawImage(stains, 0, 0, w, h);
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
    ctx.fillText(fmtLon(lon), x + 3, 14);
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
  // SAND ISLAND — 环礁西侧圆角矩形
  const sx = c.x - rx * 0.52, sy = c.y + ry * 0.10;
  ctx.fillStyle = CHART_STYLE.paperDark;
  ctx.strokeStyle = CHART_STYLE.ink;
  roundRect(ctx, sx, sy, rx * 0.34, ry * 0.16, 3);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.fillText(CHART_LABELS.sandIsland, sx + 4, sy + ry * 0.10);
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
  ctx.fillText(CHART_LABELS.easternIsland, ex - s, ey + s * 0.9);
}

// Task 7.5：中途岛环礁——礁环沙色 + 泻湖 + SW 斜线阴影 + 双岛 + 中心标注
function drawAtoll(ctx, w, h) {
  const c = { x: w * 0.44, y: h * 0.46 };
  const rx = chartNmToPx(23, w, h), ry = chartNmToPx(17, w, h);
  const outer = atollOutline(c.x, c.y, rx, ry);
  const rim = atollOutline(c.x, c.y, rx * 0.94, ry * 0.90);
  const lagoon = atollOutline(c.x, c.y, rx * 0.80, ry * 0.74);
  // 礁环沙色
  tracePath(ctx, outer);
  ctx.fillStyle = CHART_STYLE.sand; ctx.fill();
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
  // 西南侧礁外斜线阴影（clip 到放大轮廓内）
  ctx.save();
  tracePath(ctx, atollOutline(c.x, c.y, rx * 1.12, ry * 1.10));
  ctx.clip();
  ctx.strokeStyle = CHART_STYLE.inkFaint;
  for (let d = -40; d < rx; d += 7) {
    ctx.beginPath();
    ctx.moveTo(c.x - rx + d, c.y + ry * 0.75);
    ctx.lineTo(c.x - rx + d + 60, c.y + ry * 1.45);
    ctx.stroke();
  }
  ctx.restore();
  drawIslands(ctx, c, rx, ry);
  // 中心标注
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.textAlign = 'center';
  ctx.font = `bold 13px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(CHART_LABELS.atoll, c.x, c.y - 2);
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(CHART_LABELS.atollCoords, c.x, c.y + 12);
  ctx.textAlign = 'left';
}

// Task 7.6：20/40/60nm 距离环——虚线圆 + 沿水平半径右侧标注 + 中心 0nm 刻度短线
function drawRangeRings(ctx, w, h) {
  const c = latLonToChartPx(CHART_CENTER.lat, CHART_CENTER.lon, w, h);
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
    ctx.fillText(label, c.x + r + 4, c.y - 4);
    ctx.setLineDash([6, 5]);
  }
  // 中心 0nm 刻度短线（设计图中心右侧）
  ctx.setLineDash([]);
  ctx.beginPath(); ctx.moveTo(c.x + 14, c.y - 6); ctx.lineTo(c.x + 26, c.y - 6); ctx.stroke();
  ctx.restore();
}

const ChartRenderer = {
  drawAll(ctx, w, h) {
    drawChartBase(ctx, w, h);
    drawLatLonGrid(ctx, w, h);
    drawAtoll(ctx, w, h);
    drawRangeRings(ctx, w, h);
  },
  chartNmToPx,
  latLonToChartPx,
};
window.ChartRenderer = ChartRenderer;
