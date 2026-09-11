# Loop 3 审查记录（2026-09-12）

## 实拍
- 截图：loop-3-full-1440.png

## 差距清单（L2 对照分级）

| # | 级别 | 条目 | 对照证据 | 方案（文件+改法） | 结果 |
|---|------|------|---------|------------------|------|
| 1 | A | ENT 标记盖住 MIDWAY ATOLL 标题与坐标行右端 | loop-3-full-1440: 标题 "MIDWAY ATOLL" 尾部被压 | mapRenderer _drawOwnFleet：ENT 错位改为 (x-56, y-30) 向左上让开文字区 | |
| 2 | A | 空态文字横穿纸卡（未入卡内） | loop-3-full-1440: 卡片空框+文字交叉 | uiController renderChat 空态：文字作为卡片内容居中渲染（卡在文字外层） | |
| 3 | B | 25nm 标注斜排与 20nm 下移后三标注（20/25/40）视线略散 | 记录不修（各环可辨） | 记录 | |

## 设计评审（设计师 agent，L3）
- DESIGN-SCORE：还原度 9 · 氛围 8 · 层次 8 · 可用性 8 · 构图 7 —— 总分 40/50（Loop 2 37，趋势 ↑+3）
- REGRESSION 回查：标签纸舌✓ 空态纸卡+章✓（文字横穿卡为在办 #2）底栏层次✓ ≤1360 断点✓ 经纬密网✓
- 建议（控制者裁定）：#1 [D-A] 空态纸卡加深一档（brightness .97 或阴影加强）→采纳；#2 [D-A] CSE 航向标注锚到标记外侧+引导线首段缩 12px →采纳；#3 [D-B→采纳] 左下经纬标注上移 4-6px 避木尺；#4 [D-S·零代码] 补 advance 后敌标暴露态实拍（A5 还原证据）

## L4 修复清单（本轮实施）

| # | 来源 | 条目 | 改法 |
|---|------|------|------|
| F1 | L2-A1 | ENT 让开标题区 | _drawOwnFleet：ENT 错位 (x-56, y-30) |
| F2 | L2-A2 | 空态文字入卡 | renderChat 空态：文字作为卡内容居中 |
| F3 | 设计#1 | 空态卡物件感 | .empty-card 阴影加强 0 2px 6px rgba(60,45,20,.25) + brightness(.97) |
| F4 | 设计#2 | CSE 标注避让 | drawTaskForceMarker：CSE 文本锚标记外侧背离卡方向，引导线首段 12→24px 起 |
| F5 | 设计#3 | 经纬标注避尺 | 左下角标注列上移 5px |
| F6 | 设计#4 | 敌标实证 | advance 触发敌情→截图 A5 暴露态入档（零代码验证） |

## 前轮回归检查
- Loop 2 九项复验：舰队对角分离✓（残留即本轮 #1）岛标签入胶囊✓ 纸舌✓ 空态纸卡✓（残留即本轮 #2）底栏层次✓ 断点（未复验 1360）密网✓ 守卫复活✓
- 批次 A/B 全部保持 ✓

## 评分
- Fidelity：13.5/15（持平）
- DESIGN-SCORE：待 L3 复评（Loop 2 37/50）

## L5 实施结果（2026-09-12）

