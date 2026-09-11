# 保真度修正计划：实拍对照差距修复（ui-fidelity-fix-plan）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
> 前置计划：`docs/plans/ui-replication-plan.md`（已执行完毕，15/15 验收）。本计划修复终审实拍对照发现的 7 处真实差距。

**Goal:** 修复实拍对照（2026-09-11）发现的 7 处视觉差距——罗盘华丽度、SAND ISLAND 岛体压坐标、纸张做旧度、环礁立体感与 SW 海面斜线、25nm 距离环、引导线箭头与指向、标签激活凸起。

**Architecture:** 全部为既有资产的修订与新绘制（2 个 SVG 重绘/增强、chartRenderer.js 绘制修正、style.css 标签样式），零新增文件、零新增依赖。

**Tech Stack:** 同前置计划（原生 SVG/Canvas/CSS + pytest 静态守卫）。

**Spec:** 对照结论（2026-09-11 实拍 vs `docs/assets/ChatGPT Image 2026年6月17日 10_55_51.png`）——本计划 §0 逐条引用。

## Global Constraints（沿用前置计划）

- 色值只允许 `SVG_PALETTE`（tests/test_ui_assets.py 白名单）；新增色值须先登记。
- 改动任何 SVG/CSS/JS 后递增 `static/index.html` 全量 `?v=`（当前 1780997988）并同步缓存守卫测试 pin；**被 svgLoader 加载的资产文件本身无缓存参数，被修改的资产须在 `ICON_FILES` 对应 URL 后追加 `?v=<新版本号>`**。
- 每任务「改→node --check/pytest→提交」；全量 `pytest tests/ -q` 保持 253+ 全绿 0 skipped。
- 不 push、不派发子代理（执行时由控制者派发）、零新增依赖。
- 目检分工：SVG 由控制者 qlmanage 渲染核验，页面由控制者无头 Chrome 截图核验（IAB 通道不稳定，直接用 `/Applications/Google Chrome.app` headless）。

## 工作量

6 个任务、约 30 个执行步骤，预计 **1.5–2.5 小时**。建议 2 批派发：批 A = T1+T5（两个 SVG 资产），批 B = T2+T3+T4+T6（chartRenderer/CSS）。

## 范围外（用户拍板项，本计划不动）

- ENT/HOR 形态保持光栅计数牌（设计图为空心圆圈）—— Phase 6/7 既有裁定。
- 整体色温保持 `UI_DESIGN.md` token（`--color-paper-base:#f5edd6`），做旧感一律走纹理层，不改 token。
- 环礁占比保持真实地理比例（设计图的非比例夸张不采纳）。

---

## Task 1: 罗盘重绘为华丽多针版（A6）

**Files:**
- Modify: `static/assets/ui/compass.svg`（整文件重写）
- Modify: `tests/test_ui_assets.py`（compass 关键字追加）

- [ ] **Step 1: 更新守卫**——`ASSET_MANIFEST` 中 compass 条目关键字改为 `["use href", ">N<", ">E<", ">S<", ">W<"]`（`use href` 断言复用结构存在）。先运行确认 FAIL（现文件无 `use href`… 注意现文件已有 `<use href="#cardinal">`——若已含则本步自然 PASS，跳过红测直接进入 Step 2，如实记录）。

- [ ] **Step 2: 重写 compass.svg**

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
  <defs>
    <g id="ptLong">
      <polygon points="100,8 107,100 100,100" fill="#2a2218"/>
      <polygon points="100,8 93,100 100,100" fill="#f5edd6" stroke="#2a2218" stroke-width="1"/>
    </g>
    <g id="ptShort">
      <polygon points="100,32 105,100 100,100" fill="#2a2218"/>
      <polygon points="100,32 95,100 100,100" fill="#f5edd6" stroke="#2a2218" stroke-width="0.8"/>
    </g>
  </defs>
  <!-- 刻度外环：粗描边虚线圆近似放射状刻度 -->
  <circle cx="100" cy="100" r="96" fill="none" stroke="#2a2218" stroke-width="1.5"/>
  <circle cx="100" cy="100" r="91" fill="none" stroke="#2a2218" stroke-width="7" stroke-dasharray="1.2,4.6"/>
  <circle cx="100" cy="100" r="64" fill="none" stroke="#2a2218" stroke-width="1"/>
  <circle cx="100" cy="100" r="30" fill="none" stroke="#2a2218" stroke-width="1"/>
  <!-- 8 长针（每 45°） -->
  <use href="#ptLong"/>
  <use href="#ptLong" transform="rotate(45 100 100)"/>
  <use href="#ptLong" transform="rotate(90 100 100)"/>
  <use href="#ptLong" transform="rotate(135 100 100)"/>
  <use href="#ptLong" transform="rotate(180 100 100)"/>
  <use href="#ptLong" transform="rotate(225 100 100)"/>
  <use href="#ptLong" transform="rotate(270 100 100)"/>
  <use href="#ptLong" transform="rotate(315 100 100)"/>
  <!-- 8 短细针（偏移 22.5°） -->
  <use href="#ptShort" transform="rotate(22.5 100 100)"/>
  <use href="#ptShort" transform="rotate(67.5 100 100)"/>
  <use href="#ptShort" transform="rotate(112.5 100 100)"/>
  <use href="#ptShort" transform="rotate(157.5 100 100)"/>
  <use href="#ptShort" transform="rotate(202.5 100 100)"/>
  <use href="#ptShort" transform="rotate(247.5 100 100)"/>
  <use href="#ptShort" transform="rotate(292.5 100 100)"/>
  <use href="#ptShort" transform="rotate(337.5 100 100)"/>
  <circle cx="100" cy="100" r="5" fill="#2a2218"/>
  <g font-family="'Special Elite', monospace" font-size="15" fill="#2a2218" text-anchor="middle">
    <text x="100" y="30">N</text>
    <text x="170" y="105">E</text>
    <text x="100" y="182">S</text>
    <text x="30" y="105">W</text>
  </g>
