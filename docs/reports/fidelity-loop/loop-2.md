# Loop 2 审查记录（2026-09-12）

## 实拍
- 截图：loop-2-full-1440.png / loop-2-full-1280.png

## 差距清单（L2 对照分级）

| # | 级别 | 条目 | 对照证据 | 方案（文件+改法） | 结果 |
|---|------|------|---------|------------------|------|
| 1 | A | ENT/HOR 标记重叠残留（16px 错位对 63×64 牌不足，仅露 ENT 上缘） | loop-2-full-1440: HOR 牌上方细条 | mapRenderer _drawOwnFleet：错位改为垂直 28px + 水平 ±14px 对角错开 | |
| 2 | A | SAND ISLAND 文字 53px 溢出 42px 胶囊 | loop-2-full-1440: 文字右侧出框 | chartRenderer drawIslands：字号 8→7px 且胶囊宽按文字实测加宽（measureText 或 ×1.3） | |
| 3 | A | 批次B遗留：test_msg_intel_card_styles 断言空转（.msg 已换 paper_tex） | tests/test_ui_assets.py:145 | 断言目标更新为 paper_tex.jpg + repeat | |
| 4 | B | MIDWAY ATOLL 标题与 HOR 牌轻微重叠 | 数据位置耦合 | 记录不修 | |
| 5 | B | C4 遗留：arcR7 采样依赖绘制顺序 | 测试打磨 | route_display.test.mjs：标记采样绑定 CSE fillText 特征 | |

## 设计评审（设计师 agent，L3）
- DESIGN-SCORE：还原度 8 · 氛围 7 · 层次 8 · 可用性 7 · 构图 7 —— 总分 37/50（Loop 1 33，趋势 ↑+4）
- REGRESSION 回查：竖缝✓ ADVANCE 提权✓ 红章✓ 底栏读数✓ 岛标签「落地但效果不足」（并入本轮 #2）
- 建议（控制者裁定）：#1 [D-A] 标签页 tab_bg 纸舌造型（激活纸色圆角/非激活压暗下沉）→采纳；#2 [D-A] 侧栏空态包 intel_card 纸卡（SECRET 章移卡片右上）→采纳；#3 [D-B→采纳] 底栏标签加深 + 空态 60% 斜体；#4 [D-B→采纳] ≤1360px 断点标签缩字号；#5 [D-S] 经纬网密度加倍 alpha 减半（绘图纸质感）→采纳

## L4 修复清单（本轮实施）

| # | 来源 | 条目 | 改法 |
|---|------|------|------|
| F1 | L2-A1 | 舰队标记错位加大 | _drawOwnFleet：垂直 28px + 水平 ±14px 对角错开 |
| F2 | L2-A2 | 岛标签入胶囊 | drawIslands：字号 7px + 胶囊宽按文字加宽 |
| F3 | L2-A3 | 守卫断言复活 | test_msg_intel_card_styles 断言改 paper_tex.jpg + repeat |
| F4 | 设计#1 | 标签纸舌造型 | .npc-tab 圆角/激活纸色/非激活压暗下沉（对照 tab_bg.svg） |
| F5 | 设计#2 | 空态纸卡 | renderChat 空态包 intel_card_light 卡，SECRET 章移卡右上，宽 88% 居中 |
| F6 | 设计#3 | 底栏层次 | .dash-label 加深趋近 ink；空态值 60% 斜体 |
| F7 | 设计#4 | ≤1360 断点 | 顶栏标签 10px / padding 5px |
| F8 | 设计#5 | 经纬网密度 | 0.5° 步进改 0.25°，alpha 减半 |
| F9 | 缓存号 | 收口递增 | 1780997994→1780997995 + pin 同步 |

## 前轮回归检查
- Loop 1 十项修复复验：竖缝消除✓ 底栏读数✓ ADVANCE 提权✓ 红章✓ 20nm 标注✓ 顶栏色调✓ 沙环投影✓；残留两项即本轮 #1/#2 ✓
- 批次 A 五项 + 批次 B 三质感保持 ✓

## 评分
- Fidelity：13.5/15（持平——无 15 项级变化，本轮目标消化 A 级残差）
- DESIGN-SCORE：37/50（Loop 1 33；趋势 ↑+4）

