# Loop 1 审查记录（2026-09-12，基准=成品图 u1fak0）

## 实拍
- fixture：loop-1-fixture-1440.png（设计态 09:45Z）
- 空态：loop-1-empty-1440.png
- 对照基准：docs/assets/Gemini_Generated_Image_u1fak0u1fak0u1fa.png

## 差距清单（L2 对照分级）

| # | 级别 | 条目 | 对照证据 | 方案（文件+改法） | 结果 |
|---|------|------|---------|------------------|------|
| 1 | A | SAND ISLAND 胶囊文字回归消失（近景放大后胶囊/字体度量失配，胶囊内无字） | loop-1-fixture: 空白胶囊 | drawIslands：字号与胶囊宽按近景尺度重算（measureText 定宽） | |
| 2 | A | 敌标位偏正北，成品图在环礁东北偏内 | 双图并排 | design-state.js known_enemy 坐标微调至成品图位（东北 ~10nm/环礁外缘） | |
| 3 | A | 罗盘偏小偏素 | fixture 右上 vs 成品图右下大罗盘 | drawCompassRose 绘制尺寸 110→150px 并右移对位（icon 为雕刻版够华丽） | |
| 4 | B | 飞机剪影色浅（返航 alpha 0.55）且位于西北（成品图两架深色剪影在 HOR 东侧航线上） | 数据态不同+alpha | 记录（数据驱动；alpha 为返航语义） | |
| 5 | B | 环礁形态偏圆润（成品图更不规则、东北开口更大） | 双图并排 | 记录（真实地理立场已定，wob 参数不动） | |
| 6 | B | 底栏敌情 BB 段缺（数据端无战列舰数） | 已登记 | 记录 | |
| 7 | B | ENT 圈内 CSE 叠坐标行尾部（几何临界） | 已登记 GA | 记录（Loop 微调候选） | |

## 设计评审（设计师 agent，L3）
- DESIGN-SCORE：还原度 6.5 · 氛围 7.5 · 层次 6.5 · 可读性 5.5 · 构图 7 —— 总分 6.6/10（加权）
- REGRESSION：首评
- 建议（控制者裁定）：#1 [D-S] 地图中心标注碰撞（ENT 圈压 ATOLL 尾/坐标×CSE 叠字）→采纳；#2 [D-A] 搜索扇区压焦点（降 alpha+改绘制顺序）→采纳；#3 [D-A] 补 10nm 细网格（survey 感）→采纳；#4 [D-A] 页签回归纸签隐喻（米色纸底深字，推翻 E3 深色胶囊——成品图基准优先）→采纳；#5 [D-B] 纸面内阴影桌感→采纳（零依赖）

## L4 修复清单（本轮实施）

| # | 来源 | 条目 | 改法 |
|---|------|------|------|
| F1 | L2-A1 | SAND ISLAND 胶囊文字回归消失 | drawIslands：measureText 定宽重算胶囊 |
| F2 | L2-A2 | 敌标位对齐成品图东北 | design-state.js known_enemy 坐标微调 |
| F3 | L2-A3 | 罗盘放大对位 | drawCompassRose 110→150px 右移 |
| F4 | 设计#1 | 中心标注群碰撞 | MIDWAY ATOLL 锚点左上偏移；ENT/HOR 字标圈右下统一+矩形避让；CSE 沿航线外推 |
| F5 | 设计#2 | 搜索扇区退背景 | hatch alpha 减半+绘制顺序移到陆地填充前 |
| F6 | 设计#3 | 补 10nm 细网格 | mapRenderer 纸面层 rgba(90,70,40,0.10) 1px 网格 |
| F7 | 设计#4 | 页签回归纸签 | 未激活米色纸底(#e8dcc3 近似)+深棕字，激活加粗描边/加高（伪元素架构保留） |
| F8 | 设计#5 | 纸面内阴影 | #chart-area inset box-shadow 12px rgba(42,34,24,0.18) |
| F9 | 缓存号 | 收口递增 | 1780998005→1780998006 + pin + svgLoader 同步 |

## 前轮回归检查
- 批次 D/E/G/H 全要素复验（近景/深框/hatch/深 chrome/命令卡/圆圈标记/剪影/敌标/章/圆规）——fixture 截图全部在位 ✓

## 评分
- Fidelity（成品图 15 项新映射表）：待 L3 设计师复评后定分（首评）
- DESIGN-SCORE：待 L3

## 提交
- （待 L6）

## L5 实施结果（2026-09-13）

