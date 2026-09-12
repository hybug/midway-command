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
