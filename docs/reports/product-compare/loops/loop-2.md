# Loop 2 审查记录（2026-09-12，基准=成品图 u1fak0）

## 实拍
- fixture：loop-2-fixture-1440.png · 空态：loop-2-empty-1440.png

## 差距清单（L2 对照分级）

| # | 级别 | 条目 | 对照证据 | 方案 | 结果 |
|---|------|------|---------|------------------|------|
| 1 | A | ENT/HOR 圈对位偏差：成品图 ENT 在图左外缘、HOR 在环礁西缘；fixture 两圈挤在环礁中心区 | 双图并排 | design-state.js known 布兵坐标对位（ENT 西外缘 ~52nm/HOR 西缘 ~25nm 反推） | |
| 2 | A | 中心标注群密度（ENT/HOR 圈+CSE+PENDING 章+坐标行四层交叠） | fixture 中心区 | 圈对错位保持+标注群随 F1 对位自然疏散；复核 | |
| 3 | B | 飞机剪影浅（返航 alpha）/环礁圆润/BB 段缺 | 已登记 | 记录 | |

## 设计评审（设计师 agent，L3）
- DESIGN-SCORE：还原度 7.0 · 氛围 8.0 · 层次 7.0 · 可读性 6.5 · 构图 7.5 —— 总分 7.3/10（Loop 1 终评 7.2，趋势 ↑+0.1）
- REGRESSION 回查：八项全部保持（F4 中心碰撞部分——归在办）；F6 细网格「部分」（alpha 0.10 存在感不足）
- 建议（控制者裁定）：#1 [D-A] 纸面暖化（灰褐→暖黄 #e6d5a3 系，全局氛围最大杠杆）→采纳；#2 [D-B→采纳] 扇区方向标签外推+纸色 halo；#3 [D-B→采纳] 细网格 alpha 0.10→0.16；#4 [D-C→采纳] 罗盘压经度标注——标注带避让

## L4 修复清单（本轮实施）

| # | 来源 | 条目 | 改法 |
|---|------|------|------|
| F1 | L2-A1 | ENT/HOR 圈对位成品图 | design-state.js：ENT 移图左外缘（环礁西 ~52nm）、HOR 环礁西缘 ~25nm（保持存储系约定，截图对位） |
| F2 | L2-A2 | 中心标注群减密 | 随 F1 疏散；CSE 标注外推复核 |
| F3 | 设计#1 | 纸面暖黄化 | normalize_texture.py paper 目标 (225,207,168)→(232,214,175)（暖黄方向一半程）；#chart-area::after 覆层色温同步微调；test_texture_assets 目标同步 |
| F4 | 设计#2 | 扇区方向标签外推 | mapRenderer 搜索扇区方向词沿中线外推至开阔水面+纸色 halo（strokeText 或底衬） |
| F5 | 设计#3 | 细网格提存在感 | 细网格 alpha 0.10→0.16 |
| F6 | 设计#4 | 罗盘避让经度标注 | drawLatLonGrid 顶部经度标注带避开罗盘半径（x > w-170 的标注跳过或下移） |
| F7 | 缓存号 | 收口递增 | 1780998006→1780998007 + pin + svgLoader 同步 |

## 前轮回归检查
- Loop 1 九项（F1-F8+缓存）复验：纸签页签✓ 晕影✓ 细网格✓ 扇区退背景✓ ATOLLENT 消除✓ 胶囊文字✓ 罗盘✓ 敌标东北✓
- 批次 D/E/G 全要素保持 ✓

## 评分
- Fidelity/DESIGN-SCORE：待 L3 复评（Loop 1 DESIGN 7.2/10）

## L5 实施结果（2026-09-13）