| # | 状态 | 实施 | 证据/备注 |
|---|------|------|----------|
| F1 | ✅ | drawIslands：SAND ISLAND 胶囊 10px 字号 + measureText 定宽（文本宽+16，下限 62px）、16px 定高，文字水平/垂直居中；跑道横带随 sandH 联动 | after-fixture 截图胶囊内有字；test_loop2 守卫同步为 `Math.max(sandLblW + 16, 62)` |
| F2 | ✅ | design-state.js known_enemy 微调：内标 hex (9,-11)→画布 (875.9,252)≈56°/23.8nm（礁环内缘）、外标 hex (10,-17)→(834.3,144)≈37°/27.5nm（礁环外缘），保持「北向画在屏幕下方」存储系约定 | after-fixture：两枚红?标环礁东北、内外错开 |
| F3 | ✅ | drawCompassRose：110→150px，x=w-170 右移贴缘；罗盘中心 (1345,95) 与 40/60nm 标注带（y≈410）错开 | after-fixture 右上大罗盘 |
| F4 | ✅ | MIDWAY ATOLL/坐标行锚点偏移 (-48,-16)；ENT/HOR 字标统一圈右下 (tf.x+14, tf.y+20) + 与坐标行 ≥20px 检查（不足下移一行高）；矢量虚线/箭头钳制环礁心前（dashEnd/arrowBase = min(固定值, len-18/-12)），修近景箭头过冲压坐标行 | ATOLLENT 合并消除（before/after 对比）；坐标行 "28°12'N 177°21'W" 完全可读 |
| F5 | ✅ | ChartRenderer 拆 drawBase（纸底+经纬网）/drawLandmarks（环礁+环+罗盘+尺+章），mapRenderer.render 改三段式：底图→扇区→地标→实体；hatch alpha 0.12→0.06 减半。_drawPendingRecon midAngle 修复未回退 | 扇区被陆地覆盖不压焦点（NE 灰 hatch 消失）；**回归追补**：重构时漏掉的实体层 translate 已恢复并加 route_display 守卫（变异验证有效） |
| F6 | ✅ | mapRenderer._drawFineGrid：1px rgba(90,70,40,0.10) 10nm 间隔网格，间距经 ChartRenderer.chartNmToPx 换算，锚定环礁心（0.44w/0.46h 与距离环同轴）；绘制位=纹理后、距离环前 | after-fixture 东侧开阔水面细网格可见（间距≈105px 实测吻合），环礁/泻湖下方被覆盖 |
| F7 | ✅ | .npc-tab 族：未激活 ::before #2b2118→#e8dcc3 米色纸签 + 基础字色 bar-text→ink-main 深棕墨字（伪元素架构 isolation 保留）；激活 padding-bottom:6px 加高 + 底边无缝连面板（-6px 上浮保留） | after-fixture/after-empty：整排米色纸签、激活 COS 亮纸签连面板；test_npc_tab_active_lift_enhanced 同步（#e8dcc3 登记入守卫） |
| F8 | ✅ | #chart-area box-shadow 加 `inset 0 0 12px rgba(42,34,24,0.18)`（替换原 0.03 弱 inset） | after 双图图缘暗角呈桌面纸感 |
| F9 | ✅ | 缓存号 1780998005→1780998006：index.html 全部 ?v= + svgLoader paper_tex 同步 + test_ui_assets 断言/历史注释登记 | test_index_html_cache_version_consistent PASS |

**验证**：node --check 四个 JS 通过；`node tests/ui/route_display.test.mjs` PASS（F4 锚点期望值核对无需变更——CSE/标记锚点未动，新增实体层 translate 守卫）；全量 pytest 285 passed / 0 failed。
**截图**：loop-1-after-fixture-1440.png（设计态 09:45Z）、loop-1-after-empty-1440.png（空态 13:00Z），无头 Chrome 1440×900 实拍并 Read 自查（ATOLLENT 消除/扇区不压焦点/细网格/纸签/内阴影全项在位）。
**提交**：6 个 commit（F1F3F4 / F2 / F5F6 / F7F8 / F4F5 回归追补 / F9+存档），未 push。

**残留（Loop 2 候选）**：
- 空态初始位（舰队在环礁正西同纬）下 HOR 矢量箭头尖距坐标行尾 ~2px 擦边——数据相关几何，fixture 基准位无此问题；
- ENT 的 CSE 270° 读数仍被本舰航向线尾段穿过（G1 既有形态，非本轮改动引入）；
- 搜索扇区方向标签（southwest 等）随扇区退背景后被陆地遮挡，开放水面扇区可见性待设计裁定。