## 提交
- （待 L6）

## L5 实施结果（2026-09-12）

| # | 条目 | 结果 | 落点 |
|---|------|------|------|
| F1 | 舰队标记对角错开 | ✅ i=0 (x-14, y-28)、i=1 (x+14, y+0)，牌/CSE/引导线整体随动；截图 ENT/HOR 牌完全分离 | mapRenderer.js `_drawOwnFleet`；route_display.test.mjs 锚点同步（F2_LEADER_DX=-14 / DY=-28，CSE 与标记锚点均含 DX） |
| F2 | SAND ISLAND 入胶囊 | ✅ 字号 8→7px + 胶囊宽 `Math.max(rx*0.34, 62)`，截图文字全入框 | chartRenderer.js `drawIslands`（EASTERN ISLAND 维持 8px 不变） |
| F3 | 守卫断言复活 | ✅ 断言收紧钉入 `.msg {` 规则块内：`url('…/paper_tex.jpg') repeat`（不再匹配注释里的 SVG 回退串） | tests/test_ui_assets.py `test_msg_intel_card_styles` |
| F4 | 标签纸舌造型 | ✅ clip-path 切角删除 → `border-radius: 4px 4px 0 0`；非激活 `--color-paper-edge`(#d4c8a8) 压暗 + `translateY(2px)` 下沉；active::before `transform: none` 复位；.npc-tab 字色 → ink-main | style.css Phase 8a 段 |
| F5 | 空态纸卡 | ✅ `div.empty-card` 包 intel_card_light.svg，宽 88% `margin:auto`；`#chat-log:has(.empty-card)` 转 flex 垂直居中；.idle-stamp 改 absolute 右上（top:6px/right:8px） | uiController.js `renderChat` + style.css |
| F6 | 底栏层次 | ✅ .dash-label ink-faint→ink-fade；新增 `_setDashEmpty()` 给空态值（无/暂无）加 `.dash-empty`（opacity .6 + italic） | uiController.js `renderDashboard` + style.css |
| F7 | ≤1360 断点 | ✅（数值修正）设计建议 11→10px/8→5px 系对照 UI_DESIGN 规格基线，实际代码基线已是 10px/4px——照抄会成为无效甚至反向规则，故断点内在基线上再收一档：9px / 8px 3px | style.css 文件尾 `@media (max-width: 1360px)` |
| F8 | 经纬网密度 | ✅ 按裁定：`gridLine` 常量与 0.5° 主网原色不动，新增 `gridLineFaint: 'rgba(160,140,110,0.18)'` 画 0.25° 细网（跳过整半度线、无标注，垫底） | chartRenderer.js `drawLatLonGrid` |
| F9 | 缓存号收口 | ✅ index.html 全量 1780997994→1780997995 + test pin 同步 + svgLoader paper_tex ?v=1780997992→1780997995（svgLoader 在允许清单外，按 F9 条目明示执行） | index.html / svgLoader.js / test_ui_assets.py |

### 验证
- `node --check`：chartRenderer / mapRenderer / uiController / svgLoader 全过
- `node tests/ui/route_display.test.mjs`：ROUTE-DISPLAY PASS（F1 偏移同步后锚点全绿）
- 全量 `pytest tests/`：**273 passed, 0 failed**（含本轮新增守卫 `test_loop2_fidelity_fix_markers` 与 `test_npc_tab_active_lift_enhanced` 锚点修正——文件尾 @media 也含 `.npc-tab {`，rindex 锚点改钉 Phase 8a 块签名）
- 截图：loop-2-after-1440.png / loop-2-after-1280.png（无头 Chrome，服务器 8000）；裁片复核 F1 牌分离、F2 文字入框、F4 纸舌造型、F5 卡片+右上章、1280 标签单行不溢出

### 备注
- 新增守卫测试 `test_loop2_fidelity_fix_markers`（静态断言 F1/F2/F4/F5/F6/F7/F8 关键 token），防回退
- L2 表 #4（MIDWAY ATOLL 标题与 HOR 牌轻微重叠）按裁定记录不修；F1 对角错开后 HOR 牌东移 14px，重叠面进一步缩小
