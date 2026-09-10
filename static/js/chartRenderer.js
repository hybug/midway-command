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

const ChartRenderer = {
  drawAll(ctx, w, h) {
    drawChartBase(ctx, w, h);
    drawLatLonGrid(ctx, w, h);
  },
  chartNmToPx,
  latLonToChartPx,
};
window.ChartRenderer = ChartRenderer;
