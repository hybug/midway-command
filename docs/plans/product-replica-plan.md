# 成品图 100% 复现计划：基准升级至产品 mockup（product-replica-plan）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（每任务派发实现子代理+任务评审）。完成声明前遵循 superpowers:verification-before-completion；缺陷先 superpowers:systematic-debugging。计划格式沿用 `docs/plans/ui-fidelity-fix-plan.md` v3 的工程纪律（六步循环/台账/修复环/工时核算）。

**Goal:** 视觉基准从 15 项物料板**升级为成品完整界面设计图** `docs/assets/Gemini_Generated_Image_u1fak0u1fak0u1fa.png`（2752×1536，下称「成品图」），按像素级比对结果实施结构性改造并 **100% 复现**——含近景构图、深色 chrome、地图要素（圆圈标记/飞机剪影/敌标/SECRET 章）与黄铜圆规道具。设计师 agent 每轮评审 + Loop ≥5 轮 + 终验，总工时核算 **≥14h**。

**Architecture:** 三大结构性改造——①取景重构（65nm 区域远景 → 45nm 环礁近景，chartRenderer 比例参数级改动）；②Chrome 深色化（底栏/右栏换深棕黑主题，新增 chrome token 组）；③基准态 fixture（`static/dev/design-fixture.html` 渲染设计同款中局状态，使敌标/飞机/损伤等「设计中局要素」可进入像素比对）。地图要素复用已入库素材（aircraft_topdown.png、enemy_tag_q、button_26 圆规分拆）。

**Tech Stack:** 同既有（原生 HTML/CSS/JS + Canvas + SVG + Pillow + pytest + 无头 Chrome）。

**Spec:** 成品图 `Gemini_Generated_Image_u1fak0u1fak0u1fa.png`（唯一视觉基准）；15 项物料板**降级为切图规范参考**（spritesheet 面板仍是 fleet/aircraft/罗盘资产的出处规范）；概念图 `4d8kly` 为布局标注参考。

## 像素级比对结论（2026-09-12 实测，已存证 docs/reports/product-compare/）

统一 1440×900（设计非等比压缩，仅区域粗测）：

- 整体均值色：设计 (169,153,122) vs 当前 (208,199,177)——**设计暗 39/46/55**，整体更黄更旧。
- 4×4 区域均色差最大热区：**右列 98.7**（右栏：设计深色 vs 当前浅纸）、**底行 74.9/70.8/78.7**（底栏：设计深棕 `#42372C` 系 vs 当前浅纸 `#B8AC9A` 系）。
- 关键采样：图面空白设计 (231,206,159) vs 当前 (227,220,200)——**设计纸更黄（B 通道差 41）且暗角更重**；顶栏接近（182 vs 186）✓。
- 构图：设计为**环礁近景**（约 45nm 视野：20nm 环贯穿环礁内部、40nm 出上缘、60nm 贴右缘），环礁占图表面积 ~70%；当前 65nm 远景环礁仅 ~25%。

**差距分级（S=结构必改 / A=可见 / B=记录）**：
- S1 取景（远景→近景）；S2 底栏深色化；S3 右栏深色化+INTEL 深卡；S4 整体色调加深压黄
- A1 ENT/HOR 空心圆圈标记+双虚线箭头矢量（替换计数牌）；A2 飞机剪影上航线；A3 敌标双红圈；A4 SECRET 章上地图左上（横版大章）；A5 黄铜圆规道具左下；A6 尺移右侧竖放+铅笔右下；A7 NE 角 hatch 块+环礁放射细线；A8 损伤红字样式（12% (Minor)）；A9 标签深色白字（INTEL 白底激活）
- B1 齿轮图标（顶栏右）；B2 底栏敌情「4 CV / 2 BB (REPORTED)」两行式；B3 EA STERN ISLAND 黄底标注块（现已有文字）

## Global Constraints（沿用 v3 工程）

- 零新增依赖；色值新 token 先登记（新增 chrome token 组见 E 批）；缓存号递增纪律（现值 1780997997）；每任务六步+评审；不 push；目检无头 Chrome（`--timeout=12000`，**禁用 `--virtual-time-budget`**——rAF 循环会挂）。
- **基准态 fixture 纪律**：凡「设计中局要素」（敌标/飞机/损伤值）的比对一律在 fixture 渲染下进行，空态截图不得作为这些要素的验收证据。
- 计数牌退役后文件保留（`fleet_tag_*.png` 留作战情 tooltip 素材），地图不再引用。