| # | 状态 | 实施 | 证据/备注 |
|---|------|------|----------|
| F1 | ✅（折中裁定） | design-state.js 舰队对位：**Hornet 升 carriers[0] 作实体层锚点**（钉画布中心，继承原 ENT hex (-4,0)——ox/oy 不变，敌标/侦察机/待定建议屏幕位零漂移），**Enterprise 挂次位 hex (-24,-2)**（lat 27.867/lon −181.939，存储系「北向画在屏幕下方」反推保持）→ ENT 圈画布 (119.5,292.5)，环礁西缘外开阔水面、与 HOR/atoll 近同排 | after-fixture：ENT 图左外缘+贴近缘（页 x≈130/图宽 6.9%）、CSE 270°+双虚线矢量指向环礁，与成品图 ENT 形态一致。**折中说明**：实体层「首航母恒画画布中心」是 known wart（route_display 平移守卫钉住、任务书禁改），数据只能移动次航母——成品图「HOR 环礁西缘」与「ENT 图左外缘」在纯数据途径下不可兼得，按 L2-A1 首要条目保 ENT、HOR 留锚点位（环礁中心东侧），底栏读数经 damage/cap 换位保持「企业:LGT/6 CAP/位置 28.2°N 178.2°W」不变，甲板合计 14 不变（企/蜂展示序对调） |
| F2 | ✅ | 中心疏散：ENT 圈+CSE+矢量随 F1 移出后中心区由四层群降为三层（HOR 圈+CSE+PENDING 章）；chartRenderer.drawTaskForceMarker 增 CSE 读数坐标行文字带避让（带内 +y 外推一行高，形式同既有字标避让） | after-fixture：坐标行 "28°12'N 177°21'W" 完全可读，HOR 的 CSE 270° 移行下方不再压 "…21'W" 尾；route_display CSE 锚点断言不受影响（带外不触发） |
| F3 | ✅ | normalize_texture.py paper 目标 (225,207,168)→(232,214,175) 重生成 paper_tex.jpg（实测均值 231.2/213.3/174.3）；test_texture_assets TEXTURE_TARGETS 同步；#chart-area::after 晕影覆层保持不动（形状/强度不变只调纸底） | 截图像素对照：纸面 open-water patch (199.6,180.0,141.7)→(204.8,185.2,147.0)，+5/通道暖黄提亮 |
| F4 | ✅ | mapRenderer 新增 _drawSectorLabels（实体层，drawLandmarks 之后）：方向词沿扇区中线从弧外 12px 起步步进外推至环礁椭圆外 +48px 缓冲（越过外礁圈带落开阔水面），纸色圆角底衬（rgba(245,237,214,.88)+墨线）+墨字；画缘收编在屏幕系做（本地系 0 是舰队锚点行——首版 bug 已修） | after-fixture："southwest" 纸衬标签落环礁东北海面 (821,167)@canvas，压 hatch/网格仍可读（Loop1 残留「方向标签被陆地遮挡」消除） |
| F5 | ✅ | mapRenderer._drawFineGrid alpha 0.10→0.16 | after-fixture 东/南侧开阔水面细网格可辨不抢主体 |
| F6 | ✅ | chartRenderer.drawLatLonGrid：顶部经度标注 x > w-170（罗盘 150px 右上占位带）跳过，网格线照画 | after-fixture：罗盘下方 "176°30'W" 标注消除，罗盘区干净（Loop1 NEW-ISSUES 消除） |
| F7 | ✅ | 缓存号 1780998007→1780998008 全链：index.html 全部 ?v= + svgLoader paper_tex 同步 + test_ui_assets 断言/历史注释登记 | test_index_html_cache_version_consistent PASS |

**验证**：node --check 四 JS 通过；`node tests/ui/route_display.test.mjs` PASS；全量 pytest 285 passed / 0 failed（test_texture_assets 新目标、缓存号新 pin 均绿）。
**截图**：loop-2-after-fixture-1440.png（设计态 09:45Z）、loop-2-after-empty-1440.png（空态 13:00Z），无头 Chrome 1440×900 实拍并 Read 自查——ENT 左外缘/HOR 锚点位/CSE 不叠字/暖黄纸/扇区标签开阔水面可见/细网格可辨/罗盘区干净全项在位。
**提交**：4 个 commit（F1F2F6 / F4F5 / F3 / F7+存档），未 push。

**残留（Loop 3 候选）**：
- HOR 锚点圈在环礁中心东侧（成品图在环礁西缘）——需实体层「舰队居中平移」改锚（连动 route_display 守卫与 ox/oy 语义），非数据可解，建议 Loop 3 立项修 wart；
- 甲板读数企/蜂展示序对调（蜂 0/0·0 企 14/14·0）——F1 换位副作用，数值合计不变；
- ENT 存储经度 −181.9°（跨 ±180 反推值，渲染/仪表无影响，已知怪味文档化）。
