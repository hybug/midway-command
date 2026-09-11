# 保真度修正计划 v2：批次 A（SVG 先行）+ 批次 B（AI 生成图）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
> 前置计划：`docs/plans/ui-replication-plan.md`（已执行完毕，15/15 验收）。本计划 v2 取代 v1（`ui-fidelity-fix-plan.md` 初版），依据 2026-09-11 实拍对照结论与「SVG/AI 生成/网图」三档素材评估重构。

**Goal:** 修复实拍对照发现的 7 处真实差距。批次 A 用 SVG/程序化完成全部几何与线条类修正（可立即执行）；批次 B 用 AI 生成图升级三处「有机质感」（纸张/木纹/罗盘雕刻感）——控制者按本计划给出的提示词生成图片并交付，执行者过质量门后集成。批次 A+B 完成后进入 **Loop 模式**：「实拍对照 → 差距分级 → 新方案 → 实施」闭环**至少 5 轮**，直至与设计图逐项收敛。

**Architecture:** 批次 A 全部为既有资产修订（chartRenderer.js 绘制修正、style.css、SVG 重绘），零新增文件。批次 B 新增 `static/assets/ui/textures/`（AI 纹理图）与新守卫 `tests/test_texture_assets.py`（无缝平铺检测）；木纹以 data-URI 内嵌进 ruler.svg（`<img>` 引用的 SVG 不允许外部资源，必须内嵌）；罗盘 AI 版走既有抠图→质量门→curate 链路。

**Tech Stack:** 同前置计划 + Pillow（平铺接缝检测、data-URI 内嵌、色温归一）。

**Spec:** 实拍对照结论（2026-09-11）+ 素材三档评估（SVG 正解 11 项 / AI 生成 3 项 / 抠图链路已验证）。

## 批次与依赖

```
批次 A（SVG 先行，可立即执行，预计 1–1.5h）
  T0 罗盘零成本试换（库内 compass_raster.png）※ 素材到位后由 B3 直接接替，T0 简化为回归验证
  T1 环礁绘制修正（岛体避让/SW海面斜线/沙环投影）
  T2 距离环补 25nm
  T3 引导线指向环礁+箭头
  T4 标签激活凸起增强
批次 B（AI 生成图，素材已到位，可执行，预计 1–1.5h）
  B1 旧纸无缝纹理（A2/A11）
  B2 木纹贴图（A14）
  B3 AI 雕刻罗盘（P3 质量已确认，启用）
批次 A 中的 T5 罗盘 SVG 重绘取消（B3 已有更优质素材）。
Loop（A+B 完成后启动，「对照-方案-实施」闭环 ≥5 轮，预计 3–5h）——详见「Loop 模式」章节。
```

## Global Constraints（沿用前置计划）

- 色值只允许 `SVG_PALETTE`；AI 图**不改 token**，色温归一一律走纹理本身或 overlay。
- 改动 CSS/JS 后递增 `static/index.html` 全量 `?v=`（当前 1780997989）并同步缓存守卫 pin；被 svgLoader 加载的资产修改时在 `ICON_FILES` URL 追加 `?v=`。
- 每任务「红测→实现→转绿→目检→提交」；全量 `pytest tests/ -q` 保持 253+ 全绿 0 skipped。
- 目检：SVG 用 qlmanage，页面用无头 Chrome（`/Applications/Google Chrome.app --headless=new --screenshot --virtual-time-budget=9000`；IAB 通道不稳定弃用）。
- **批次 B 质量门（AI 图专用，集成前强制）**：
  1. **无缝平铺检测**：`Pillow` 将图平铺 2×2，接缝两侧 4px 带灰度差均值 ≤ 8/255，且目检无可见接缝；
  2. **色温归一**：纹理均值色与 `#f5edd6`（纸）/`#c9a76a`（木）做比对，偏差用 Pillow 通道缩放拉回（记录在报告）；
  3. 抠图类（B3）走既有 `extract_icons.py` → `quality_gate.py` → `curate_icons.py` 全链路；
  4. 来源与提示词登记进 `docs/reports/raster-icon-review.md` 附录。

---

## 批次 A — SVG 先行（可立即执行）

