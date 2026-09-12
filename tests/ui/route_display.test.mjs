/** 断言三层：①投影确定性 ②底图层圆心一致 ③实体标记绘制位置==逻辑坐标投影（接线正确）。*/
import assert from "node:assert/strict";
import * as vm from "node:vm";
import { loadGameScripts } from "./dom-stub.mjs";

const { sandbox, document } = loadGameScripts([
  "static/js/svgLoader.js", "static/js/chartRenderer.js", "static/js/mapRenderer.js",
]);
const canvas = document.getElementById("tacticalMap");
const renderer = new sandbox.MapRenderer("tacticalMap");

// ── ① 投影确定性（chartRenderer 层）──
// 注：vm 桩上下文返回的对象原型属另一 realm，deepStrictEqual 校验原型，
// 先摊开成本 realm 普通对象再比较（断言语义不变）
const p1 = sandbox.ChartRenderer.latLonToChartPx(31.5, -176.0, 1440, 900);
const p2 = sandbox.ChartRenderer.latLonToChartPx(31.5, -176.0, 1440, 900);
assert.deepEqual({ ...p1 }, { ...p2 }, "同输入投影必须确定");
const pFar = sandbox.ChartRenderer.latLonToChartPx(28.2, -177.4, 1440, 900);
assert.deepEqual({ x: pFar.x, y: pFar.y }, { x: 720, y: 450 }, "图面中心 lat/lon 必须映射到画布中心");

// ── ② 底图层：环礁中心与距离环圆心一致（真实渲染调用）──
sandbox.ChartRenderer.drawAll(canvas.__ctx, 1440, 900);
const arcs = canvas.__ctx.__calls.filter((c) => c.name === "arc");
const atollCx = 1440 * 0.44, atollCy = 900 * 0.46;
const ringArc = arcs.find((c) => Math.abs(c.args[2] - sandbox.ChartRenderer.chartNmToPx(60, 1440, 900)) < 1);
assert.ok(ringArc, "未找到 60nm 距离环 arc 调用");
assert.ok(Math.abs(ringArc.args[0] - atollCx) < 1 && Math.abs(ringArc.args[1] - atollCy) < 1,
  `距离环圆心 (${ringArc.args[0]},${ringArc.args[1]}) 偏离环礁中心 (${atollCx},${atollCy})`);

// ── ③ 实体层：舰队标记画在其逻辑坐标的投影处（接线测试）──
// 最小 state：字段以 mapRenderer.render 实际读取为准，缺啥补啥（systematic-debugging 迭代桩 state）
function makeState(lat, lon) {
  return {
    clock: { game_time: "1942-06-04T04:00:00Z" }, game_phase: "playing",
    task_forces: [{ name: "Task Force 16", course: 240, speed: 25,
      carriers: [{ name: "USS Enterprise (CV-6)", position: { lat, lon }, aircraft: [] }] }],
    known_enemy: [], active_scouts: [], pending_reports: [], pending_suggestions: [],
  };
}
renderer.render(makeState(31.5, -176.0));
const drawn = canvas.__ctx.__calls.filter((c) => c.name === "arc" || c.name === "drawImage");