## 工作量核算表（≥10h 双保险）

| 阶段 | 内容 | 工时 |
|------|------|------|
| P0 | 基准登记+比对报告落盘+fixture 设计 | 0.8h |
| 批次 D 构图取景（D1 近景/D2 色调/D3 画框/D4 hatch） | 4 任务 | 2.0h |
| 批次 E Chrome 深色化（E1 底栏/E2 右栏+INTEL/E3 标签/E4 损伤红字/E5 齿轮） | 5 任务 | 2.2h |
| 批次 G 地图要素（G1 圆圈矢量/G2 飞机/G3 敌标/G4 章上图/G5 圆规/G6 尺铅笔） | 6 任务 | 2.5h |
| H 基准态 fixture+比对流水线 | 2 任务 | 1.0h |
| Loop ×5（实拍→分级→设计师→实施→存档） | 5 轮 | 5.0h |
| V 终验（全分支审查+修复波次+收口） | 3 | 1.0h |
| **合计** | | **≥14.5h** ✓（预算保护同 v3：提前收敛则 Loop 加深、B/D-B 解禁至 10h 下限） |

---

## Phase P0 — 基准登记与比对报告

### Task P0.1: 基准切换登记

**Files:** Modify: `docs/reports/ui-replication-report.md`

- [ ] 顶部追加「基准升级声明」：产品 mockup（u1fak0）自本计划起为唯一视觉基准；15 项物料板降级为切图规范参考；像素比对数据（上文表）全文引用。
- [ ] Commit `docs: 视觉基准升级登记为成品图`

### Task P0.2: 比对流水线固化

**Files:** Create: `docs/assets/compare_regions.py`

- [ ] 把本次比对逻辑固化为可重复脚本（缩放→4×4 区域差→关键采样→side-by-side 存证，代码=本计划上文执行过的 PIL 段，落盘为 argparse 脚本：`python docs/assets/compare_regions.py <design.png> <current.png> <outdir>`）。
- [ ] Commit `feat: 区域比对流水线固化`；**派评审**。

---

## 批次 D — 构图与取景（S1/S4/A7）

### Task D1: 近景取景重构

**Files:** Modify: `static/js/chartRenderer.js`

- [ ] **红测**：test_ui_assets.py 追加——

```python
def test_close_framing_constants():
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "/ 45)" in js, "取景未改 45nm 近景"
    assert "CHART_VIEW_NM = 45" in js, "视野常量未提取"
```

- [ ] 实现：`const CHART_VIEW_NM = 45;`，`chartNmToPx(nm, w, h) { return (nm / CHART_VIEW_NM) * (Math.min(w, h) / 2 - 30); }`；`drawRangeRings` 中 60nm 环允许出画（设计即如此，不加特判）；环礁 rx/ry 由 `chartNmToPx(23/17)` 自动放大，目检微调至「20nm 环贯穿环礁内部、40nm 出上缘」。
- [ ] `node --check` + pytest + 无头 Chrome 目检（环礁占比 ~70% 图表面积）。
- [ ] Commit `feat: 45nm 近景取景重构`；**派评审**。

### Task D2: 整体色调加深压黄（S4）

**Files:** Modify: `docs/assets/normalize_texture.py`、`static/assets/textures/paper_tex.jpg`、`static/css/style.css`

- [ ] **红测**：test_texture_assets.py 的 paper 目标色 (245,237,214) → (225,207,168)（采样设计图面 (231,206,159) 的提亮版），容差不变 → FAIL。
- [ ] normalize_texture.py 的 paper 目标同步 → 重跑脚本再生成 → 转绿；style.css 若有硬编码纸色 overlay 同步压暗。
- [ ] 全量 pytest + 目检（图面/顶栏/卡片三处同步变黄变旧）。
- [ ] Commit `feat: 纸面色调压黄加深对齐成品图`；**派评审**。

### Task D3: 海图深色画框

**Files:** Modify: `static/css/style.css`（#chart-area 边框）

- [ ] 设计图海图四周有厚深木框（~10px，#2b2118 系）。`#chart-area { border: 10px solid #2b2118; border-radius: 2px; }`（新色值登记 SVG_PALETTE 注释或用 ink 变体 rgba）。目检 + Commit `feat: 海图深色厚画框`。

### Task D4: NE hatch 块与放射细线（A7）

**Files:** Modify: `static/js/chartRenderer.js`