### Task T0: 罗盘零成本试换（compass_raster）

**Files:**
- Modify: `static/js/chartRenderer.js`（drawCompassRose）、`static/index.html`（缓存号）

库内已有绿幕抠图真罗盘 `static/assets/ui/icons/compass_raster.png`（评审 §3.1：质感优于 SVG 版）。

- [ ] drawCompassRose 改为优先 `getIcon('compass_raster')`，SVG `getIcon('compass')` 回退：

```javascript
function drawCompassRose(ctx, w, h) {
  const raster = getIcon('compass_raster');
  if (raster) { ctx.drawImage(raster, w - 150, 20, 110, 110 * (raster.height / raster.width)); return; }
  const icon = getIcon('compass');
  if (icon) ctx.drawImage(icon, w - 150, 24, 110, 110);
}
```

- [ ] 缓存号递增（1780997989→1780997990）随提交。
- [ ] 控制者目检：真罗盘 vs 设计图 A6——**满意则 T5（SVG 重绘）与 B3 取消；不满意记结论进 T5/B3 的取舍依据**。
- [ ] Commit `feat: 罗盘优先使用绿幕抠图真品`

### Task T1: 环礁绘制修正（岛体避让/SW 海面斜线/沙环投影）

**Files:** Modify: `static/js/chartRenderer.js`

- [ ] **岛体避让**——drawIslands 沙岛矩形移到中心坐标行（`c.y+20`）之下：`const sx = c.x - rx * 0.60, sy = c.y + ry * 0.32;`（几何自检：上缘 ≈`c.y+29` > `c.y+20` ✓；标签 `c.y+0.56ry` 在泻湖内缘 `c.y+0.74ry` 之上 ✓）。标签位置不动。
- [ ] **SW 海面斜线**——删除现「clip 到放大轮廓」斜线块，改为在 `tracePath(ctx, outer)` 沙色填充**之前**执行（先铺后盖，环礁填充自动盖掉多余部分）：

```javascript
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
```

- [ ] **沙环投影**——沙色填充后、泻湖填充前插入：

```javascript
  ctx.save();
  ctx.translate(2, 3);
  tracePath(ctx, outer);
  ctx.strokeStyle = 'rgba(42, 34, 24, 0.35)';
  ctx.lineWidth = 2.5;
  ctx.stroke();
  ctx.restore();
```

- [ ] `node --check` + 全量 pytest + 控制者无头 Chrome 目检。
- [ ] Commit `feat: 环礁绘制修正（岛体避让/SW海面斜线/沙环投影）`（缓存号随 T2/T4 批内收口）

### Task T2: 距离环补 25nm 内环

**Files:** Modify: `static/js/chartRenderer.js`、`tests/test_ui_assets.py`

- [ ] 红测：`test_chart_renderer_constants_match_css` 的 label 列表追加 `"25nm"` → FAIL。
- [ ] `const RING_NM = [["20nm", 20], ["25nm", 25], ["40nm", 40], ["60nm", 60]];`
- [ ] 转绿 → Commit `feat: 距离环补 25nm 内环`

### Task T3: 引导线指向环礁 + 箭头

**Files:** Modify: `static/js/chartRenderer.js`、`static/js/mapRenderer.js`

- [ ] `drawTaskForceMarker(ctx, tf, w, h)`；删写死 `(tf.x-60, tf.y+18)` 段，替换为：

```javascript
  const ac = atollCenter(w, h);
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
```

- [ ] mapRenderer 调用点传 `(ctx, tfData, W, H)`。
- [ ] `node --check` + pytest + 目检（箭头指向环礁）。
- [ ] Commit `feat: 舰队引导线指向环礁并带箭头`（批内最后一次提交递增缓存号→1780997990，同步 pin）

### Task T4: 标签激活凸起增强

**Files:** Modify: `static/css/style.css`

- [ ] 伪元素承载切角底色，本体恢复投影（`isolation: isolate` 防 `z-index:-1` 伪元素被父背景吞掉）：

