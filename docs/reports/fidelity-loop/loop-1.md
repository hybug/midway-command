# Loop 1 审查记录（2026-09-12）

## 实拍
- 截图：loop-1-full-1440.png / loop-1-full-1280.png（控制者无头 Chrome）

## 差距清单（L2 对照分级）

| # | 级别 | 条目 | 对照证据 | 方案（文件+改法） | 结果 |
|---|------|------|---------|------------------|------|
| 1 | A | 20nm 标注被环礁遮成 "2nm" | loop-1-full-1440: 环礁右缘 "2nm" | chartRenderer drawRangeRings：20nm 标注 y 改环下方（c.y + 14）错开环礁 | |
| 2 | A | ENT/HOR 两舰队标记重叠（仅见 HOR） | loop-1-full-1440: 仅一个计数牌 | mapRenderer _drawOwnFleet：按舰队索引加 y 偏移（i=0 上移 16px），错开展示 | |
| 3 | A | 顶栏纸带偏亮，与海图陈旧纸对比强 | loop-1-full-1440 顶栏 | style.css #topbar.paper-topbar 叠 multiply 色调层（或 filter: sepia(0.12) brightness(0.97)) | |
| 4 | A | 沙环投影弱 | 环礁下缘投影不明显 | chartRenderer translate(2,3) 块：stroke-width 2.5→3.5、alpha 0.35→0.5 | |
| 5 | B | CSE 240 航向线与引导线在牌下交汇显乱 | 数据驱动布局，设计图无对应场景 | 记录不修 | |
| 6 | B | 1280 底栏换行挤压（旧观察） | loop-1-full-1280 | 记录不修 | |
| 7 | B | 纸张归一后再暗一档（残余） | 与设计图并排稍浅 | 记录，Loop 2 视设计评审 | |

## 设计评审（设计师 agent，L3）
- DESIGN-SCORE：还原度 7/10 · 氛围 6/10 · 层次 7/10 · 可用性 6/10 · 构图 7/10 —— 总分 33/50
- 建议（控制者裁定后并入下方 L4 清单）：
  1. [D-B→升A] 底栏甲板读数裁切（1440 裁「飞」、1280 三行裁切）——可用性缺陷，升 A 当轮修
  2. [D-S] 竖向接缝 x≈100 贯通全高——控制者初判为 .chart-light 光照层边缘（位置不随宽度变），派单含根因诊断
  3. [D-S] ADVANCE 主操作提权（复用 .btn-execute 墨色 token，对齐设计图 EXECUTE ORDER 黑块）
  4. [D-A] SAND ISLAND 白胶囊空字（文字在框外）+ EASTERN ISLAND 标注被 HOR 牌遮挡
  5. [D-A] 空闲态 SECRET 红章语义（复用 secret_stamp.svg 于侧栏空态）

## L4 修复清单（本轮实施）

| # | 来源 | 条目 | 改法 |
|---|------|------|------|
| F1 | L2-A1 | 20nm 标注被环礁遮 | drawRangeRings：20nm 标注 y 移环下方 |
| F2 | L2-A2 | 舰队标记重叠 | _drawOwnFleet 按索引 y 偏移 16px |
| F3 | L2-A3 | 顶栏偏亮 | #topbar 叠暖色调层 |
| F4 | L2-A4 | 沙环投影弱 | 投影 stroke 加深加粗 |
| F5 | D-S-2 | 竖向接缝 x≈100 | 先诊断（chart-light 边缘 vs 纸纹接缝），对应羽化/遮罩 |
| F6 | D-S-3 | ADVANCE 提权 | 墨色底反白，SITREP 维持次级 |
| F7 | D-A-4 | 岛标签入胶囊 + EASTERN ISLAND 可见性 | drawIslands 文字基线对回胶囊内；EASTERN ISLAND 标注避开 HOR 遮挡位 |
| F8 | D-A-5 | 空闲态红章 | 侧栏空态叠 secret_stamp（rotate -8°, multiply, .85） |
| F9 | D-B-1 升 A | 底栏甲板读数裁切 | renderDashboard 缩短格式 + CSS flex/nowrap |
| F10 | 批次C收口 | 审计表回填 | route-module-audit.md 缺口标记已覆盖 |

## 前轮回归检查
- Loop 前置：批次 A 五项修复复验（罗盘/岛体避让/SW斜线/25nm 错位/引导线方向）——loop-1 实拍全部保持 ✓；批次 B 三质感保持 ✓。

## 评分
- Fidelity：13.5/15（基线 loop-0 13.0；趋势 ↑——A1 地图/A2 纸张/A6 罗盘/A9 标签升为复刻）
- DESIGN-SCORE 总分：33/50（首评基线）