- [ ] NE 角（环礁右上）加斜线 hatch 块（复用 SW 斜线绘制逻辑，区域改为环礁外东北矩形，线更细 5px 步进）。
- [ ] 环礁周围加放射状细线（等深线感）：以环礁中心为圆心，r 从 reef 外缘起每 18px 画一圈极淡椭圆（`strokeStyle: rgba(42,34,24,0.08)`，3 圈）。
- [ ] 目检对照成品图 NE 区 → Commit `feat: NE hatch 块与环礁放射细线`；**派评审**。

---

## 批次 E — Chrome 深色化（S2/S3/A8/A9/B1）

### Task E1: 新 chrome token 组与底栏深色化（S2）

**Files:** Modify: `static/css/style.css`、`tests/test_ui_assets.py`（token 断言扩充）

- [ ] **红测**：CSS_TOKENS 增 `--color-bar-dark: #332a20`、`--color-bar-text: #d8cbb2`、`--color-damage: #c25b3a`（采样成品图底栏底色/文字/损伤橙红）。
- [ ] `#bottom { background: var(--color-bar-dark); }`、`.dash-label { color: var(--color-bar-text); opacity: .65; }`、`.dash-val { color: var(--color-bar-text); }`、损伤值红字样式 `.dash-val-damage { color: var(--color-damage); }`（uiController 损伤非 OK 时挂类）。
- [ ] 转绿+目检（底栏深棕黑+浅字+橙红损伤）→ Commit `feat: 底栏深色化（chrome token 组）`；**派评审**。

### Task E2: 右栏深色化 + INTEL 深卡（S3）

**Files:** Modify: `static/css/style.css`、`static/js/uiController.js`

- [ ] `#sidebar { background: #241c14; }`（采样成品图右栏底 (62,46,36) 压暗版，登记）；INTEL 消息卡改深底浅字（复用 .msg-classified 深卡变体——INTEL 卡常驻深色）；PLAYER 卡保留红棕头条+浅字。
- [ ] 目检对照成品图右栏 → Commit `feat: 右栏深色化与 INTEL 深卡`；**派评审**。

### Task E3: 标签深色白字（A9）

**Files:** Modify: `static/css/style.css`

- [ ] `.npc-tab::before { background: #2b2118; }`、`.npc-tab { color: var(--color-bar-text); }`、`.npc-tab.active::before { background: var(--color-paper-base); } .npc-tab.active { color: var(--color-ink-main); }`（INTEL 式白底激活）。
- [ ] 目检 → Commit `feat: 标签深色白字（INTEL 白底激活）`；**派评审**。

### Task E4: 顶栏齿轮图标（B1）

**Files:** Create: `static/assets/ui/gear.svg`；Modify: `static/index.html`

- [ ] 手绘 8 齿齿轮 SVG（圆环+齿+中孔，ink 色，24px）置顶栏最右；缓存号递增。
- [ ] Commit `feat: 顶栏齿轮图标`；**派评审**。

---

## 批次 G — 地图要素（A1–A6）

### Task G1: ENT/HOR 空心圆圈标记 + 双虚线箭头矢量（A1，计数牌退役）

**Files:** Modify: `static/js/chartRenderer.js`（drawTaskForceMarker 重写）、`static/js/mapRenderer.js`、`tests/ui/route_display.test.mjs`（锚点同步）

- [ ] **红测**：test_ui_assets.py 追加——`assert "circle-outline" in js`（新函数名锚点）。
- [ ] 实现（替换计数牌分支）：

```javascript
function drawTaskForceMarker(ctx, tf, w, h, ox = 0, oy = 0) {
  // 空心圆圈标记（成品图形态）：r=10 空心 + 字标 + 航向线 + 双虚线箭头矢量指向环礁
  const ac = { x: atollCenter(w, h).x - ox, y: atollCenter(w, h).y - oy };
  ctx.save();
  ctx.strokeStyle = CHART_STYLE.ink; ctx.lineWidth = 2.5;
  ctx.beginPath(); ctx.arc(tf.x, tf.y, 10, 0, Math.PI * 2); ctx.stroke();       // circle-outline
  ctx.fillStyle = CHART_STYLE.ink;
  ctx.font = `bold 11px ${CHART_STYLE.fontTypewriter}`;
  ctx.fillText(tf.callsign, tf.x - 14, tf.y - 16);                               // 字标在圈左上
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
```