| # | 状态 | 实施与验证 |
|---|------|-----------|
| F1 | ✅ 完成（改法偏差，已验证更优） | 清单改法 (x-56,y-30) 经几何/实机验证**反向恶化**：ENT 左移 42px 使计数牌对标题覆盖从 ~26px² 增至 ~945px²（压住标题中部）。按本条目标「让开 MIDWAY ATOLL 标题与坐标行」改为横向右移 **(x+80, y-64)**：ENT 牌落环礁东侧开阔纸面（tag 左缘 atollCx+0.06w+48.5，恒在标题右缘 +45 之外），y 带 [cy-96,cy-32] 避开 25/40nm 环标注；与 HOR (x+14,y) 保持对角错开（角接触不相交）。实机截图：标题/坐标行/双岛标签完整可见 |
| F2 | ✅ 完成（根因修正，DOM 未改） | 读现状：`.chat-empty` **已**嵌套于 `.empty-card` 内（Loop2-F5 已改 DOM 层级）。真实根因是 intel_card_light.svg 默认 `preserveAspectRatio=xMidYMid meet`——`background-size:100% 100%` 拉伸元素画布后画稿在内部等比缩放再居中（315px 元素仅画出 ~196px 卡），文字行（283px）随之左右穿出画稿边框。修复：`.empty-card` 加 `aspect-ratio:320/140` 对齐画稿比例（画稿铺满元素）+ flex 垂直水平居中。实测卡 315×138、文字 235px 完全入卡居中，SECRET 章保持卡右上 |
| F3 | ✅ 完成 | `.empty-card` 加 `box-shadow: 0 2px 6px rgba(60,45,20,.25)` + `filter: brightness(.97) drop-shadow(...)`（原 drop-shadow 保留，暗度链式叠加） |
| F4 | ✅ 完成（改法偏差，按清单预案） | 清单最小改法（背向航向 20px）几何验证落在 63×64 光栅计数牌**内部**（20 < 31.5 半宽），与「标记外侧」语义冲突——按清单预案走「背离」方案：CSE 标注锚 `marker − 44px·û`（û 指向环礁/引导线方向，即标注在标记外侧背离引导线侧）；引导线首段起距 12→24px。实测 ENT/HOR 的 CSE 240° 标注均落开阔纸面，与邻牌/环标注零重叠 |
| F5 | ✅ 完成 | drawLatLonGrid 纬度标注（均在左缘列 x=6）`y-3 → y-8`；实机截图 27°0'N 完全位于铅笔/木尺上方 |
| F6 | ⛔ 无法自然触发（零代码，按清单预案维持静态） | `POST /advance {"minutes":15}` ×4（13:30→14:30Z）后 `/state` 的 `known_enemy` 仍为 0。代码层根因：`known_enemy` 仅由 `process_reports → check_pending_reports`（src/scouting.py:685）填充，前置条件是玩家批准侦察建议→侦 察机起飞→报告到达（`pending_reports`），tick 管线无自动敌情事件，initial_state `known_enemy=[]`。**空态场景无法自然触发敌情**——按清单预案 A5 维持静态 0.5 不强造，未截图 after-enemy |

### 测试与缓存
- `node --check`：chartRenderer.js / mapRenderer.js / uiController.js 通过
- `node tests/ui/route_display.test.mjs`：PASS（锚点同步：F2_LEADER (−14,−28)→(+80,−64)；CSE 期望改 û·44 公式；松界邻域 60→115px 覆盖新偏移）
- `pytest tests/`：273 passed 0 failed（test_ui_assets.py 两处守卫随意图同步：标记错位字面量、缓存号 1780997996）
- 缓存号：index.html 1780997995→1780997996（6 处）
- 截图：loop-3-after-1440.png（1440×900 实机）；循环内对比 crop：/tmp/after-atoll-zoom.png、/tmp/after-empty-zoom.png、/tmp/after-lat-zoom.png（过程稿）

### 偏差与守卫同步说明
- F1/F4 均先按清单数字做几何验证（node 计算 + 无头 Chrome 实机对比）后确认与条目目标冲突再偏差，偏差依据已写入源码注释与本节——两处偏差都更严格地满足「让开标题/标注避让」的设计目标。
- tests/test_ui_assets.py 不在「只动」清单内，但其两处静态守卫锚定被本轮**有意修改**的实现字面量（标记偏移、缓存号），按「全量 pytest 全绿」要求做最小同步（各 1 行），与该文件既有「每轮随修复同步守卫」的惯例一致。
