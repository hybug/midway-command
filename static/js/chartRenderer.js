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
  // 成品图复现 G7：东岛黄底标注块底色（采样成品图 SAND/EASTERN ISLAND 黄底标注 ≈#dec080）
  labelYellow: '#dec080',
  gridLine: 'rgba(160,140,110,0.35)',
  gridLineFaint: 'rgba(160,140,110,0.18)', // fix Loop2-F8: 0.25° 细网（alpha 减半，绘图纸质感）
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

// 成品图复现 D1：45nm 近景取景——换算式 (nm / 45) × (min(w,h)/2 + 100)，
// 基准半径取负边距（初版 -30 边距时 40nm 不出上缘、60nm 不出画右缘，目检调参 +100）；
// 60nm 环允许出画（设计即如此，不加特判）
const CHART_VIEW_NM = 45;
function chartNmToPx(nm, w, h) {
  return (nm / CHART_VIEW_NM) * (Math.min(w, h) / 2 + 100);
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
// fix Loop2-F8: 0.25° 细网垫底（gridLineFaint alpha 减半、无标注，绘图纸质感），
// 0.5° 主网保持 gridLine 原色与度分标注
function drawLatLonGrid(ctx, w, h) {
  ctx.save();
  ctx.lineWidth = 1;
  // 细网：0.25° 步进，跳过整半度线（由主网绘制）；(v*2)%1===0 即 0.5° 的倍数
  ctx.strokeStyle = CHART_STYLE.gridLineFaint;
  ctx.setLineDash([4, 4]);
  for (let lat = 26.25; lat <= 30.01; lat += 0.25) {
    if ((lat * 2) % 1 === 0) continue;
    const y = latLonToChartPx(lat, CHART_CENTER.lon, w, h).y;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }
  for (let lon = -183; lon <= -172; lon += 0.25) {
    if (lon < -180 || (lon * 2) % 1 === 0) continue;
    const x = latLonToChartPx(CHART_CENTER.lat, lon, w, h).x;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
  }
  ctx.setLineDash([]);
  // 主网：0.5° 步进 + 度分标注（原样保留）
  ctx.strokeStyle = CHART_STYLE.gridLine;
  // 成品图复现 D1/B5（设计审计 MISSING-11）：近景后边缘度分标注淡出（初版 0.15 目检过淡，
  // 调至 0.25），验收口径「可辨但不抢主体」——边缘刻度不再与近景环礁/距离环构图冲突
  ctx.fillStyle = 'rgba(107, 93, 74, 0.25)'; // inkFade #6b5d4a 淡出
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  for (let lat = 26.0; lat <= 30.01; lat += 0.5) {
    const y = latLonToChartPx(lat, CHART_CENTER.lon, w, h).y;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    ctx.setLineDash([]);
    // fix Loop3-F5: 纬度标注（均在左缘列 x=6）上移避左下木尺（y-3 → y-8）
    ctx.fillText(fmtLat(lat), 6, y - 8);
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

// 成品图复现 G7③：东岛停机剪影——aircraft_topdown 缩小 60%（基准 26px）深灰排列跑道旁
// （filter brightness 压暗为深灰剪影，本征朝向画布上方 -Y，停放机头朝北）
function drawParkingRamp(ctx, x, y) {
  const icon = getIcon('aircraft_topdown');
  if (!icon) return;
  const silW = 26 * 0.6;
  const silH = silW * (icon.height / icon.width);
  ctx.save();
  ctx.filter = 'brightness(0.32)';
  for (let i = 0; i < 3; i++) {
    ctx.drawImage(icon, x + i * (silW + 6), y - silH / 2, silW, silH);
  }
  ctx.restore();
}

// Task 7.5：双岛——SAND ISLAND 圆角矩形 + EASTERN ISLAND 三角形与三条交叉跑道
// 成品图复现 G7：近景后东岛放大，补沙岛侧跑道横带 + 东岛黄底标注块 + 停机剪影
function drawIslands(ctx, c, rx, ry) {
  ctx.font = `8px ${CHART_STYLE.fontTypewriter}`;
  // SAND ISLAND — 环礁西侧圆角矩形（下移避让坐标行）
  const sx = c.x - rx * 0.60, sy = c.y + ry * 0.32;
  // fix Loop1-F1: SAND ISLAND 胶囊 measureText 重算宽高——近景尺度下 7px 字在
  // rx*0.34×ry*0.16 大胶囊内度量失配，目检呈空白胶囊。改 10px 字号，胶囊按文字实宽
  // +16 定宽（下限 62px）、16px 定高，文字水平/垂直居中，胶囊尺寸随文字走
  ctx.font = `10px ${CHART_STYLE.fontTypewriter}`;
  const sandLblW = ctx.measureText(CHART_LABELS.sandIsland).width;
  const sandW = Math.max(sandLblW + 16, 62);
  const sandH = 16;
  ctx.fillStyle = CHART_STYLE.paperDark;
  ctx.strokeStyle = CHART_STYLE.ink;
  roundRect(ctx, sx, sy, sandW, sandH, 3);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.fillText(CHART_LABELS.sandIsland, sx + (sandW - sandLblW) / 2, sy + sandH * 0.72);
  // 成品图复现 G7②：SAND ISLAND 侧跑道横带——浅色横带 + 墨色虚线中线（成品图沙岛下方长条跑道）
  const bandY = sy + sandH + 8, bandH = 10; // runwayBand
  ctx.fillStyle = CHART_STYLE.paper;
  ctx.strokeStyle = CHART_STYLE.ink;
  ctx.lineWidth = 1;
  roundRect(ctx, sx, bandY, sandW, bandH, 3);
  ctx.fill(); ctx.stroke();
  ctx.strokeStyle = CHART_STYLE.inkFade;
  ctx.setLineDash([4, 3]);
  ctx.beginPath();
  ctx.moveTo(sx + 4, bandY + bandH / 2);
  ctx.lineTo(sx + sandW - 4, bandY + bandH / 2);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.strokeStyle = CHART_STYLE.ink;
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
  // 成品图复现 G7③：停机剪影 3 架排列在跑道下方（三角形底缘外侧沙地）
  drawParkingRamp(ctx, ex - s * 0.55, ey + s * 0.75);
  // 成品图复现 G7①：EASTERN ISLAND 黄底标注块（黄底墨字矩形，成品图形态；
  // 原 L4-F7 右下裸字升级为标注块，位置沿用右下侧避让舰队标记）
  ctx.font = `7px ${CHART_STYLE.fontTypewriter}`;
  const lbl = CHART_LABELS.easternIsland;
  const lblW = ctx.measureText(lbl).width + 8;
  const lx = ex + s * 0.35, ly = ey + s * 0.62;
  ctx.fillStyle = CHART_STYLE.labelYellow;
  ctx.strokeStyle = CHART_STYLE.ink;
  roundRect(ctx, lx, ly, lblW, 12, 2);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.fillText(lbl, lx + 4, ly + 9);
}

// Task 7.5：中途岛环礁——礁环沙色 + 泻湖 + SW 斜线阴影 + 双岛 + 中心标注
function drawAtoll(ctx, w, h) {
  const c = atollCenter(w, h);
  // 成品图复现 D1 目检调参：23/17 → 34/25（近景后环礁跨度 ≈70% 图面，与成品图占比对齐）
  const rx = chartNmToPx(34, w, h), ry = chartNmToPx(25, w, h);
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
  // hatchNE — 东北海面斜线（成品图复现 D4：复用 SW 斜线逻辑，区域改环礁外东北矩形，步进 7→5px）
  ctx.save();
  ctx.beginPath();
  ctx.rect(c.x - rx * 0.4, c.y - ry * 1.5, rx * 1.9, ry * 1.35);
  ctx.clip();
  ctx.strokeStyle = CHART_STYLE.inkFaint;
  ctx.lineWidth = 1;
  for (let d = 0; d < rx * 2.2; d += 5) {
    ctx.beginPath();
    ctx.moveTo(c.x - rx * 0.3 + d, c.y - ry * 0.15);
    ctx.lineTo(c.x - rx * 0.3 + d + ry * 1.2, c.y - ry * 1.5);
    ctx.stroke();
  }
  ctx.restore();
  // 环礁外等深线感放射细线（成品图复现 D4）：reef 外缘起每 18px 三圈极淡椭圆，先铺后盖
  ctx.save();
  ctx.strokeStyle = 'rgba(42, 34, 24, 0.08)';
  ctx.lineWidth = 1;
  for (let k = 0; k < 3; k++) {
    ctx.beginPath();
    ctx.ellipse(c.x, c.y, rx * 1.06 + k * 18, ry * 1.06 + k * 18, 0, 0, Math.PI * 2);
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
  // fix Loop1-F4: 标注群锚点整体偏移左上 (-48,-16)——MIDWAY ATOLL/坐标行原画环礁心正中，
  // 与 ENT/HOR 圈标及 CSE 读数几何临界相叠；成品图标注群即偏左上位
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.textAlign = 'center';
  ctx.font = `bold 13px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(CHART_LABELS.atoll, c.x - 48, c.y - 24);
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(CHART_LABELS.atollCoords, c.x - 48, c.y + 4);
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
  // fix Loop1-F3: 罗盘 110→150px 放大并右移贴缘（成品图右下大罗盘位；右上罗盘中心
  // 与 40/60nm 距离环右侧标注带 y≈410 错开，互不压盖）
  const raster = getIcon('compass_engraved') || getIcon('compass_raster');
  if (raster) { ctx.drawImage(raster, w - 170, 20, 150, 150 * (raster.height / raster.width)); return; }
  const icon = getIcon('compass');
  if (icon) ctx.drawImage(icon, w - 170, 24, 150, 150);
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

// 成品图复现 G1：ENT/HOR 舰队标记——空心圆圈 + 字标 + 航向线 + 双虚线箭头矢量指向环礁
// （计数牌退役：fleet_tag_*.png 光栅素材保留作 tooltip 素材，不再上图）
function drawTaskForceMarker(ctx, tf, w, h, ox = 0, oy = 0) {
  // 空心圆圈标记（成品图形态）：r=10 空心 + 字标 + 航向线 + 双虚线箭头矢量指向环礁
  const ac = { x: atollCenter(w, h).x - ox, y: atollCenter(w, h).y - oy };
  ctx.save();
  ctx.strokeStyle = CHART_STYLE.ink; ctx.lineWidth = 2.5;
  ctx.beginPath(); ctx.arc(tf.x, tf.y, 10, 0, Math.PI * 2); ctx.stroke();       // circle-outline
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.font = `bold 11px ${CHART_STYLE.fontTypewriter}`;
  // fix Loop1-F4: 字标统一圈右下 (tf.x+14, tf.y+20)——原圈左上字标压 MIDWAY ATOLL 标注群；
  // 与环礁中心坐标行（ac.y + 4 基线，drawAtoll 同源）保持 ≥20px 矩形避让，不足再下移一行高
  const lblX = tf.x + 14;
  let lblY = tf.y + 20;
  if (Math.abs(lblY - (ac.y + 4)) < 20) lblY += 14;
  ctx.fillText(tf.callsign, lblX, lblY);
  const rad = ((tf.courseDeg - 90) * Math.PI) / 180;
  ctx.beginPath(); ctx.moveTo(tf.x, tf.y);
  ctx.lineTo(tf.x + Math.cos(rad) * 30, tf.y + Math.sin(rad) * 30); ctx.stroke(); // 航向线
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(`CSE ${Math.round(tf.courseDeg)}°`, tf.x + Math.cos(rad) * 34, tf.y + Math.sin(rad) * 34);
  // 双虚线矢量：两条平行虚线从圈缘指向环礁，末端双箭头
  const dx = ac.x - tf.x, dy = ac.y - tf.y, len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len, px = -uy, py = ux;
  ctx.setLineDash([5, 4]); ctx.strokeStyle = CHART_STYLE.inkFade; ctx.lineWidth = 1.2;
  for (const side of [-4, 4]) {
    ctx.beginPath();
    ctx.moveTo(tf.x + ux * 14 + px * side, tf.y + uy * 14 + py * side);
    ctx.lineTo(tf.x + ux * 70 + px * side, tf.y + uy * 70 + py * side);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  const tx = tf.x + ux * 74, ty = tf.y + uy * 74;
  ctx.beginPath();
  ctx.moveTo(tx + ux * 6, ty + uy * 6);
  ctx.lineTo(tx - ux * 4 + px * 5, ty - uy * 4 + py * 5);
  ctx.lineTo(tx - ux * 4 - px * 5, ty - uy * 4 - py * 5);
  ctx.closePath(); ctx.fill();
  ctx.restore();
}

// Task 7.9：敌情接触标记——红圈 ENEMY 标记，大小随置信度（high 46 / medium 34 / low 26）
// 成品图复现 G3 勘误（设计师审计）：成品图敌标实为「红虚线圈 + 中央 ? + 下方 ENEMY 红字」，
// 原裁定红方块 enemy_tag_q 系判读错误——改用 enemy_marker.svg（本就是该形态，质量门 PASS）；
// enemy_tag_q.png 保留为战报方框变体（svgLoader 资产在册），不再上图。
function drawEnemyContact(ctx, contact) {
  const size = { high: 46, medium: 34, low: 26 }[contact.confidence] || 26;
  const icon = getIcon('enemy_marker');
  if (!icon) return;
  const ih = size * (icon.height / icon.width); // viewBox 120x150（1:1.25），按素材纵横比绘制防拉伸
  ctx.drawImage(icon, contact.x - size / 2, contact.y - ih / 2, size, ih);
}

// 成品图复现 G4：SECRET 章——地图左上角横版大章（设计审计 MISSING-6：成品图该位置是
// SECRET 章，原「海图（CHART）」字幕已随之从 index.html 移除，保留会穿帮）。
// 章目标矩形 24,20,180,76；-10° 倾斜用 ctx 变换绕章心旋转（先 translate 到章心再 rotate）。
function drawSecretStamp(ctx, w, h) {
  const stamp = getIcon('secret_stamp');
  if (!stamp) return;
  ctx.save();
  ctx.translate(24 + 180 / 2, 20 + 76 / 2);
  ctx.rotate(-10 * Math.PI / 180);
  ctx.drawImage(stamp, -90, -38, 180, 76);
  ctx.restore();
}

const ChartRenderer = {
  drawAll(ctx, w, h) {
    drawChartBase(ctx, w, h);
    drawLatLonGrid(ctx, w, h);
    drawAtoll(ctx, w, h);
    drawRangeRings(ctx, w, h);
    drawCompassRose(ctx, w, h);
    drawScaleBar(ctx, w, h);
    drawSecretStamp(ctx, w, h);
  },
  drawTaskForceMarker,
  drawEnemyContact,
  chartNmToPx,
  latLonToChartPx,
};
window.ChartRenderer = ChartRenderer;