- [ ] mapRenderer 调用处去掉计数牌分支；计数牌引用注释保留（素材退役）。route_display.test.mjs 锚点从 CSE 坐标系同步。
- [ ] `node tests/ui/route_display.test.mjs` PASS + 全量 pytest + 目检（对照成品图 ENT/HOR+双虚线箭头）。
- [ ] Commit `feat: 舰队标记复刻为空心圆圈+双虚线箭头矢量（计数牌退役）`；**派评审**。

### Task G2: 飞机剪影上航线（A2）

**Files:** Modify: `static/js/mapRenderer.js`

- [ ] 实现：`_drawScoutAircraft` 内对每架在途侦察机（active_scouts，status 为 outbound/returning）在当前位置叠画 `getIcon('aircraft_topdown')`（w≈26px，rotate 朝航向：`ctx.rotate(bearing)`），剪影沿航线插值移动（复用现有 scout 插值位置）。
- [ ] **验收必须走 fixture**（空态无机载）：H 批 fixture 就绪前先用单测桩 state（含 1 架 active_scout）在 route_display.test.mjs 断言剪影 drawImage 被调用且坐标==插值位置。
- [ ] Commit `feat: 侦察机剪影沿航线绘制`；**派评审**。

### Task G3: 敌标双红圈（A3）

**Files:** Modify: `static/js/mapRenderer.js`（_drawEnemyContacts 已有——核对成品图形态：红色虚线圈+?, 非 ENEMY 字样版）

- [ ] 成品图敌标 = 红色虚线圆圈 + 中央红 ？（无 ENEMY 字）。enemy_marker.svg（带 ENEMY 字样）保留给战报；地图标记改用 `enemy_tag_q.png`（红底白？方块）或新画红虚线圈？裁定：**用 enemy_tag_q 红方块**（已入库、质量门 PASS）+ 缩放 0.8，保持现渲染调用。若目检与成品图圆形差异明显，再补红色虚线圈 SVG（新资产走质量门）。
- [ ] fixture 下目检双红圈 → Commit `feat: 敌情标记对齐成品图形态`；**派评审**。

### Task G4: SECRET 章上地图左上（A4）

**Files:** Modify: `static/js/chartRenderer.js`（drawAll 尾部）

- [ ] `drawAll` 末尾（比例尺后）：`const stamp = getIcon('secret_stamp'); if (stamp) ctx.drawImage(stamp, 24, 20, 180, 76);`（横版大章，rotate 用 ctx 变换 -10°）。
- [ ] 目检 → Commit `feat: SECRET 章上地图左上`；**派评审**。

### Task G5: 黄铜圆规道具（A5）

**Files:** Create: `static/assets/ui/icons/compass_brass.png`（分拆产物）；Modify: `static/index.html`（desk prop）

- [ ] **素材来源裁定（2026-09-12 勘验后锁定）**：从 u1fak0 直接裁**不可行**——圆规为写实黄铜材质，压在非纯色底上（叠木尺/图框双线/虚线航线），矩形裁切会带杂质，alpha 抠图对金属反光边缘质量风险高；且整块场景贴片会把设计图的图框线带入与我们自绘图框冲突。**采用 button_26 分拆路线**：`docs/assets/icons_extracted/button_26_88x354.png`（铅笔+圆规工具条，透明底现成）分拆圆规段——风格与既有桌面道具同族。
- [ ] Read button_26 定分割框 → Pillow 裁切+trim → `static/assets/ui/icons/compass_brass.png` → quality_gate（G4 多部件按 MANUAL 目检裁决先例）。
- [ ] 桌面左下接入（横放木尺旁，rotate 约 15°，drop-shadow 同族）。
- [ ] 目检 → Commit `feat: 黄铜圆规桌面道具（button_26 分拆）`；**派评审**。

### Task G6: 尺与铅笔移位（A6，按成品图勘测修正）

**Files:** Modify: `static/css/style.css`

- [ ] **成品图实际布局**（勘测修正，推翻 v1 草案「尺竖放右缘」）：**木尺横放左下**（压海图左缘，与圆规同侧）、**铅笔竖放右缘**（笔尖朝下）、右侧另有一把斜放直尺（不再新造，ruler_wood 横放即可）。当前实现：尺/铅笔均横放底部中央——需移位。
- [ ] `.desk-ruler { left: 6px; right: auto; bottom: 54px; transform: rotate(-3deg); }`（横放左下压图缘）；`.desk-pencil { right: 14px; left: auto; bottom: 120px; transform: rotate(180deg) 或垂直翻转; height: 200px; width: auto; }`（竖放右缘笔尖朝下，以目检调优）。限制：不遮比例尺/罗盘/经纬标注。
- [ ] 目检对照成品图 → Commit `feat: 尺与铅笔按成品图布局移位`；**派评审**。

