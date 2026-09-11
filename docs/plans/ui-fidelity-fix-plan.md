# 保真度修正计划 v3：批次 A（SVG）+ 批次 B（AI 图）+ Loop×5 + 终验 —— ≥10 小时完整执行工程

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（每任务派发实现子代理 + 任务评审，本轮执行的主框架）。完成声明前遵循 superpowers:verification-before-completion（先验证后声明）；终验走 superpowers:requesting-code-review 的全分支审查；Loop 中遇缺陷先 superpowers:systematic-debugging 再修。本计划 v3 取代 v2。

**Goal:** 修复实拍对照发现的 7 处真实差距并系统性收敛：批次 A（SVG/程序化，5 任务）→ 批次 B（AI 生成图集成，4 任务）→ **Loop 模式（「实拍对照→差距分级→方案→实施」闭环 ≥5 轮）**→ 终验（全分支审查+修复波次）。总执行工时**自下而上核算 ≥10 小时**（见工作量核算表），并有预算保护条款兜底。

**Architecture:** 零新增依赖（Pillow/numpy 已在 .venv）。批次 A 修订 chartRenderer.js/style.css/svgLoader.js；批次 B 新增 `static/assets/textures/`（归一化 AI 纹理）与 `tests/test_texture_assets.py` 质量门，木纹以 data-URI 内嵌 ruler.svg，雕刻罗盘走「亮度反转 alpha」抠图链。每任务走「红测→实现→转绿→目检→**任务评审**→提交」六步，评审不合格进修复环（≤5 轮，沿用子代理驱动纪律）。

**Tech Stack:** 原生 HTML/CSS/JS + SVG/Canvas 2D + Pillow + pytest 静态守卫 + 无头 Chrome 目检（`/Applications/Google Chrome.app --headless=new`；IAB 通道不稳定，弃用）。

**Spec:** 实拍对照结论（2026-09-11）+ 素材三档评估 + `docs/assets/ai_textures/` 三张已交付素材的质量门初检（见批次 B）。

## 执行框架（superpowers 纪律）

1. **派发**：每任务一个实现子代理（简报文件制，禁贴历史）；控制器记录 BASE，产出评审包派任务评审者（SPEC ✅ + QUALITY Approved 才算完成）。
2. **评审**：每任务双重把关——客观门（pytest/node --check/质量门脚本）+ 目检（控制者无头 Chrome / qlmanage）。评审 findings 进修复环：轮 1–3 恢复原实现者，轮 4–5 换更强实现者，5 轮后控制器裁定（parked 需记台账）。
3. **台账**：`.superpowers/sdd/ui-fidelity-fix-plan/progress.md` 记录每任务完成行、rulings、deferred minors；会话中断后凭台账与 git log 恢复，禁止凭记忆重派。
4. **提交**：每任务一个 Conventional Commit（中文）；JS/CSS/SVG 变更必递增 `?v=`（当前 1780997989）并同步缓存守卫 pin。

## Global Constraints（沿用前置计划）

- 色值只允许 `SVG_PALETTE`（含其 rgba 透明变体）；AI 图**不改 token**，色温归一走纹理本身。
- 新色值/新资产先登记（`SVG_PALETTE` / `ASSET_MANIFEST` / `RASTER_ICONS` / `TEXTURE_TARGETS`）再使用。
- 只动本计划列出的文件；不碰 `src/` 游戏逻辑；不 push 远端；不派发实现子代理的子代理。
- 目检分工：实现者静态验证 + Read PNG；页面级目检由控制器无头 Chrome 截图（IAB 弃用）。

## 工作量核算表（自下而上，保证 ≥10h）

| 阶段 | 任务数 | 单任务均时（红测+实现+转绿+目检+评审+提交） | 小计 |
|------|--------|---------------------------------------------|------|
| R0 基线与纹理守卫 | 3 | 10–25 min | **0.8h** |
| 批次 A（SVG 修正） | 5 | 20–35 min | **2.2h** |
| 批次 B（AI 图集成） | 4 | 30–45 min（含管线脚本与抠图链） | **2.4h** |
| Loop ×5（每轮 L1–L5） | 5 轮 | 50–65 min/轮（实拍对照 15 + 方案 10 + 实施 20–30 + 存档评审 10） | **4.8h** |
| F 终验（全分支审查+修复波次+报告） | 3 | — | **1.0h** |
| **合计** | | | **≥11.2h** ✓ |