// ── ③ 独立公式对照（控制裁定加强）──
// 公式副本，源码变更时须同步——逐字抄录自 static/js/mapRenderer.js 的 _worldToHex/_hexToPixel
// （常量 HEX_SIZE/SQRT3/CELL_NM/REF_LAT/REF_LON 同源；运行时对照断言防抄录漂移，见下）
const HEX_SIZE = 12, SQRT3 = Math.sqrt(3), CELL_NM = 10, REF_LAT = 28.2, REF_LON = -177.4;
function worldToHexCopy(lat, lon) {
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
function hexToPixelCopy(q, r) {
  return [HEX_SIZE * (SQRT3 * q + SQRT3 / 2 * r), HEX_SIZE * (3 / 2 * r)];
}

// 渲染器投影 vs 公式副本：不一致说明源码公式已变更，须同步抄录
const [q, r] = renderer._worldToHex(31.5, -176.0);
const [ex, ey] = renderer._hexToPixel(q, r);
assert.deepEqual([q, r], worldToHexCopy(31.5, -176.0), "_worldToHex 与公式副本不一致（源码已变更，须同步抄录）");
assert.deepEqual([ex, ey], hexToPixelCopy(q, r), "_hexToPixel 与公式副本不一致（源码已变更，须同步抄录）");

// 舰队居中平移：render 内部局部变量不可读，按公式独立计算（控制裁定）
const centerX = canvas.width / 2, centerY = canvas.height / 2;
const ox = centerX - ex, oy = centerY - ey;
// 录制器记录的是 translate(ox,oy) 本地系坐标；画布位置 = 本地坐标 + (ox,oy)
const toCanvas = (lx, ly) => [lx + ox, ly + oy];

// 锚点 1：drawTaskForceMarker 的 CSE 标注画在航向线末端延长处（成品图复现 G1 圆圈形态：
// 标注 = 标记 + 34px × 航向单位向量（course−90° 修正），34px 与航向线长 30px 同批源码常量）。
// F2 错位机制（成品图复现 G1 保留）：首舰（i=0）对角偏移 (x-14, y-28)
// （mapRenderer._drawOwnFleet `i === 0 ? px-14/py-28 : px+14/py`），
// CSE 标注与双虚线矢量随之整体偏移——本套件只有 i=0 一艘，期望值含此偏移。
const F2_LEADER_DX = -14;
const F2_LEADER_DY = -28;
const cseCalls = canvas.__ctx.__calls.filter((c) => c.name === "fillText" && String(c.args[0]).startsWith("CSE "));
assert.ok(cseCalls.length >= 1, "未找到 drawTaskForceMarker 的 CSE 标注 fillText 调用");
const [, cseLx, cseLy] = cseCalls[0].args;
const hdgRad = ((240 - 90) * Math.PI) / 180; // course=240（makeState 同源，-90° 屏幕系修正）
const expectedCseX = centerX + F2_LEADER_DX + Math.cos(hdgRad) * 34;
const expectedCseY = centerY + F2_LEADER_DY + Math.sin(hdgRad) * 34;
const [drawnCseX, drawnCseY] = toCanvas(cseLx, cseLy);
assert.ok(Math.abs(drawnCseX - expectedCseX) < 2 && Math.abs(drawnCseY - expectedCseY) < 2,
  `CSE 标注画布位置 (${drawnCseX.toFixed(1)},${drawnCseY.toFixed(1)}) 偏离逻辑坐标投影 (${expectedCseX.toFixed(1)},${expectedCseY.toFixed(1)}) 超过 2px`);

// 锚点 2：标记本体（空心圆圈 r=10，成品图复现 G1）应画在投影点 + F2 首舰对角偏移处（舰队居中平移下 x 投影=图面中心）
const markerArc = drawn.find((c) => c.name === "arc" && Math.abs(c.args[2] - 10) < 0.5);
assert.ok(markerArc, "未找到舰队标记空心圆圈（arc r≈10）调用");
const [drawnMx, drawnMy] = toCanvas(markerArc.args[0], markerArc.args[1]);
assert.ok(Math.abs(drawnMx - (centerX + F2_LEADER_DX)) < 2 && Math.abs(drawnMy - (centerY + F2_LEADER_DY)) < 2,
  `舰队标记画布位置 (${drawnMx.toFixed(1)},${drawnMy.toFixed(1)}) 偏离投影点 (${centerX + F2_LEADER_DX},${centerY + F2_LEADER_DY}) 超过 2px`);

// 松界（任务书原断言，经 translate 修正）：标记相关调用落在投影点邻域
// 成品图复现 G1：ENT 让位 hack 已删，F2 对角错位 (x-14,y-28) 距投影 31px，邻域 60px 覆盖
const hit = drawn.some((c) => Math.hypot((c.args[0] ?? 999) + ox - centerX, (c.args[1] ?? 999) + oy - centerY) < 60);
assert.ok(hit, "舰队标记未绘制在其逻辑投影（图面中心附近）处");

// 回归（fix: 缺省列表防御）：render 是公开入口，缺省 active_scouts/known_enemy 的
// 最小 state 不得让渲染帧抛错（桩环境复现根因：_drawSearchSectors 的
// state.active_scouts.filter 首先抛 TypeError）
assert.doesNotThrow(() => renderer.render({
  task_forces: [{ name: "Task Force 16", course: 240, speed: 25,
    carriers: [{ name: "USS Enterprise (CV-6)", position: { lat: 31.5, lon: -176.0 }, aircraft: [] }] }],
}), "render 遇缺省 active_scouts/known_enemy 字段不得抛错");

// ── ④ 刷新链路（批次 C4）：advance 语义模拟——逻辑位置变化后 render 必须以新位置为绘制目标 ──
// 键名/路径以源码 grep 校正：_animState.fleetPositions 仅声明、从未写入——_drawOwnFleet
// 无 lerp 缓存，每帧直接把标记画在当前 state 的投影上（_lerpPos 为死代码，无人调用）。
// 故「动画目标」= 本次 render 的投影点本身；断言意图：新逻辑位置成为绘制目标。
// （若日后给舰队引入 lerp 位置缓存，本组断言会因标记滞后于投影差而红——正是要守的链路。）
const sA = makeState(31.5, -176.0);
renderer.render(sA);
const arcR10 = () => canvas.__ctx.__calls.filter((c) => c.name === "arc" && Math.abs(c.args[2] - 10) < 0.5);
const beforeCount = arcR10().length;
assert.ok(beforeCount >= 1, "render(sA) 未产生舰队标记（arc r≈10）");
const sB = makeState(31.4, -176.1); // 模拟一 tick（advance 15min）后的逻辑位置
renderer.render(sB);
// 新逻辑位置 → hex → 像素（本地系；render 每次 resize 重置 centerX/centerY=720/450）
const [q2, r2] = renderer._worldToHex(31.4, -176.1);
const [nx, ny] = renderer._hexToPixel(q2, r2);
const fp = renderer._animState.fleetPositions; // 源码现状：空对象（仅声明）；有 lerp 缓存时此处应有 {targetX,targetY}
const entry = Object.values(fp).find((v) => v && "targetX" in v);
if (entry) {
  // 引入了 lerp 缓存的未来实现：目标必须跟随新逻辑位置（舰队居中平移下 target==投影点）
  assert.ok(Math.abs(entry.targetX - (renderer.centerX - nx)) < 2
          && Math.abs(entry.targetY - (renderer.centerY - ny)) < 2,
    "舰队动画目标未跟随新逻辑位置（刷新链路断裂）");
}
// 当前实现断言：stateB 渲染帧的标记必须画在 stateB 投影 + F2 首舰对角偏移处（新逻辑位置成为绘制目标）
const bArcs = arcR10();
assert.ok(bArcs.length > beforeCount, "render(sB) 未产生新的舰队标记帧");
const [bx, by] = bArcs[bArcs.length - 1].args;
assert.ok(Math.abs(bx - (nx + F2_LEADER_DX)) < 2 && Math.abs(by - (ny + F2_LEADER_DY)) < 2,
  `sB 帧标记 (${bx.toFixed(1)},${by.toFixed(1)}) 偏离 sB 投影 (${(nx + F2_LEADER_DX).toFixed(1)},${(ny + F2_LEADER_DY).toFixed(1)})——刷新链路断裂（显示落后于逻辑）`);
// 位移必须精确等于两次逻辑位置的投影差值（重绘位置精确移动投影差）
const [qA, rA] = renderer._worldToHex(31.5, -176.0);
const [axp, ayp] = renderer._hexToPixel(qA, rA);
const aArc = arcR10()[beforeCount - 1].args;
assert.ok(Math.abs((bx - aArc[0]) - (nx - axp)) < 2 && Math.abs((by - aArc[1]) - (ny - ayp)) < 2,
  "sA→sB 标记位移 ≠ 逻辑位置投影差（重绘未精确跟随状态变化）");
// render 已把 _currentState 换成 sB（动画循环每帧 render(_currentState) 的数据源）
assert.ok(renderer._currentState === sB, "render 后 _currentState 未更新为新 state");

// ── ⑤ 成品图复现 G2：在途侦察机剪影（aircraft_topdown）沿航线叠画 ──
// 空态无机载（H 批 fixture 未就绪，验收裁定）：桩 state 注入 1 架 active_scout，
// 断言剪影 drawImage 被调用、锚点==position 投影、尺寸 w≈26px、rotate==航向角。
// 剪影注入 vm 上下文：svgLoader 的 loadedIcons 为顶层 const（全局词法环境），
// 同 context 的后续 runInContext 可读写（桩环境无 Image/fetch，加载器本身不会填充）。
const seedIcon = vm.runInContext(
  'loadedIcons["aircraft_topdown"] = { width: 158, height: 115, __stub: true };'
  + 'getIcon("aircraft_topdown")', sandbox);
assert.ok(seedIcon && seedIcon.__stub, "vm 桩：aircraft_topdown 图标注入失败");

const SCOUT_LAT = 30.5, SCOUT_LON = -178.2;
const scoutState = makeState(31.5, -176.0);
scoutState.active_scouts = [{
  id: "SCOUT-1", status: "in_flight", phase: "outbound", direction: "west",
  position: { lat: SCOUT_LAT, lon: SCOUT_LON },
  search_bearing_min: 250, search_bearing_max: 290, search_distance_nm: 120,
  fuel_pct: 80, aircraft_lost: 0,
}];
renderer.render(scoutState);
// fix（随 G7）：drawParkingRamp（东岛停机剪影）也以 aircraft_topdown drawImage 上图，
// 剪影计数按本节锚定尺寸 w≈26px 过滤（停机剪影 w=15.6px、待定建议机群 w=16px，不混淆）
const SIL_W = 26, SIL_H = 26 * (115 / 158); // 源码 w=26，等比高（viewBox 158x115）
const silCalls = canvas.__ctx.__calls.filter(
  (c) => c.name === "drawImage" && c.args[0] === seedIcon
      && Math.abs(c.args[3] - SIL_W) < 0.01);
assert.ok(silCalls.length === 1, `侦察机剪影 drawImage 应恰好被调用 1 次，实得 ${silCalls.length}`);

// 位置：_drawScoutAircraft 先 translate(px,py) 再以局部原点为中心画剪影——录制器记的是
// 原始参数，故剪影锚点 = 紧邻其前的 translate 调用（fleet 本地系下的 position 投影）
const [sq, sr] = renderer._worldToHex(SCOUT_LAT, SCOUT_LON);
const [sx, sy] = renderer._hexToPixel(sq, sr);
const [, silDx, silDy, silDw, silDh] = silCalls[0].args;
assert.ok(Math.abs(silDw - SIL_W) < 0.01 && Math.abs(silDh - SIL_H) < 0.01,
  `剪影应按 w≈26px 等比绘制，实得 ${silDw}x${silDh}`);
const callsAll = canvas.__ctx.__calls;
let trIdx = callsAll.indexOf(silCalls[0]);
while (trIdx-- > 0 && callsAll[trIdx].name !== "translate") { /* 回溯最近 translate */ }
const [trX, trY] = callsAll[trIdx].args;
assert.ok(Math.abs(trX - sx) < 0.01 && Math.abs(trY - sy) < 0.01,
  `剪影 translate 锚点 (${trX.toFixed(1)},${trY.toFixed(1)}) 偏离插值位置投影 (${sx.toFixed(1)},${sy.toFixed(1)})`);

// 航向：bearing 250–290 中点 270° → (270−90)°=π 屏幕角；剪影本征朝上（−Y）须再 +π/2 → 3π/2
const silRotate = canvas.__ctx.__calls.find(
  (c) => c.name === "rotate" && Math.abs(c.args[0] - (3 * Math.PI) / 2) < 1e-6);
assert.ok(silRotate, "剪影未按航向 rotate（期望 3π/2 = π 航向角 + π/2 朝向补偿）");

// ── ⑥ 成品图复现 G3：敌情标记勘误——enemy_marker.svg（红虚线圈+?+ENEMY）上图 ──
// 原裁定红方块 enemy_tag_q 系判读错误（设计师审计），改回 enemy_marker；空态无敌标，
// 以桩 state 注入 1 个 known_enemy 断言 drawImage(enemy_marker) 被调用且锚点==投影。
const seedMarker = vm.runInContext(
  'loadedIcons["enemy_marker"] = { width: 120, height: 150, __stub: true };'
  + 'getIcon("enemy_marker")', sandbox);
assert.ok(seedMarker && seedMarker.__stub, "vm 桩：enemy_marker 图标注入失败");

const ENEMY_LAT = 30.0, ENEMY_LON = -178.0;
const enemyState = makeState(31.5, -176.0);
enemyState.known_enemy = [{ position: { lat: ENEMY_LAT, lon: ENEMY_LON }, confidence: "high" }];
renderer.render(enemyState);
const markerCalls = canvas.__ctx.__calls.filter((c) => c.name === "drawImage" && c.args[0] === seedMarker);
assert.ok(markerCalls.length === 1, `enemy_marker drawImage 应恰好被调用 1 次，实得 ${markerCalls.length}`);

// 位置/尺寸：锚点==known_enemy 投影（_drawEnemyContacts 无 translate，直接画投影点）；
// 尺寸沿用 confidence 档位映射（high 46）+ 1:1.25 等比（viewBox 120x150）
const [eq, er] = renderer._worldToHex(ENEMY_LAT, ENEMY_LON);
const [ex0, ey0] = renderer._hexToPixel(eq, er);
const MK_W = 46, MK_H = 46 * (150 / 120);
const [, mkDx, mkDy, mkDw, mkDh] = markerCalls[0].args;
assert.ok(Math.abs(mkDx - (ex0 - MK_W / 2)) < 0.01 && Math.abs(mkDy - (ey0 - MK_H / 2)) < 0.01,
  `敌标锚点 (${mkDx.toFixed(1)},${mkDy.toFixed(1)}) 偏离投影 (${ex0.toFixed(1)},${ey0.toFixed(1)})`);
assert.ok(Math.abs(mkDw - MK_W) < 0.01 && Math.abs(mkDh - MK_H) < 0.01,
  `敌标应按 confidence=high 档 46px 等比绘制，实得 ${mkDw}x${mkDh}`);

// ── ⑦ 成品图复现 G4：SECRET 章叠在 drawAll 末尾（比例尺后），-10° 倾斜 24,20,180,76 ──
const seedStamp = vm.runInContext(
  'loadedIcons["secret_stamp"] = { width: 260, height: 110, __stub: true };'
  + 'getIcon("secret_stamp")', sandbox);
assert.ok(seedStamp && seedStamp.__stub, "vm 桩：secret_stamp 图标注入失败");

const callsBefore = canvas.__ctx.__calls.length;
sandbox.ChartRenderer.drawAll(canvas.__ctx, 1440, 900);
const drawAllCalls = canvas.__ctx.__calls.slice(callsBefore);
const stampImg = drawAllCalls.find((c) => c.name === "drawImage" && c.args[0] === seedStamp);
assert.ok(stampImg, "drawAll 未叠画 SECRET 章");
// 章心平移 (24+90, 20+38) → rotate(-10°) → drawImage(-90,-38,180,76)（目标矩形 24,20,180,76）
const stampIdx = drawAllCalls.indexOf(stampImg);
const stampTranslate = drawAllCalls.slice(0, stampIdx).reverse().find((c) => c.name === "translate");
assert.deepEqual(stampTranslate.args.map((v) => Math.round(v)), [114, 58],
  "SECRET 章未绕章心 (114,58) 旋转平移");
const stampRotate = drawAllCalls.slice(0, stampIdx).reverse().find((c) => c.name === "rotate");
assert.ok(stampRotate && Math.abs(stampRotate.args[0] - (-10 * Math.PI / 180)) < 1e-9,
  "SECRET 章缺 -10° rotate");
assert.deepEqual(stampImg.args.slice(1), [-90, -38, 180, 76], "SECRET 章 drawImage 矩形不符");
// 顺序：章在比例尺标注（末位 fillText 'nm'）之后（drawAll 末尾=比例尺后）
const nmIdx = drawAllCalls.map((c) => c.name === "fillText" && c.args[0] === "nm").lastIndexOf(true);
assert.ok(stampIdx > nmIdx, "SECRET 章未画在比例尺之后（drawAll 末尾裁定）");

// ── ⑧ 回归（fix: _drawPendingRecon 缺失 midAngle 定义）──
// 真实 state 出现 launch_scout 待定建议时，_drawPendingRecon 引用未定义的 midAngle
// （本函数内扇区中点变量实为 midRad）→ ReferenceError 使整帧渲染崩溃。
// 桩 state 注入 1 条 launch_scout，断言 render 不抛错且飞机剪影按扇区中点角绘制。
const pendingState = makeState(31.5, -176.0);
pendingState.pending_suggestions = [{
  action_type: "launch_scout",
  details: { direction: "northwest", aircraft_count: 4, sector_start: 280, sector_end: 340,
             range_nm: 200, pattern: "sector" },
}];
assert.doesNotThrow(() => renderer.render(pendingState),
  "render 遇 launch_scout 待定建议不得抛错（midAngle ReferenceError 回归）");
// 修复路径实际出图：领队机 16px ×1 + 翼机 16*0.7=11.2px ×2（源码 _drawPendingRecon 绘制参数）；
// 东岛停机剪影（G7）w=15.6px 不与 16px 混淆
const pendingLead = canvas.__ctx.__calls.filter(
  (c) => c.name === "drawImage" && c.args[0] === seedIcon && c.args[3] === 16);
const pendingWing = canvas.__ctx.__calls.filter(
  (c) => c.name === "drawImage" && c.args[0] === seedIcon && Math.abs(c.args[3] - 11.2) < 0.01);
assert.ok(pendingLead.length === 1 && pendingWing.length === 2,
  `待定侦察建议应绘制 1 领队机(16px)+2 翼机(11.2px)，实得 ${pendingLead.length}+${pendingWing.length}`);

console.log("ROUTE-DISPLAY PASS");
