/**
 * chartRenderer.js — 设计图 A1「地图主图」程序化绘制（docs/plans/ui-replication-plan.md）
 * 旧海图纸底图 + 中途岛环礁 + 距离环 + 经纬网 + 罗盘 + 比例尺。
 * 色值必须与 style.css 的 :root token 保持一致（tests/test_ui_assets.py 守卫）。
 * M.3 数据驱动化：取景/经纬网/距离环/环礁公式/标注全部消费 THEATER 战区对象
 * （GET /theater 下发；BUILTIN_THEATER 同值兜底），详见 BUILTIN_THEATER 注释块。
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

// ── M.3 ChartEngine 数据驱动化：战区包（theater pack）消费 ──
// THEATER 为 GET /theater 下发的战区对象（theaters/midway/theater.json 原样结构），
// init 时经 TheaterLoader 异步填充；null 时以 BUILTIN_THEATER（与战区包同值的 JS
// 字面量）渲染——同步可用性兜底：加载失败/离线/vm 桩（无 loader）均不白屏，
// 「内置默认 = 战区包同值」由 tests/test_ui_assets.py 锚点断言守卫。
// 图面中心/取景 nm/距离环表/环礁公式参数等硬编码常量就此退役，全部读 THEATER。
const BUILTIN_THEATER = {
  id: 'midway',
  name: '中途岛',
  view: {
    center: { lat: 28.2, lon: -177.4 },      // 环礁中心（=range_rings.origin 真坐标）
    view_nm: 45,                              // D1 近景取景（45nm）
    rotation: 0,
    atoll_screen_frac: { x: 0.44, y: 0.46 },  // R-M2：环礁构图位（成品图量取 0.44w/0.46h）
  },
  graticule: {
    minor_step: 0.25,                         // 细网（gridLineFaint，无标注）
    major_step: 0.5,                          // 主网 + 度分标注（R-M1：对齐渲染现状）
    label_format: 'dms',
    extent: { lat_min: 26.0, lat_max: 30.0, lon_min: -183.0, lon_max: -172.0 }, // 网格覆盖域
  },
  range_rings: { origin: { lat: 28.2, lon: -177.4 }, rings_nm: [20, 25, 40, 60], labels: true },
  atoll: {                                    // 环礁程序化绘制参数（nm 尺度，投影消费）
    radius_nm: { x: 34, y: 25 },              // D1 近景环礁半轴（跨度 ≈70% 图面）
    rim: { x: 0.94, y: 0.90 },                // 内缘墨线比例
    lagoon: { x: 0.80, y: 0.74 },             // 泻湖比例
  },
  labels: {
    atoll: 'MIDWAY ATOLL',
    atoll_coords: "28°12'N 177°21'W",
    sand_island: 'SAND ISLAND',
    eastern_island: 'EASTERN ISLAND',
  },
};
let THEATER = null;
function T() { return THEATER || BUILTIN_THEATER; }

// 成品图复现 D1：近景取景换算式 (nm / view_nm) × (min(w,h)/2 + 100)——基准半径负边距
// （初版 -30 边距时 40nm 不出上缘、60nm 不出画右缘，目检调参 +100）；60nm 环允许出画。
// view_nm 由 THEATER.view 直供（M.3 数据驱动；内置默认/战区包同值 45）。
const BASE_RADIUS_MARGIN = 100;
function chartNmToPx(nm, w, h) {
  return (nm / T().view.view_nm) * (Math.min(w, h) / 2 + BASE_RADIUS_MARGIN);
}

// 环礁图面中心——环礁、双岛与距离环共享的绘制基准（fix: 距离环与环礁共心）。
// R-M2：range_rings.origin 真坐标经 makeProjector（atoll_screen_frac）落构图位，
// 与改造前 atollCenter（0.44w/0.46h）逐像素一致。
function atollCenter(w, h) {
  const th = T();
  return makeProjector(th.view, w, h)(th.range_rings.origin.lat, th.range_rings.origin.lon);
}

// fix Loop3-F1（CHART_SYSTEM.md §四 C3 投影唯一化）→ M.3 数据驱动化：唯一坐标系出入口——
// makeProjector(view, w, h) -> project(lat, lon) -> {x, y}（含 project.invert(x, y) → {lat, lon}），
// 等距圆柱 + cos(lat) 纬度修正。view.atoll_screen_frac 指定 view.center 的图面锚位
// （R-M2：环礁构图位 0.44/0.46；缺省 0.5/0.5 = 画布中心——实体层 mapRenderer 传
// {center} 即走画布中心锚，取值与 view.center 同源）。view_nm 缺省回落 THEATER。
function makeProjector(view, w, h) {
  const c = view.center;
  const frac = view.atoll_screen_frac || { x: 0.5, y: 0.5 };
  const viewNm = view.view_nm || T().view.view_nm;
  const pxPerDegLat = (60 / viewNm) * (Math.min(w, h) / 2 + BASE_RADIUS_MARGIN); // 1° 纬度 ≈ 60nm
  const pxPerDegLon = pxPerDegLat * Math.cos(c.lat * Math.PI / 180);
  const project = (lat, lon) => ({
    x: w * frac.x + (lon - c.lon) * pxPerDegLon,
    y: h * frac.y - (lat - c.lat) * pxPerDegLat,
  });
  project.invert = (x, y) => ({
    lon: c.lon + (x - w * frac.x) / pxPerDegLon,
    lat: c.lat - (y - h * frac.y) / pxPerDegLat,
  });
  return project;
}

// 底图经纬投影（THEATER.view 全量消费，含构图 frac）——环礁真坐标落构图位
function latLonToChartPx(lat, lon, w, h) {
  return makeProjector(T().view, w, h)(lat, lon);
}

// M.3：战区包异步拉取（失败静默保持内置默认；vm 桩未载 theaterLoader.js 时跳过）
if (typeof window !== 'undefined' && window.TheaterLoader && window.TheaterLoader.load) {
  window.TheaterLoader.load().then((t) => { if (t && t.view) THEATER = t; }).catch(() => {});
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

// Task 7.4：虚线经纬网 + 纬度（左）/经度（顶）度分标注（步进/覆盖域由 THEATER.graticule 驱动，M.3）
// fix Loop2-F8: 细网垫底（gridLineFaint alpha 减半、无标注，绘图纸质感），
// 主网保持 gridLine 原色与度分标注
function drawLatLonGrid(ctx, w, h) {
  const th = T();
  const g = th.graticule, ext = g.extent;
  const lat0 = th.view.center.lat, lon0 = th.view.center.lon;
  // 网格参考系：view.center → 画布中心（缺省 0.5/0.5 锚）——改造前网格即锚画布中心，
  // 与环礁构图位（atoll_screen_frac 0.44/0.46）相差 (0.06w, 0.04h)；视觉零变化裁定
  // 保留两锚现状，M.4 底图 GeoJSON 化时统一
  const gridProj = makeProjector({ center: th.view.center, view_nm: th.view.view_nm }, w, h);
  ctx.save();
  ctx.lineWidth = 1;
  // 细网：minor_step 步进，跳过整半度线（由主网绘制）；(v*2)%1===0 即 0.5° 的倍数
  ctx.strokeStyle = CHART_STYLE.gridLineFaint;
  ctx.setLineDash([4, 4]);
  for (let lat = ext.lat_min + g.minor_step; lat <= ext.lat_max + 1e-9; lat += g.minor_step) {
    if ((lat * 2) % 1 === 0) continue;
    const y = gridProj(lat, lon0).y;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }
  for (let lon = ext.lon_min; lon <= ext.lon_max + 1e-9; lon += g.minor_step) {
    if (lon < -180 || (lon * 2) % 1 === 0) continue;
    const x = gridProj(lat0, lon).x;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
  }
  ctx.setLineDash([]);
  // 主网：major_step 步进 + 度分标注（原样保留）
  ctx.strokeStyle = CHART_STYLE.gridLine;
  // 成品图复现 D1/B5（设计审计 MISSING-11）：近景后边缘度分标注淡出（初版 0.15 目检过淡，
  // 调至 0.25），验收口径「可辨但不抢主体」——边缘刻度不再与近景环礁/距离环构图冲突
  ctx.fillStyle = 'rgba(107, 93, 74, 0.25)'; // inkFade #6b5d4a 淡出
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  for (let lat = ext.lat_min; lat <= ext.lat_max + 1e-9; lat += g.major_step) {
    const y = gridProj(lat, lon0).y;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    ctx.setLineDash([]);
    // fix Loop3-F5: 纬度标注（均在左缘列 x=6）上移避左下木尺（y-3 → y-8）
    ctx.fillText(fmtLat(lat), 6, y - 8);
  }
    // fix Loop2-F6: 罗盘避让——右上罗盘 150px 占位（drawCompassRose 自 w-170 起），
    // 落在罗盘半径带内（x > w-170）的顶部经度标注跳过（网格线照画，只让标注带避让）
    for (let lon = ext.lon_min; lon <= ext.lon_max + 1e-9; lon += g.major_step) {
      if (lon < -180) continue;
      const x = gridProj(lat0, lon).x;
      ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      ctx.setLineDash([]);
      if (x > w - 170) continue; // 罗盘占位带（x > w-170）内不画标注
      ctx.fillText(fmtLon(lon), x + 3, 26); // y=26 经度标注下移（罗盘/章避让，fix round 3）
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
  const L = T().labels;
  ctx.font = `8px ${CHART_STYLE.fontTypewriter}`;
  // SAND ISLAND — 环礁西侧圆角矩形（下移避让坐标行）
  const sx = c.x - rx * 0.60, sy = c.y + ry * 0.32;
  // fix Loop1-F1: SAND ISLAND 胶囊 measureText 重算宽高——近景尺度下 7px 字在
  // rx*0.34×ry*0.16 大胶囊内度量失配，目检呈空白胶囊。改 10px 字号，胶囊按文字实宽
  // +16 定宽（下限 62px）、16px 定高，文字水平/垂直居中，胶囊尺寸随文字走
  ctx.font = `10px ${CHART_STYLE.fontTypewriter}`;
  const sandLblW = ctx.measureText(L.sand_island).width;
  const sandW = Math.max(sandLblW + 16, 62);
  const sandH = 16;
  ctx.fillStyle = CHART_STYLE.paperDark;
  ctx.strokeStyle = CHART_STYLE.ink;
  roundRect(ctx, sx, sy, sandW, sandH, 3);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.fillText(L.sand_island, sx + (sandW - sandLblW) / 2, sy + sandH * 0.72);
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
  const lbl = T().labels.eastern_island;
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
// （M.3：半轴/内外缘比例/标注由 THEATER.atoll 与 THEATER.labels 驱动）
function drawAtoll(ctx, w, h) {
  const a = T().atoll;
  const c = atollCenter(w, h); // range_rings.origin 真坐标 → atoll_screen_frac 构图位（R-M2）
  // 成品图复现 D1 目检调参：23/17 → 34/25（近景后环礁跨度 ≈70% 图面，与成品图占比对齐）
  const rx = chartNmToPx(a.radius_nm.x, w, h), ry = chartNmToPx(a.radius_nm.y, w, h);
  const outer = atollOutline(c.x, c.y, rx, ry);
  const rim = atollOutline(c.x, c.y, rx * a.rim.x, ry * a.rim.y);
  const lagoon = atollOutline(c.x, c.y, rx * a.lagoon.x, ry * a.lagoon.y);
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
  ctx.fillText(T().labels.atoll, c.x - 48, c.y - 24);
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(T().labels.atoll_coords, c.x - 48, c.y + 4);
  ctx.textAlign = 'left';
}

// Task 7.6：距离环——虚线圆 + 沿水平半径右侧标注 + 中心 0nm 刻度短线
// 以环礁为圆心（atollCenter 与 drawAtoll 共心，设计图亦如此）；
// 半径由 THEATER.range_rings.rings_nm 驱动（M.3），标签派生 `${nm}nm`
function drawRangeRings(ctx, w, h) {
  const c = atollCenter(w, h);
  ctx.save();
  ctx.strokeStyle = CHART_STYLE.inkFade;
  ctx.fillStyle = CHART_STYLE.inkFade;
  ctx.font = `9px ${CHART_STYLE.fontTypewriter}`;
  ctx.lineWidth = 1;
  ctx.setLineDash([6, 5]);
  for (const nm of T().range_rings.rings_nm) {
    const label = `${nm}nm`;
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
// fix Loop3-F1 投影唯一化：实体层无舰队居中 translate，标记与环礁同屏幕系——
// 签名回归 (ctx, tf, w, h)，引导线直接指向屏幕系环礁心（ox/oy 本地系换算删除）
function drawTaskForceMarker(ctx, tf, w, h) {
  // 空心圆圈标记（成品图形态）：r=10 空心 + 字标 + 航向线 + 双虚线箭头矢量指向环礁
  const ac = atollCenter(w, h);
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
  // fix Loop2-F2: CSE 读数外推复核——锚点圈 CSE 落入环礁中心坐标行文字带
  //（基线 ac.y+4 ±14px、中心 ±140px 内）时沿屏幕 +y 外推一行高，消叠字
  //（fixture 实证：HOR 锚点圈 CSE 270° 压坐标行 "…21'W" 尾）；带外维持原位（航线同排）
  let cseX = tf.x + Math.cos(rad) * 34, cseY = tf.y + Math.sin(rad) * 34;
  if (Math.abs(cseY - (ac.y + 4)) < 14 && Math.abs(cseX - ac.x) < 140) cseY = ac.y + 18;
  ctx.fillText(`CSE ${Math.round(tf.courseDeg)}°`, cseX, cseY);
  // 双虚线矢量：两条平行虚线从圈缘指向环礁，末端双箭头
  const dx = ac.x - tf.x, dy = ac.y - tf.y, len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len, px = -uy, py = ux;
  // fix Loop1-F4: 矢量虚线/箭头钳制在环礁心之前——近景下圈标距心可不足 80px，
  // 固定 70/74px 长度会过冲环礁心、箭头压中心标注群与坐标行（fixture 实证）
  const dashEnd = Math.min(70, len - 18);
  const arrowBase = Math.min(74, len - 12);
  if (dashEnd > 14) {
    ctx.setLineDash([5, 4]); ctx.strokeStyle = CHART_STYLE.inkFade; ctx.lineWidth = 1.2;
    for (const side of [-4, 4]) {
      ctx.beginPath();
      ctx.moveTo(tf.x + ux * 14 + px * side, tf.y + uy * 14 + py * side);
      ctx.lineTo(tf.x + ux * dashEnd + px * side, tf.y + uy * dashEnd + py * side);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }
  const tx = tf.x + ux * arrowBase, ty = tf.y + uy * arrowBase;
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
  // M.3：战区对象注入口——fixture（离线，无 /theater）经 setTheater 注入与
  // theaters/midway/theater.json 同值的 DESIGN_THEATER，走同一数据通道；
  // getTheater() 供测试/调试读当前生效战区（THEATER 或内置默认）。
  setTheater(t) { if (t && t.view) THEATER = t; },
  getTheater() { return T(); },
  // fix Loop1-F5: 底图层拆分 drawBase（纸底+经纬网）/drawLandmarks（环礁+距离环+罗盘+
  // 比例尺+章）——搜索扇区须画在纸面之后、陆地填充之前（先扇区后陆地，扇区压焦点消除）；
  // drawAll 保持原序（base+landmarks），像素比对与既有测试不受影响。
  // M.3：THEATER 恒有兜底（T() → 内置默认），drawAll 不再白屏直返。
  drawBase(ctx, w, h) {
    drawChartBase(ctx, w, h);
    drawLatLonGrid(ctx, w, h);
  },
  drawLandmarks(ctx, w, h) {
    drawAtoll(ctx, w, h);
    drawRangeRings(ctx, w, h);
    drawCompassRose(ctx, w, h);
    drawScaleBar(ctx, w, h);
    drawSecretStamp(ctx, w, h);
  },
  drawAll(ctx, w, h) {
    this.drawBase(ctx, w, h);
    this.drawLandmarks(ctx, w, h);
  },
  drawTaskForceMarker,
  drawEnemyContact,
  chartNmToPx,
  latLonToChartPx,
  makeProjector,
};
window.ChartRenderer = ChartRenderer;