**预算保护条款**：若所有 S/A 级差距提前清零且总耗时 <10h，则 Loop 自动加深（第 6、7 轮…），**B 级清单在保护期内解禁为可修**，直至工时达 10h 下限或清单彻底枯竭（枯竭须逐项核对表证明）。

## 批次与依赖

```
R0 基线与纹理守卫（0.8h）
批次 A（SVG 修正，2.2h）：T0 罗盘回归验证 → T1 环礁三连修 → T2 25nm 环 → T3 引导线箭头 → T4 标签凸起
批次 B（AI 图，2.4h）：B0 纹理管线与守卫 → B1 纸张 → B2 木纹 → B3 雕刻罗盘
Loop ×5（4.8h）：L1…L5，每轮「实拍→分级→方案→实施→存档」（预算保护可加深）
F 终验（1.0h）：F1 全分支审查 → F2 修复波次+复审 → F3 报告/台账收口
```

---

## Phase R0 — 基线与纹理守卫

### Task R0.1: 修正前基线实拍

**Files:** Create: `docs/reports/fidelity-loop/loop-0-*.png`（基线即 loop-0）

- [ ] 起 uvicorn（探活 `curl localhost:8000`，占用先杀）；无头 Chrome 截整页 1440×900 与 1280×800 + 海图区/顶栏/侧栏/桌面四张特写，命名 `loop-0-full-1440.png` 等。
- [ ] 建立 `docs/reports/fidelity-loop/loop-0.md`：15 项当前状态表（复刻/部分/偏差）+ Fidelity 基线分（对照 2026-09-11 结论：罗盘、岛体压坐标、纸张做旧、SW 斜线、沙环立体、25nm、箭头、标签凸起 = 8 条已知 A/S 级，先记账）。
- [ ] Commit `docs: 保真度修正基线（loop-0 实拍与 15 项状态表）`

### Task R0.2: 纹理质量门守卫（先失败）

**Files:** Create: `tests/test_texture_assets.py`

- [ ] 写测试：

```python
"""AI 纹理素材质量门（docs/plans/ui-fidelity-fix-plan.md 批次 B）。

源素材到位性 + 集成产物的色温归一与平铺接缝断言。
"""
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "docs" / "assets" / "ai_textures"
DST = BASE / "static" / "assets" / "textures"

# 集成产物 → (接缝差阈值/255——None 表示非平铺用途不断言, 目标均值色, 通道容差)
TEXTURE_TARGETS = {
    "paper_tex.jpg": (8, (245, 237, 214), 10),
    "wood_tex.png": (None, (201, 167, 106), 14),
}


def test_source_images_present():
    for f in ["P1_paper.png", "P2_wood.png", "P3_compass.png"]:
        assert (SRC / f).exists(), f"缺少 AI 源素材 {f}"


def test_integrated_textures_normalized():
    for fname, (seam_max, target, tol) in TEXTURE_TARGETS.items():
        p = DST / fname
        assert p.exists(), f"缺少集成纹理 {fname}"
        a = np.array(Image.open(p).convert("RGB")).astype(int)
        mean = a.reshape(-1, 3).mean(axis=0)
        dev = max(abs(mean[0] - target[0]), abs(mean[1] - target[1]), abs(mean[2] - target[2]))
        assert dev <= tol, f"{fname} 均值色 {mean.round(1)} 偏离 {target} 超 {tol}"
        if seam_max is not None:
            h, w, _ = a.shape
            seam = max(
                np.abs(a[:, 0, :] - a[:, w - 1, :]).mean(),
                np.abs(a[0, :, :] - a[h - 1, :, :]).mean(),
            )
            assert seam <= seam_max, f"{fname} 接缝差 {seam:.1f} 超阈 {seam_max}"


def test_integrated_textures_size_floor():
    for fname in TEXTURE_TARGETS:
        im = Image.open(DST / fname)
        assert min(im.size) >= 400, f"{fname} 尺寸过小 {im.size}"
```

- [ ] 运行 `pytest tests/test_texture_assets.py -v` → FAIL（集成产物不存在）；**红测入库**。Commit `test: AI 纹理质量门守卫骨架（先失败）`

### Task R0.3: 评审

- [ ] 派任务评审者核 R0.1/R0.2（基线 15 项表 vs 实拍一致性；测试断言真实性）。findings 进修复环。