```css
.npc-tab { position: relative; isolation: isolate; background: transparent; }
.npc-tab::before {
  content: ""; position: absolute; inset: 0; z-index: -1;
  clip-path: polygon(0 100%, 0 6px, 6px 0, calc(100% - 6px) 0, 100% 6px, 100% 100%);
  background: var(--color-paper-dark);
}
.npc-tab.active::before { background: var(--color-paper-base); }
.npc-tab.active { transform: translateY(-6px); box-shadow: 0 -3px 6px rgba(0, 0, 0, 0.25); }
```

- [ ] 旧 `.npc-tab` 规则中的 `background`/`clip-path` 行删除（避免双底色）；缓存号随 T3 收口。
- [ ] 目检（激活 tab 高凸+投影）→ Commit `feat: 标签激活凸起增强`

### 批次 A 收尾

- [ ] `pytest tests/ -q` 全绿 0 skipped；无头 Chrome 整页截图对照；验收报告追加「保真度修正·批次 A」小节。
- [ ] Commit `docs: 保真度修正批次A验收记录`

---

## 批次 B — AI 生成图（素材已到位 2026-09-11，可执行）

> **交付方式**：控制者用任意生图工具（即梦/DALL-E/Midjourney/Gemini 均可）按下述提示词生成，把图片放进 `docs/assets/ai_textures/`（文件名按提示词编号），然后说「批次 B 执行」。执行者过质量门后集成；不合格的具体说明原因并给出修订提示词。

### 素材到位与质量门初检（2026-09-11）

三张图已入库 `docs/assets/ai_textures/`（P1_paper.png / P2_wood.png / P3_compass.png，AI 生成、无第三方许可问题）。客观门 + 目检结果：

| 素材 | 尺寸 | 平铺接缝差（竖/横，/255，阈 ≤8） | 均值色 vs 目标 | 初检结论 |
|------|------|--------------------------------|----------------|---------|
| P1_paper | 1254×1254 | 6.8 / 8.0 | (238,218,180) vs #f5edd6(245,237,214) | **通过**——目检纤维纹/渍斑/水痕俱佳，轻度提亮归一即可 |
| P2_wood | 1774×887 | 18.4 / **56.3** | (192,124,51) vs #c9a76a(201,167,106) | **条件通过**——不可平铺（上下缘暗边）；尺身属「裁切拉伸」非平铺用途：裁上下缘各 ~6% 消暗边后沿长轴拉伸；色温偏橙需脱橙提亮归一 |
| P3_compass | 1254×1254 | 0.7 / 0.7 | 白底纯净（均值 223,223,224） | **通过**——铜版雕刻质感极佳（8 长针+8 细针+刻度环+NESW，纯黑白线稿），直接进抠图链路；P3 质量预期优于库内 compass_raster 与 SVG 版 |

执行调整（相对原任务描述的增量）：
- **B1 纸张**：轻度色温归一（向 #f5edd6 提亮 ~3%，记录参数）→ 存 `static/assets/ui/textures/paper_tex.jpg`（JPEG q85 控制体积）→ `drawChartBase` 改 `ctx.createPattern` 平铺 + CSS `paper_base.svg` 引用切换为纹理（SVG 版保留为回退）。
- **B2 木纹**：裁上下缘各 ~6% → 脱橙归一（降饱和、向 #c9a76a 拉回，记录参数）→ 沿长轴拉伸，以 data-URI 内嵌 ruler.svg；**不做平铺检测**（非平铺用途），以裁切归一后目检为准。
- **B3 罗盘**：P3 走 `extract_icons.py` 白底抠图 → `quality_gate.py` → `curate_icons.py` 产出 `compass_engraved.png`；细 hatch 线若在距离抠图中断裂，改用「亮度反转作 alpha」的白底直接透明法，并在报告中记录所选方式。

### 提示词 P1：旧纸无缝纹理（用于 A2 海图底/A11 顶栏/卡片）

```
Seamless tileable texture of aged 1942 nautical chart paper, warm cream color close to #f5edd6, flat top-down scan, subtle fiber grain, faint brown age spots and water stains, gently mottled surface, even flat lighting, no vignette, no shadows, no folds, no tears, no objects, no text, no watermark, tile seamlessly on all edges. Authentic old paper scan look, muted and slightly desaturated.
```