</svg>
```

- [ ] **Step 3: 转绿** — `pytest tests/test_ui_assets.py -v` 全 PASS。
- [ ] **Step 4: 缓存** — `static/js/svgLoader.js` 中 compass 的 ICON_FILES URL 追加 `?v=1780997989`（资产文件缓存参数，Global Constraints）。
- [ ] **Step 5: 目检** — 控制者 qlmanage 渲染：16 针 + 刻度环 + 字母清晰。
- [ ] **Step 6: Commit** `feat: A6 罗盘重绘为华丽多针版（刻度外环/长短针）`

## Task 2: 环礁绘制修正（岛体避让/SW 海面斜线/沙环立体感）

**Files:**
- Modify: `static/js/chartRenderer.js`（drawIslands、drawAtoll）

- [ ] **Step 1: SAND ISLAND 避让中心坐标**——drawIslands 中沙岛矩形改为泻湖西南更低处（中心标注坐标行在 `c.y+20`，岛体上缘须低于它）：

```javascript
  const sx = c.x - rx * 0.60, sy = c.y + ry * 0.32;
```

沙岛标签保持在矩形下方（现 `sy + ry * 0.16 + 10` 不动）。几何自检：岛体上缘 `c.y+0.32ry ≈ c.y+29 > c.y+20` ✓，岛底 `c.y+0.48ry`、标签 `c.y+0.56ry`，均在泻湖内缘 `c.y+0.74ry` 之上 ✓。

- [ ] **Step 2: SW 海面大片斜线（移到环礁填充之前）**——drawAtoll 中删除现有「clip 到放大轮廓」的斜线块，替换为在 `tracePath(ctx, outer)` 填充沙色**之前**执行：

```javascript
  // 西南海面斜线阴影：先铺后盖（环礁填充会盖住多余部分）
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

- [ ] **Step 3: 沙环下缘投影**——在沙色填充之后、泻湖填充之前插入（外轮廓向下偏移描一圈暗色，形成立体投影）：

```javascript
  ctx.save();
  ctx.translate(2, 3);
  tracePath(ctx, outer);
  ctx.strokeStyle = 'rgba(42, 34, 24, 0.35)';
  ctx.lineWidth = 2.5;
  ctx.stroke();
  ctx.restore();
```

（`rgba(42,34,24,…)` 为 `--color-ink-main` 的透明变体，色板合规。）

- [ ] **Step 4: 验证** — `node --check static/js/chartRenderer.js`；`pytest tests/ -q` 253 全绿；控制者无头 Chrome 截图目检（岛体不再压坐标、SW 海面斜线成片、沙环有投影）。
- [ ] **Step 5: Commit** `feat: 环礁绘制修正（岛体避让/SW海面斜线/沙环投影）`（含缓存号递增，见 Task 6）

## Task 3: 距离环补 25nm 内环

**Files:**
- Modify: `static/js/chartRenderer.js`（RING_NM）、`tests/test_ui_assets.py`（字面量断言）

- [ ] **Step 1: 红测**——`test_chart_renderer_constants_match_css` 的 label 列表追加 `"25nm"`，运行确认 FAIL。
- [ ] **Step 2:** `const RING_NM = [["20nm", 20], ["25nm", 25], ["40nm", 40], ["60nm", 60]];`
- [ ] **Step 3: 转绿** → **Step 4: Commit** `feat: 距离环补 25nm 内环`（并入 Task 5 的缓存号提交亦可）

## Task 4: 引导线指向环礁 + 箭头

**Files:**
- Modify: `static/js/chartRenderer.js`（drawTaskForceMarker 签名与引导线）、`static/js/mapRenderer.js`（调用点）

- [ ] **Step 1:** 签名改 `drawTaskForceMarker(ctx, tf, w, h)`；删除写死的 `(tf.x-60, tf.y+18)` 虚线段，替换为：