---

## 批次 A — SVG 修正（每任务六步：红测→实现→转绿→目检→评审→提交）

### Task T0: 罗盘优先级链切换（engraved > raster > svg）

**Files:** Modify: `static/js/chartRenderer.js`（drawCompassRose）
**Interfaces:** Produces 罗盘三级回退链；B3 产出 `compass_engraved.png` 后自动生效（svgLoader 条目在 B3 注册）。

- [ ] 实现（B3 之前的中间态：raster > svg）：

```javascript
function drawCompassRose(ctx, w, h) {
  const raster = getIcon('compass_raster');
  if (raster) { ctx.drawImage(raster, w - 150, 20, 110, 110 * (raster.height / raster.width)); return; }
  const icon = getIcon('compass');
  if (icon) ctx.drawImage(icon, w - 150, 24, 110, 110);
}
```

B3 合入时把首行改为 `getIcon('compass_engraved') || getIcon('compass_raster')`。
- [ ] `node --check`；全量 pytest；无头 Chrome 目检罗盘区域。
- [ ] Commit `feat: 罗盘优先使用绿幕抠图真品`；**派评审**。

### Task T1: 环礁绘制三连修（岛体避让/SW 海面斜线/沙环投影）

**Files:** Modify: `static/js/chartRenderer.js`（drawIslands、drawAtoll）

- [ ] **红测**：`tests/test_ui_assets.py` 追加结构断言（防回退）：

```python
def test_chart_atoll_fix_markers():
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "ry * 0.32" in js, "沙岛未下移避让坐标行"
    assert "rect(c.x - rx * 1.5" in js, "SW 海面斜线未铺开"
    assert "translate(2, 3)" in js, "沙环投影缺失"
```

运行确认 FAIL → **Step 2 实现**（三段代码见下）→ 转绿。

```javascript
// drawIslands：沙岛矩形（标签位置不动）
const sx = c.x - rx * 0.60, sy = c.y + ry * 0.32;
// drawAtoll：在 tracePath(ctx, outer) 沙色填充之前铺西南海面斜线（先铺后盖）
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
// 沙色填充后、泻湖填充前：外轮廓偏移描暗圈（立体投影）
ctx.save();
ctx.translate(2, 3);
tracePath(ctx, outer);
ctx.strokeStyle = 'rgba(42, 34, 24, 0.35)';
ctx.lineWidth = 2.5;
ctx.stroke();
ctx.restore();
```

- [ ] 删除旧「clip 到放大轮廓」斜线块（被新 SW 海面层取代）。
- [ ] `node --check` + 全量 pytest；无头 Chrome 海图特写目检三处。
- [ ] Commit `feat: 环礁绘制修正（岛体避让/SW海面斜线/沙环投影）`；**派评审**。

### Task T2: 距离环补 25nm

**Files:** Modify: `static/js/chartRenderer.js`、`tests/test_ui_assets.py`

- [ ] 红测：constants 测试 label 列表追加 `"25nm"` → FAIL。
- [ ] `const RING_NM = [["20nm", 20], ["25nm", 25], ["40nm", 40], ["60nm", 60]];` → 转绿。
- [ ] 目检四环标注；Commit `feat: 距离环补 25nm 内环`；**派评审**。

### Task T3: 引导线指向环礁 + 箭头

**Files:** Modify: `static/js/chartRenderer.js`、`static/js/mapRenderer.js`

- [ ] **红测**：

```python
def test_task_force_leader_arrow():
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "atollCenter(w, h)" in js and "closePath" in js, "引导线未指向环礁或缺箭头"
    assert "(tf.x - 60, tf.y + 18)" not in js, "写死方向未移除"
```

- [ ] 实现：签名改 `drawTaskForceMarker(ctx, tf, w, h)`；引导线替换为：

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

- [ ] mapRenderer 调用点传 `(ctx, tfData, W, H)`；`node --check` 两文件；全量 pytest；目检箭头指向环礁。
- [ ] Commit `feat: 舰队引导线指向环礁并带箭头`；**派评审**。

### Task T4: 标签激活凸起增强

**Files:** Modify: `static/css/style.css`、`static/index.html`（缓存号→1780997990 + pin 同步）