---

## 批次 H — 基准态 fixture 与比对流水线

### Task H1: 设计态 fixture 页面

**Files:** Create: `static/dev/design-fixture.html`、`static/dev/design-state.js`

- [ ] fixture 页面：加载真实渲染器三件套 + 设计态 canned state（09:45Z、AP 14/20、task_forces 双舰队（course 270）、known_enemy ×2（NE 双红圈位）、active_scouts ×1（HOR 西南航线）、损伤 minor、甲板 14 SBD/TBD、侦察 30°-90°、敌情 4 CV / 2 BB）→ `render(state)`。
- [ ] 页面顶部加「FIXTURE — 非游戏画面」小字条（防误认）。README 注明仅用于像素比对。
- [ ] Commit `feat: 设计态渲染 fixture（像素比对专用）`；**派评审**。

### Task H2: 像素比对验收流

- [ ] 无头 Chrome 截 fixture 页 → `compare_regions.py 成品图 fixture截图` 出区域差报告 → 存 docs/reports/product-compare/。
- [ ] 验收线：4×4 区域均色差最大格 ≤ 45（当前 98.7），图面空白采样 B 通道差 ≤ 20（当前 41）；结构要素（圆圈标记/双虚线/飞机/敌标/章/圆规/深 chrome）逐项在位。
- [ ] Commit `test: 基准态像素比对验收流`；**派评审**。

---

## Loop ×5（同 v3 纪律）

- 每轮 L1 实拍（**fixture 页 + 游戏空态页双截图**）→ L2 对照分级（对照基准=成品图）→ L3 设计师 agent（prompt 模板沿用，基准图替换为 u1fak0）→ L4 方案 → L5 实施 → L6 存档。
- Fidelity 评分基准换为成品图 15 项新映射表（Loop 1 的 L2 重建该表——原表以物料板为准，作废重评）。
- 预算保护：S/A/D-S 清零且工时 <10h → 加深轮次、B/D-B 解禁至 10h 下限。

## Phase V — 终验

- V1 全分支审查（P0 BASE..HEAD）→ V2 单修复波次+范围化复审 → V3 收口（ui-replication-report 基准升级终章、AGENTS.md 测试基数、工作区清理）。

## 验收总表

| 差距 | 任务 | 门 |
|------|------|-----|
| S1 近景取景 | D1 | 红测+目检 |
| S4 色调压黄 | D2 | 纹理门红绿+目检 |
| S2/S3 底/右栏深色化 | E1/E2 | token 红绿+目检 |
| A9 标签深色/A8 损伤红字/B1 齿轮 | E3/E1/E4 | 目检 |
| A1 圆圈标记+矢量 | G1 | 红测+录制器+目检 |
| A2 飞机剪影 | G2 | 录制器断言+fixture 目检 |
| A3 敌标 | G3 | fixture 目检 |
| A4 章上图 / A5 圆规 / A6 尺铅笔 | G4/G5/G6 | 质量门+目检 |
| 像素比对验收 | H1/H2 | 区域差 ≤45 + 结构要素清单 |
| 整体收敛 | Loop ×5 | 双曲线趋势不降；末轮 S=0 |
| 工程质量 | V1–V3 | 全分支 APPROVE |

## Self-Review 记录

- **基准切换的连锁影响已穷举**：15 项映射表作废重评（Loop 1 L2）、计数牌退役、 troops fixture 纪律、 Loop 实拍双页（fixture+空态）。
- **占位符扫描**：G1/G2/H1 核心代码完整；G3 两方案（红方块沿用/补虚线圈）给了裁决规则；「参数名以源码为准」处均附 grep 程序。
- **依赖一致性**：D1 改变全部地图几何 → 必须先于 G（G 的坐标断言依赖新取景）；H1 依赖 G2/G3 的状态字段消费；Loop 依赖 D/E/G/H；V 收尾。顺序执行无环。
- **已知代价（登记）**：近景后 60nm 环出画、远处舰队不可见——战术信息让位于构图复现（成品图即此取舍）；fixture 页为 dev 工件常驻 static/dev/。