- 负向要求（工具支持 negative prompt 就填）：`vignette, gradient border, dark edges, folded corner, object, text, watermark, high contrast`
- 规格：**1024×1024 以上、必须可无缝平铺**。建议生成 2 张：标准版（如上）+ 陈旧版（把 `warm cream color close to #f5edd6` 换成 `yellowed tan aged paper, heavier stains and browning`）对照择优。
- 用途与集成：海图 Canvas 底纹（`drawChartBase` 由 `drawImage` 拉伸改为 `ctx.createPattern` 平铺）+ `style.css` 中顶栏/卡片的 `paper_base.svg` 引用换纹理（`background-repeat: repeat`）。SVG 版保留为加载失败的回退。

### 提示词 P2：旧木尺木纹（用于 A14 尺身）

```
Seamless tileable wood grain texture of worn vintage varnished wooden ruler, warm honey-tan wood close to #c9a76a, fine straight tight grain lines along one axis, small scratches and dents, slightly darkened worn edges, flat top-down view, even flat lighting, no numbers, no tick marks, no metal parts, no background, no text.
```

- 规格：1024×512 以上、可平铺（沿尺身长轴纹理走向）。
- 集成：**data-URI 内嵌**进 ruler.svg（`<img>` 引用的 SVG 禁止外部资源）：一次性脚本用 Pillow 把纹理缩到尺身比例、base64 编码写进 `<image>` + `<pattern>` 填充尺身矩形，刻度/数字图层保留在其上；脚本与产物一并提交。

### 提示词 P3（可选）：AI 雕刻罗盘（T0 目检不满意才启用）

```
Vintage nautical compass rose, copperplate engraving style, black ink lines on pure white background, top-down, perfectly centered, 8 long ornate points with alternating dark and light halves, 8 short fine points between them, graduated outer ring with fine tick marks, bold serif letters N E S W, delicate hatching, high contrast pure black and white only, no gray shading, no shadows, no other text.
```

- 规格：纯白背景+纯黑线稿（`extract_icons.py` 角点取色抠图可直接处理）；1024×1024；居中对称。
- 集成：跑抠图→`quality_gate.py`→`curate_icons.py` 产出 `compass_engraved.png` → svgLoader `ICON_FILES` 增条目 → `drawCompassRose` 优先级改为 `compass_engraved > compass_raster > compass.svg`。

### 批次 B 任务

- [ ] **B1 纸张**：质量门（平铺检测/色温归一/目检）→ 存 `static/assets/ui/textures/paper_tex.jpg` → `drawChartBase` 改 pattern 平铺 + CSS 引用切换 → 目检（海图/顶栏/卡片三处）→ Commit `feat: AI 旧纸纹理接入（Canvas 平铺+CSS）`
- [ ] **B2 木纹**：质量门 → data-URI 内嵌 ruler.svg → 目检（刻度数字在木纹上清晰）→ Commit `feat: AI 木纹接入木尺`
- [ ] **B3 罗盘（可选）**：抠图链路 → 质量门 → 接入 → 目检 → Commit `feat: AI 雕刻罗盘接入`
- [ ] 验收报告追加「保真度修正·批次 B」小节 + `raster-icon-review.md` 登记 AI 图来源/提示词/许可证结论（AI 生成=无第三方许可问题）。

---

## Loop 模式：对照-方案-实施闭环（≥5 轮）

> 批次 A+B 全部完成并验收后自动启动。目的：单轮修复后必然残留「 implementation 盲区」——每轮以**新实拍**为基准重新对照设计图，把残余差距系统性地逼出来并消化，直到逐项收敛。

### 总规则

- **轮次下限 5**。某轮若未发现新差距，仍须产出「逐项核对表 + 截图存档」作为该轮产出，**不得空转略过**；连续两轮零新差距可提前收敛（默认仍跑满 5 轮）。
- **对照由控制者亲自执行**（目检不可委派——既有分工 R5）；实施派子代理，红绿测试随行。
- **回归红线**：每轮结束时 `pytest tests/ -q` 全绿 0 skipped；前轮已修项若回退，按 S 级处理。

### 每轮流程（L1–L5）