- [ ] **红测**：`tests/test_ui_assets.py` 追加 `assert "isolation: isolate" in css`（选择器 `.npc-tab` 段）。
- [ ] 实现：

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

（旧 `.npc-tab` 规则中的 `background`/`clip-path` 行删除，避免双底色。）
- [ ] 转绿 + 目检（激活 tab 高凸+投影）+ Commit `feat: 标签激活凸起增强`；**派评审**。

### 批次 A 收尾评审

- [ ] 全量 pytest + 无头 Chrome 整页对照批次 A 五项；验收报告追加「批次 A」小节；Commit `docs: 批次A验收记录`。

---

## 批次 B — AI 生成图集成（素材已到位：`docs/assets/ai_textures/` P1/P2/P3）

### Task B0: 纹理归一管线（含脚本与产物）

**Files:** Create: `docs/assets/normalize_texture.py`、`static/assets/textures/`（产物）

- [ ] 写归一脚本（完整）：

```python
#!/usr/bin/env python3
"""AI 纹理归一：裁边/色温归一 → static/assets/textures/（通道缩放法，记录于报告）。"""
from pathlib import Path

import numpy as np
from PIL import Image

SRC = Path(__file__).parent / "ai_textures"
DST = Path(__file__).parent.parent / "static" / "assets" / "textures"


def normalize(img: Image.Image, target_rgb, crop=None) -> Image.Image:
    if crop:  # (left, top, right, bottom) 比例
        w, h = img.size
        img = img.crop((int(w * crop[0]), int(h * crop[1]), int(w * (1 - crop[2])), int(h * (1 - crop[3]))))
    a = np.array(img).astype(np.float64)
    mean = a.reshape(-1, 3).mean(axis=0)
    scale = np.array(target_rgb) / np.maximum(mean, 1)
    return Image.fromarray(np.clip(a * scale, 0, 255).astype(np.uint8))


DST.mkdir(parents=True, exist_ok=True)
paper = normalize(Image.open(SRC / "P1_paper.png").convert("RGB"), (245, 237, 214))
paper.save(DST / "paper_tex.jpg", quality=85)
print("paper_tex.jpg", paper.size)
wood = normalize(Image.open(SRC / "P2_wood.png").convert("RGB"), (201, 167, 106), crop=(0.0, 0.06, 0.0, 0.06))
wood.save(DST / "wood_tex.png")
print("wood_tex.png", wood.size)
```

- [ ] 运行 → `pytest tests/test_texture_assets.py -v` 转绿 → 归一参数（scale 值）记入报告。
- [ ] Commit `feat: AI 纹理归一管线（裁边/色温归一）`；**派评审**。

### Task B1: 旧纸纹理接入（Canvas 平铺 + CSS）

**Files:** Modify: `static/js/chartRenderer.js`（drawChartBase）、`static/js/svgLoader.js`（ICON_FILES 增 paper_tex）、`static/css/style.css`（顶栏/卡片引用）、`static/index.html`（缓存号）

- [ ] **红测**：`test_chart_renderer_constants_match_css` 同文件追加 `assert "createPattern" in js`。
- [ ] 实现——svgLoader 增条目 `paper_tex: '/static/assets/textures/paper_tex.jpg?v=1780997990'`；drawChartBase 改：

```javascript
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
```

CSS：`#topbar.paper-topbar` 与 `.msg`/`.order-note` 的纸底 URL 换 `/static/assets/textures/paper_tex.jpg`（`background-repeat: repeat`；SVG 保留为回退注释）。
- [ ] 转绿 + 无头 Chrome 目检（海图/顶栏/军令卡三处纸纹一致）+ Commit `feat: AI 旧纸纹理接入（Canvas 平铺+CSS）`；**派评审**。

### Task B2: 木纹接入木尺（data-URI 内嵌）

**Files:** Create: `docs/assets/embed_wood.py`、`static/assets/ui/ruler_wood.svg`；Modify: `static/index.html`（道具 img 换 ruler_wood.svg + 缓存号）

- [ ] **红测**：`assert "data:image/png;base64" in (BASE/"static/assets/ui/ruler_wood.svg").read_text()`。
- [ ] 实现内嵌脚本（完整）：

