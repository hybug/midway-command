/** O.3 珊瑚海战区切换 —— GeoJSON 地理层渲染 + 双舰队上图（Node 桩环境）。
 *  断言四层：①珊瑚海包注入后 drawGeography 消费真实 geography.geojson
 *  （land 多边形填充/海岸线、label 标注上图；环礁程序化绘制不触发）
 *  ②midway 近景包（带 atoll 参数）不消费地理层、环礁照绘（回归）
 *  ③双盟军舰队（YOR/LEX）字标上图于各自真实投影位
 *  ④大取景（view_nm 800）细网格跳过（<24px 噪点守卫）。*/
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { loadGameScripts } from "./dom-stub.mjs";

const BASE = new URL("../../", import.meta.url);
const readJson = (p) => JSON.parse(readFileSync(new URL(p, BASE), "utf8"));

const coralTheater = readJson("theaters/coral-sea/theater.json");
coralTheater.geography = readJson("theaters/coral-sea/geography.geojson");

const { sandbox, document } = loadGameScripts([
  "static/js/svgLoader.js", "static/js/chartRenderer.js", "static/js/mapRenderer.js",
]);
const canvas = document.getElementById("tacticalMap");
const renderer = new sandbox.MapRenderer("tacticalMap");

// ── ① 珊瑚海包：地理层上图、环礁不上图 ──
sandbox.ChartRenderer.setTheater(coralTheater);
const geo = coralTheater.geography.features;
const landNames = geo.filter((f) => f.properties.class === "land").map((f) => f.properties.name);
assert.ok(landNames.includes("New Guinea (Papua East)"), "珊瑚海包缺新几内亚 land feature（前提取材）");

canvas.__ctx.__calls.length = 0;
sandbox.ChartRenderer.drawAll(canvas.__ctx, 1440, 900);
const calls = canvas.__ctx.__calls;
// land 填充走 GEO_STYLE.landFill（数据驱动样式：多边形 closePath → fill）
const fills = calls.filter((c) => c.name === "fill" && c.args.length === 0);
assert.ok(fills.length >= landNames.length,
  `land 多边形填充次数不足: fills=${fills.length} land=${landNames.length}`);
assert.ok(calls.some((c) => c.name === "set:fillStyle" && c.args[0] === "#e2d4b2"),
  "未找到陆地米黄填充（GEO_STYLE.landFill）");
// 标注全走数据（label feature text → fillText）
for (const text of ["CORAL SEA", "SOLOMON ISLANDS", "GUADALCANAL"]) {
  assert.ok(calls.some((c) => c.name === "fillText" && c.args[0] === text),
    `标注 ${text} 未上图`);
}
// 环礁程序化绘制不触发（无 atoll 参数 → drawAtoll 早退）
assert.ok(!calls.some((c) => c.name === "fillText" && c.args[0] === "MIDWAY ATOLL"),
  "珊瑚海包不应绘制 midway 环礁标注");
assert.ok(!calls.some((c) => c.name === "fillText" && c.args[0] === "SAND ISLAND"),
  "珊瑚海包不应绘制环礁双岛");

// 陆地质心投影确定性：新几内亚首顶点投影点在场内（取景消费 theater.view）
const ng = geo.find((f) => f.properties.class === "land" && f.properties.name === "New Guinea (Papua East)");
const [lon0, lat0] = ng.geometry.coordinates[0][0];
const pp = sandbox.ChartRenderer.latLonToChartPx(lat0, lon0, 1440, 900);
assert.ok(pp.x >= 0 && pp.x <= 1440 && pp.y >= 0 && pp.y <= 900,
  `新几内亚顶点投影出场: (${pp.x.toFixed(1)},${pp.y.toFixed(1)})`);