**L1 实拍** —— 无头 Chrome 截整页（1440×900 与 1280×800）+ 分区特写（顶栏/海图区/侧栏/桌面；军令卡与聊天若能触发数据则一并实拍），存 `docs/reports/fidelity-loop/loop-N-*.png`。

**L2 对照与分级** —— 控制者持设计图逐项核对：① 15 项映射表；② 整体氛围（色调/做旧/构图/字体）；③ **回归检查**（前轮已修项是否仍复刻）。产出 `docs/reports/fidelity-loop/loop-N.md` 差距清单，每条分三级：

| 级 | 定义 | 处置 |
|----|------|------|
| **S** | 要素缺失 / 明显走样 / 前轮修复回退 | 本轮必修 |
| **A** | 可见但不影响识别 | 本轮修，或明确排入下轮（写进下轮清单） |
| **B** | 主观吹毛求疵（生成图噪点级） | 记录不修——防止过度拟合 AI 设计图的随机瑕疵 |

**L3 方案** —— 每条 S/A 级写具体修法（文件 + 改法 + 预期效果），追加进 loop-N.md。素材需求走决策树：**SVG 程序化 → 库内现成光栅 → AI 生成（给出新提示词）→ 网图（仅限公有领域/CC0）**；新素材过对应质量门（抠图链 / 平铺检测 / 色温归一）。

**L4 实施** —— 子代理按清单修复；控制者逐条目检确认关闭；S 级未关闭不得进入下一轮。

**L5 存档** —— pytest 全绿 + Fidelity 评分表更新（15 项逐项：复刻=1 / 部分=0.5 / 偏差=0，**趋势不得下降**）→ loop-N.md 终稿 + Commit（`fix: 保真度 loop-N 修复（S x个/A x个）` + `docs: loop-N 审查记录`）。

### 退出条件与升级

- **正常退出**：跑满 5 轮 且 末轮 S 级 = 0。
- **提前收敛**：跑满 5 轮后连续 2 轮零新差距（仍须出核对表）。
- **升级出口**：某 S 级连续两轮修不掉（超出 SVG/现有素材能力）→ 按「参考系」先例登记为**已知局限**，不再空转；需要新 AI 素材的 → 当轮产出提示词交控制者，轮次暂停计时。

### 工件清单

```
docs/reports/fidelity-loop/
  loop-1.md … loop-5.md      # 每轮：差距清单（分级）/ 方案 / 实施结果 / 评分
  loop-N-full-1440.png 等     # 每轮实拍存档
docs/reports/ui-replication-report.md
  → 末尾追加「Loop 汇总」小节：5 轮趋势表（轮次/新发现 S/A/B 数/修复数/Fidelity 分）
```

## 验收总表

| 差距 | 任务 | 批次 | 门 |
|------|------|------|-----|
| 罗盘华丽度 | T0（→B3 兜底） | A（→B） | 目检 |
| 岛体压坐标 | T1 | A | 目检 |
| SW 海面斜线 | T1 | A | 目检 |
| 沙环立体感 | T1 | A | 目检 |
| 25nm 环 | T2 | A | 红绿测试+目检 |
| 引导线箭头 | T3 | A | 目检 |
| 标签凸起 | T4 | A | 目检 |
| 纸张做旧 | B1 | B | 平铺门+色温门+目检 |
| 木纹质感 | B2 | B | 平铺门+目检 |
| 整体收敛 | Loop ×5（每轮对照-方案-实施） | Loop | 每轮评分趋势不降；末轮 S 级=0 |

## Self-Review 记录

- **覆盖**：实拍对照 7 项真实差距全部映射；三档评估的「AI 生成 3 项」全部落批次 B，且罗盘给了「库内现货优先」的低成本路径；Loop 模式覆盖批次完成后的系统性收敛（≥5 轮，含分级、退出、升级出口）。
- **占位符扫描**：批次 B 的集成代码形态（pattern 平铺/data-URI 内嵌/抠图链路）已写明；Loop 每步的产物路径与命令形态已写明；具体像素级参数（平铺偏移、内嵌缩放比、各轮差距条目）属执行时数据，已给获取程序。
- **依赖一致性**：T0 结论由 B3 接替；批次 B 全部素材已到位；Loop 依赖 A+B 完成，评分趋势红线防止越修越偏。