```python
#!/usr/bin/env python3
"""木纹 data-URI 内嵌进 ruler 副本（<img> 引用的 SVG 禁外部资源，必须内嵌）。
产物 ruler_wood.svg；原 ruler.svg 保留为回退。
"""
import base64
from pathlib import Path

SRC = Path("static/assets/textures/wood_tex.png")
TPL = Path("static/assets/ui/ruler.svg")
OUT = Path("static/assets/ui/ruler_wood.svg")

b64 = base64.b64encode(SRC.read_bytes()).decode()
svg = TPL.read_text()
pattern = (
    '<pattern id="woodTex" width="600" height="44" patternUnits="userSpaceOnUse">'
    f'<image href="data:image/png;base64,{b64}" width="600" height="44" preserveAspectRatio="xMidYMid slice"/>'
    '</pattern>'
)
svg = svg.replace('<linearGradient id="wood"', f'{pattern}<linearGradient id="wood"')
svg = svg.replace('fill="url(#wood)"', 'fill="url(#woodTex)"')
OUT.write_text(svg)
print(f"{OUT} written ({OUT.stat().st_size // 1024}KB)")
```

- [ ] 运行 + index.html 道具 img 指向 `ruler_wood.svg` + 缓存号递增 → 转绿 → 目检（刻度/数字在木纹上清晰、无暗边）→ Commit `feat: AI 木纹接入木尺（data-URI 内嵌）`；**派评审**。

### Task B3: 雕刻罗盘接入（亮度反转抠图链）

**Files:** Create: `docs/assets/cut_compass.py`、`static/assets/ui/icons/compass_engraved.png`；Modify: `static/js/svgLoader.js`（ICON_FILES 增条目）、`static/js/chartRenderer.js`（T0 链首位换 engraved）

- [ ] **抠图**（亮度反转保 hatch，避免距离抠图蚀断细线）：

```python
#!/usr/bin/env python3
"""P3 雕刻罗盘白底→透明（亮度反转法，保留细阴线）。"""
from pathlib import Path

import numpy as np
from PIL import Image

im = Image.open(Path(__file__).parent / "ai_textures" / "P3_compass.png").convert("RGB")
a = np.array(im).astype(float)
lum = a.mean(axis=2)
alpha = np.clip((255 - lum) * 1.2, 0, 255).astype(np.uint8)
out = Image.fromarray(np.dstack([np.array(im).astype(np.uint8), alpha]), "RGBA")
out = out.crop(out.getchannel("A").getbbox())
out.save(Path(__file__).parent.parent / "static" / "assets" / "ui" / "icons" / "compass_engraved.png")
print("compass_engraved.png", out.size)
```

- [ ] **质量门**：`quality_gate.py static/assets/ui/icons/compass_engraved.png`——线稿多部件若 G4 FAIL，按 fleet_24/评审先例以「MANUAL 目检裁决」入库（结论记报告）；目检透明度与细线完整。
- [ ] **接入**：ICON_FILES 增 `compass_engraved: '/static/assets/ui/icons/compass_engraved.png'`；T0 的 drawCompassRose 首选改 `getIcon('compass_engraved') || getIcon('compass_raster')`；缓存号递增。
- [ ] 转绿 + 目检（地图右上雕刻罗盘 vs 设计图 A6 并排）+ Commit `feat: AI 雕刻罗盘接入（亮度反转抠图）`；**派评审**。

### 批次 B 收尾评审

- [ ] 全量 pytest + 整页对照（纸/木/罗盘三质感 vs 设计图）+ 验收报告「批次 B」小节 + `raster-icon-review.md` 登记 AI 素材来源/提示词/归一参数。Commit `docs: 批次B验收记录`。

---

## Loop 模式：对照-方案-实施闭环（≥5 轮，4.8h）

> 批次 A+B 验收后自动启动。每轮以**新实拍**为基准，把单轮修复的盲区系统性逼出并消化。

### 总规则

- **轮次下限 5**；某轮零新差距仍须产出「逐项核对表+截图存档」，不得空转略过；连续两轮零差距可提前收敛（默认跑满 5 轮）。
- **对照由控制者亲自执行**（目检不可委派）；实施派子代理，红绿测试随行。
- **回归红线**：每轮 `pytest tests/ -q` 全绿 0 skipped；前轮已修项回退按 S 级处理。
- **预算保护**：S/A 提前清零且总工时 <10h → Loop 加深至 6/7 轮，B 级解禁为可修，直至 10h 下限或清单枯竭（枯竭须核对表证明）。

### 每轮流程