```javascript
  // 引导线指向环礁中心（虚线 + 箭头）
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

- [ ] **Step 2:** mapRenderer.js 调用点改为 `ChartRenderer.drawTaskForceMarker(ctx, tfData, W, H)`（W/H 即 render() 现用的 CSS 像素宽高）。
- [ ] **Step 3:** `node --check` 两文件；全量 pytest；目检箭头指向环礁。
- [ ] **Step 4: Commit** `feat: 舰队引导线指向环礁并带箭头`

## Task 5: 纸张做旧增强（A2）

**Files:**
- Modify: `static/assets/ui/paper_base.svg`（整文件重写）、`tests/test_ui_assets.py`（关键字）

- [ ] **Step 1: 红测**——paper_base 关键字追加 `"stainsBig"`，运行确认 FAIL。
- [ ] **Step 2: 重写 paper_base.svg**（大渍斑层 + 原渍斑增强 + 边缘焦化）：

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">
  <defs>
    <filter id="stainsBig" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.006" numOctaves="2" seed="19"/>
      <feColorMatrix type="matrix" values="0 0 0 0 0.52  0 0 0 0 0.42  0 0 0 0 0.24  0 0 0 0.5 0"/>
      <feComponentTransfer><feFuncA type="discrete" tableValues="0 0 0 0.2 0 0.45"/></feComponentTransfer>
    </filter>
    <filter id="stains" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="3" seed="11"/>
      <feColorMatrix type="matrix" values="0 0 0 0 0.55  0 0 0 0 0.45  0 0 0 0 0.28  0 0 0 0.55 0"/>
      <feComponentTransfer><feFuncA type="discrete" tableValues="0 0 0 0 0.15 0 0.4 0.65"/></feComponentTransfer>
    </filter>
    <radialGradient id="edgeBurn" cx="50%" cy="50%" r="72%">
      <stop offset="0%" stop-color="#3a2518" stop-opacity="0"/>
      <stop offset="76%" stop-color="#3a2518" stop-opacity="0"/>
      <stop offset="100%" stop-color="#3a2518" stop-opacity="0.3"/>
    </radialGradient>
    <filter id="grain" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7"/>
      <feColorMatrix type="matrix" values="0 0 0 0 0.42  0 0 0 0 0.36  0 0 0 0 0.26  0 0 0 0.18 0"/>
    </filter>
  </defs>
  <rect width="1200" height="900" fill="#f5edd6"/>
  <rect width="1200" height="900" filter="url(#stainsBig)" opacity="0.7"/>
  <rect width="1200" height="900" filter="url(#stains)" opacity="0.6"/>
  <rect width="1200" height="900" fill="url(#edgeBurn)"/>
  <rect width="1200" height="900" filter="url(#grain)"/>
</svg>
```

- [ ] **Step 3:** svgLoader 中 paper_base 的 URL 追加 `?v=1780997989`（与 Task 1 同版本号）。
- [ ] **Step 4: 转绿 + 目检**（控制者 qlmanage：大渍斑成片、边缘焦化）→ **Step 5: Commit** `feat: A2 纸张做旧增强（大渍斑/边缘焦化）`

## Task 6: 标签激活凸起增强 + 缓存号收口

**Files:**
- Modify: `static/css/style.css`、`static/index.html`、`tests/test_ui_assets.py`（缓存 pin）

- [ ] **Step 1:** `.npc-tab` 族改造（伪元素承载切角底色，元素本体恢复投影能力）：

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

（`isolation: isolate` 使 `::before` 的 `z-index:-1` 落在标签底色层而非标签条背景之后；旧 `.npc-tab` 规则中的 `background`/`clip-path` 行删除，避免双底色。）

- [ ] **Step 2:** index.html 全量 `?v=1780997988→1780997989`；同步 `tests/test_ui_assets.py` 缓存守卫 pin。
- [ ] **Step 3:** 全量 pytest 253 全绿；目检激活 tab 高凸 + 投影可见。
- [ ] **Step 4: Commit** `feat: 标签激活凸起增强与缓存号收口`

---

## 验收（控制者执行）

1. `pytest tests/ -q` 全绿 0 skipped；`node --check` 全部涉及 JS。
2. 无头 Chrome 整页截图 vs 设计图复对照：罗盘 16 针、岛体避让、SW 海面斜线、25nm 环、箭头指向、纸张陈旧感、标签凸起——7 项逐条打勾，记入 `docs/reports/ui-replication-report.md`「保真度修正轮」小节。
3. 每批派发后走「红测→实现→转绿→目检→提交」，评审沿用前置计划的两层把关。

## Self-Review 记录

- **覆盖**：§一表 7 项真实差距全部映射（1→T1、2→T2S1、3→T5、4→T2S2/S3、5→T3、6→T4、7→T6）。
- **契约一致性**：所有新色值在 SVG_PALETTE 或其透明变体；缓存号策略含 svgLoader 资产 URL 追加参数（新覆盖点，已写明）；RING_NM 标签对结构沿用。
- **占位符扫描**：无 TBD；T2S1 几何自检给出数值验证路径。