## 提交
- 8df02c1 fix: 海图标注与舰队标记保真修正（F1/F2/F4/F7）
- add7a64 fix: 顶栏暖色调、vignette 竖缝根因修复、ADVANCE 提权、甲板读数防裁切（F3/F5/F6/F9）
- c2b990b feat: 侧栏空态叠加 SECRET 红章（F8）
- 255c3f0 docs: 航线模块审计表回填（F10）
- （本次提交）chore: 缓存号递增 1780997994 + loop1 实施记录与前后截图归档

## L5 实施结果（2026-09-12）

| # | 状态 | 实施摘要 / 根因与证据 |
|---|------|----------------------|
| F1 | ✅ | drawRangeRings：20nm 标注改画环内下方位（`c.x+r*0.72, c.y+r*0.72+12`），25nm 右上 45°、40/60nm 水平右侧不变；实拍 loop-1-after-1440.png「20nm」完整可见，不再被环礁右缘截断 |
| F2 | ✅ | _drawOwnFleet：i=0 舰队标记整体 y−16（含 CSE 标注与引导线，经 drawTaskForceMarker 入参偏移）；实拍 ENT 牌上缘露出、两牌可辨。残留：63×64 计数牌下 16px 错位仍有大部分重叠，是否加大间距留 L6 评审。tests/ui/route_display.test.mjs 几何锚点按新行为同步（`F2_LEADER_DY = -16`） |
| F3 | ✅ | `#topbar.paper-topbar` 加 `filter: sepia(0.14) brightness(0.96)`；顶栏纸带压暗偏暖，与海图陈旧纸对比收敛 |
| F4 | ✅ | drawAtoll 投影块 stroke-width 2.5→3.5、alpha 0.35→0.5；环礁下缘立体投影增强 |
| F5 | ✅ 根因修正 | **根因不是 .chart-light**（诊断推翻初判）：`#vignette-overlay` 的 vignette.svg 为 1200×900（4:3），`background-size: 100% 100%` 下默认 `preserveAspectRatio="xMidYMid meet"` 使内容在 16:9 视口信箱化为 1200×900 居中——SVG 内容盒左右缘 x≈120/1320 形成贯通全高硬竖缝（1280 宽时 x≈40，随视口变化）。诊断：实拍亮度剖面（底栏纯色区 x=116 处 213→122 硬台阶 + 右向 ~250px 线性回升，纵贯图顶/图底/底栏）；file:// 隔离探针五组对照（/tmp/f5probe）锁定 vignette 层——移除即消失、单独即可复现，chart-light/noise/paper_tex 均排除；paper_tex.jpg 左右边缘均值 235.6/235.9、上下 233.6/233.6，可无缝平铺，无纸纹接缝。修法：`#vignette-overlay` 改等效 CSS 径向渐变（`radial-gradient(75% 75% at 50% 46%, ...)`，色标与 SVG 一致），随视口自适应无缝；修后底栏剖面最大相邻台阶 67→10 |
| F6 | ✅ | `#btn-advance` 复用墨色主操作样式（ink-main 底 + paper-base 字 + bold，hover #3a3228）；`#btn-sitrep` 维持 .btn 次级 |
| F7 | ✅ | SAND ISLAND 基线回胶囊内（`sy + ry*0.16*0.72`）垂直居中；EASTERN ISLAND 移三角形右下侧（`ex+s*0.6, ey+s*0.8`），脱离 HOR 计数牌常态遮挡位。残留：SAND ISLAND 8px 字宽（≈53px）略超胶囊宽（≈42px）右侧溢出，属字体度量既有情况，L6 评审 |
| F8 | ✅ | renderChat 空态在「等待指令（AWAITING ORDERS）」上方叠 `<img src="/static/assets/ui/secret_stamp.svg" class="idle-stamp">`；CSS 按 spec（rotate −8°/multiply/0.85/96px）；实拍侧栏 SECRET 红章 |
| F9 | ✅ | renderDashboard 甲板读数改「企 80/80·0 蜂 80/80·0」（去「备/飞」字）；`.dash-item` 加 `white-space: nowrap`、甲板项 `flex: 1.6`（`:has(#d-deck)`）；1440/1280 实拍均单行无裁切 |
| F10 | ✅ | route-module-audit.md：8 行 C1/C2 已排用例「计划用例」列回填「已覆盖（loop1 收口）」（用例经 grep tests/ 逐一核实存在）；`update_entity_position` 与 `generate_parallel_route` 两处低危未排缺口保留并标注「后续批次」 |

### L5 回归与验证
- node --check：chartRenderer.js / mapRenderer.js / uiController.js / route_display.test.mjs 通过
- pytest 全量：**272 passed 0 failed**（test_ui_assets.py 缓存 pin 同步 1780997993→1780997994；route_display 几何锚点按 F2 偏移同步）
- 实拍：loop-1-after-1440.png / loop-1-after-1280.png（基线对照 loop-1-full-1440.png / loop-1-full-1280.png）；底栏接缝量化对比见 F5 行