- **L1 实拍**（15min）：
  ```bash
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
    --screenshot=docs/reports/fidelity-loop/loop-N-full-1440.png --window-size=1440,900 \
    --hide-scrollbars --virtual-time-budget=9000 "http://localhost:8000/"
  ```
  同法出 1280×800 与海图/顶栏/侧栏/桌面特写。
- **L2 对照分级**（15min）：15 项映射表 + 整体氛围 + 前轮回归，写入 `loop-N.md`：S（缺失/走样/回退，本轮必修）/ A（可见可接受，本轮修或排下轮）/ B（吹毛求疵，记录不修——防过拟合生成图噪点）。
- **L3 方案**（10min）：每条 S/A 写「文件+改法+预期」；素材需求走决策树 SVG → 库内光栅 → AI 生成（新提示词交控制者，轮次暂停计时）→ 网图（仅 CC0/公有领域）；新素材过对应质量门。
- **L4 实施**（20–30min）：子代理修复 + 控制者逐条目检关闭；S 级未清零不得进下一轮；同一 S 级两轮修不掉 → 登记「已知局限」。
- **L5 存档**（10min）：Fidelity 评分（复刻=1/部分=0.5/偏差=0，**趋势不得下降**）→ loop-N.md 终稿 → 两个 Commit（`fix: 保真度 loop-N 修复（SxAy）` + `docs: loop-N 审查记录`）。

### loop-N.md 模板

```markdown
# Loop N 审查记录（日期）
## 实拍
- 截图：loop-N-full-1440.png / loop-N-full-1280.png / 特写×4
## 差距清单
| # | 级别 | 条目 | 对照证据 | 方案（文件+改法） | 结果 |
|---|------|------|---------|------------------|------|
## 前轮回归检查
- 上一轮已修项逐一复核：…
## 评分
- Fidelity：N.N/15（上轮 N.N；趋势 ↑/→/↓）
## 提交
- <hash> fix / <hash> docs
```

---

## Phase F — 终验（1h）

- [ ] **F1 全分支审查**：`review-package <R0 BASE> HEAD` 派最终审查者（superpowers:requesting-code-review 标准），输入含台账 deferred minors 与 5 轮 Loop 趋势表；产出 findings。
- [ ] **F2 修复波次**：全部 findings 合并为**单个**修复子代理派发 → 唯一一轮范围化复审（ALL-ADDRESSED）→ 残余按裁定 park。
- [ ] **F3 收口**：`ui-replication-report.md` 追加「保真度修正工程汇总」（两批次+5 轮趋势表+工时实绩 vs 核算表）；AGENTS.md 测试基数更新；5 轮 loop 文件与截图随 git 归档。Commit `docs: 保真度修正工程收口`。

---

## 验收总表

| 差距/目标 | 任务 | 阶段 | 门 |
|-----------|------|------|-----|
| 罗盘华丽度 | T0+B3 | A+B | 抠图质量门+目检 |
| 岛体压坐标 / SW 海面斜线 / 沙环立体 | T1 | A | 红绿结构断言+目检 |
| 25nm 环 | T2 | A | 字面量红绿+目检 |
| 引导线箭头 | T3 | A | 红绿+目检 |
| 标签凸起 | T4 | A | 红绿+目检 |
| 纸张做旧 | B0+B1 | B | 纹理门（色温/接缝/尺寸）+目检 |
| 木纹质感 | B0+B2 | B | 纹理门+目检 |
| 整体收敛 | Loop ×5 | Loop | 每轮评分趋势不降；末轮 S=0 |
| 工程质量 | F1–F3 | F | 全分支审查 APPROVE + 残余全裁定 |

## Self-Review 记录

- **覆盖**：7 项差距 + 5 轮收敛 + 终验全映射；每任务带评审环节（执行框架§1–2）。
- **工时保证**：核算表 ≥11.2h（下限 10h）+ 预算保护条款（Loop 加深 + B 级解禁）双保险。
- **占位符扫描**：所有新增脚本/测试/CSS/JS 均完整可运行；Loop 各轮差距条目属执行时数据，模板与命令已给全。
- **依赖一致性**：B3 依赖 B0？否——B3 只依赖 P3 源图；B1 依赖 B0 产物 paper_tex；T0 中间态被 B3 升级；Loop 依赖 A+B；F 依赖 Loop。顺序执行无环。