// ── ③ 双盟军舰队上图（YOR/LEX 字标于各自真实投影位）──
const yorLat = -15.5, yorLon = 155.6, lexLat = -15.7, lexLon = 155.4;
const coralState = {
  clock: { game_time: "1942-05-06T21:00:00Z" }, game_phase: "playing",
  theater: { id: "coral-sea", name: "珊瑚海", timezone_offset: 10 },
  task_forces: [
    { name: "Task Force 17 (TG 17.5)", course: 315, speed: 27,
      carriers: [{ name: "USS Yorktown (CV-5)", position: { lat: yorLat, lon: yorLon },
                   course: 315, speed: 27, cap_strength: 12, damage_level: 0, air_groups: [] }] },
    { name: "Task Force 11 (TG 17.8)", course: 315, speed: 27,
      carriers: [{ name: "USS Lexington (CV-2)", position: { lat: lexLat, lon: lexLon },
                   course: 315, speed: 27, cap_strength: 12, damage_level: 0, air_groups: [] }] },
  ],
  known_enemy: [], active_scouts: [], aircraft_losses: [], pending_reports: [], pending_suggestions: [],
  ap: { current: 3, max: 3, turn_type: "normal", can_act: true },
};
renderer.render(coralState);
// 细网格跳过守卫（④）：view_nm 800 → 10nm 步距 <24px，不得画细网格线束
const fineGrid = canvas.__ctx.__calls.filter((c) => c.name === "set:strokeStyle" && c.args[0] === "rgba(90,70,40,0.16)");
assert.equal(fineGrid.length, 0, "大取景下细网格应跳过（<24px 噪点守卫）");

// 双舰队标记：drawTaskForceMarker 的 CSE 航向线标注 ×2（每舰队一条）
const markerCalls = canvas.__ctx.__calls.filter((c) => c.name === "fillText" && String(c.args[0]).startsWith("CSE "));
assert.equal(markerCalls.length, 2, `双舰队标记不足: ${markerCalls.length}`);
// 字标上图：YOR/LEX 各一次（drawTaskForceMarker 圈内字标）
const badgeCalls = canvas.__ctx.__calls.filter((c) => c.name === "fillText" && ["YOR", "LEX"].includes(c.args[0]));
assert.deepEqual(badgeCalls.map((c) => c.args[0]).sort(), ["LEX", "YOR"], "舰队字标 YOR/LEX 未上图");
// 位置：YOR 标记空心圈（r=10 arc）圆心 == ChartRenderer 直接投影（唯一投影语义不回归）
const yorPx = sandbox.ChartRenderer.latLonToChartPx(yorLat, yorLon, 1440, 900);
const lexPx = sandbox.ChartRenderer.latLonToChartPx(lexLat, lexLon, 1440, 900);
const markerArcs = canvas.__ctx.__calls.filter((c) => c.name === "arc" && c.args[2] === 10);
assert.ok(markerArcs.some((c) => Math.abs(c.args[0] - yorPx.x) < 1 && Math.abs(c.args[1] - yorPx.y) < 1),
  "YOR 标记未落在真实投影位");
assert.ok(markerArcs.some((c) => Math.abs(c.args[0] - lexPx.x) < 1 && Math.abs(c.args[1] - lexPx.y) < 1),
  "LEX 标记未落在真实投影位");

// ── ② midway 近景包回归：带 atoll 参数 → 环礁照绘、地理层不消费 ──
const midwayTheater = readJson("theaters/midway/theater.json");
midwayTheater.geography = readJson("theaters/midway/geography.geojson");
sandbox.ChartRenderer.setTheater(midwayTheater);
canvas.__ctx.__calls.length = 0;
sandbox.ChartRenderer.drawAll(canvas.__ctx, 1440, 900);
const midCalls = canvas.__ctx.__calls;
assert.ok(midCalls.some((c) => c.name === "fillText" && c.args[0] === "MIDWAY ATOLL"),
  "midway 包环礁标注丢失（回归）");
assert.ok(!midCalls.some((c) => c.name === "set:fillStyle" && c.args[0] === "#e2d4b2"),
  "midway 近景包不应消费 GeoJSON 地理层（环礁程序化绘制并存冲突）");

console.log("GEO-RENDER PASS");
