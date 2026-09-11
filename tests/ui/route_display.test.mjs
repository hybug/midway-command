/** 断言三层：①投影确定性 ②底图层圆心一致 ③实体标记绘制位置==逻辑坐标投影（接线正确）。*/
import assert from "node:assert/strict";
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

// 锚点 1：drawTaskForceMarker 的 CSE 标注画在航向线末端（本地系 args[1]/args[2]）。
// 独立期望：标注在标记投影点沿航向（course 240°，航海 -90° 修正）前 38px（源码常量）处。
// fix Loop2-F1: 首舰（i=0）标记对角错开 (x-14, y-28)（ENT/HOR 同位防重叠，
// mapRenderer._drawOwnFleet `i === 0 ? px-14/py-28 : px+14/py`），
// CSE 标注与引导线随之整体偏移——本套件只有 i=0 一艘，期望值含此偏移。
const F2_LEADER_DX = -14;
const F2_LEADER_DY = -28;
const cseCalls = canvas.__ctx.__calls.filter((c) => c.name === "fillText" && String(c.args[0]).startsWith("CSE "));
assert.ok(cseCalls.length >= 1, "未找到 drawTaskForceMarker 的 CSE 标注 fillText 调用");
const [, cseLx, cseLy] = cseCalls[0].args;
const rad = ((makeState(0, 0).task_forces[0].course - 90) * Math.PI) / 180;
const expectedCseX = centerX + F2_LEADER_DX + Math.cos(rad) * 38;
const expectedCseY = centerY + F2_LEADER_DY + Math.sin(rad) * 38;
const [drawnCseX, drawnCseY] = toCanvas(cseLx, cseLy);
assert.ok(Math.abs(drawnCseX - expectedCseX) < 2 && Math.abs(drawnCseY - expectedCseY) < 2,
  `CSE 标注画布位置 (${drawnCseX.toFixed(1)},${drawnCseY.toFixed(1)}) 偏离逻辑坐标投影 (${expectedCseX.toFixed(1)},${expectedCseY.toFixed(1)}) 超过 2px`);

// 锚点 2：标记本体（矢量回退圆 r=7）应画在投影点 + F1 首舰对角偏移处（舰队居中平移下 x 投影=图面中心）
const markerArc = drawn.find((c) => c.name === "arc" && Math.abs(c.args[2] - 7) < 0.5);
assert.ok(markerArc, "未找到舰队标记矢量回退圆（arc r≈7）调用");
const [drawnMx, drawnMy] = toCanvas(markerArc.args[0], markerArc.args[1]);
assert.ok(Math.abs(drawnMx - (centerX + F2_LEADER_DX)) < 2 && Math.abs(drawnMy - (centerY + F2_LEADER_DY)) < 2,
  `舰队标记画布位置 (${drawnMx.toFixed(1)},${drawnMy.toFixed(1)}) 偏离投影点 (${centerX + F2_LEADER_DX},${centerY + F2_LEADER_DY}) 超过 2px`);

// 松界（任务书原断言，经 translate 修正）：标记相关调用落在投影点 60px 邻域
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
const arcR7 = () => canvas.__ctx.__calls.filter((c) => c.name === "arc" && Math.abs(c.args[2] - 7) < 0.5);
const beforeCount = arcR7().length;
assert.ok(beforeCount >= 1, "render(sA) 未产生舰队标记（arc r≈7）");
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
// 当前实现断言：stateB 渲染帧的标记必须画在 stateB 投影 + F1 首舰对角偏移处（新逻辑位置成为绘制目标）
const bArcs = arcR7();
assert.ok(bArcs.length > beforeCount, "render(sB) 未产生新的舰队标记帧");
const [bx, by] = bArcs[bArcs.length - 1].args;
assert.ok(Math.abs(bx - (nx + F2_LEADER_DX)) < 2 && Math.abs(by - (ny + F2_LEADER_DY)) < 2,
  `sB 帧标记 (${bx.toFixed(1)},${by.toFixed(1)}) 偏离 sB 投影 (${(nx + F2_LEADER_DX).toFixed(1)},${(ny + F2_LEADER_DY).toFixed(1)})——刷新链路断裂（显示落后于逻辑）`);
// 位移必须精确等于两次逻辑位置的投影差值（重绘位置精确移动投影差）
const [qA, rA] = renderer._worldToHex(31.5, -176.0);
const [axp, ayp] = renderer._hexToPixel(qA, rA);
const aArc = arcR7()[beforeCount - 1].args;
assert.ok(Math.abs((bx - aArc[0]) - (nx - axp)) < 2 && Math.abs((by - aArc[1]) - (ny - ayp)) < 2,
  "sA→sB 标记位移 ≠ 逻辑位置投影差（重绘未精确跟随状态变化）");
// render 已把 _currentState 换成 sB（动画循环每帧 render(_currentState) 的数据源）
assert.ok(renderer._currentState === sB, "render 后 _currentState 未更新为新 state");

console.log("ROUTE-DISPLAY PASS");
