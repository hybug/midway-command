# 全库文档冲突审计报告（对照 docs/plans/product-replica-plan.md）

> 审计日期：2026-09-12 · 方式：双 Explore agent 并行通读 18 份文档 + 交叉验证（server.py 端点/缓存号现值/CSS 布局实况/目录存在性）
> 结论：**发现 60+ 项**。其中 4 处硬冲突会直接误导执行者；1 份文档（TECH_ARCH.md）整份过时；其余为过时数字/基准断言/需随计划排期更新的伴生项。

## 一、硬冲突（会直接误导执行者，须先改）

| # | 文件:位置 | 冲突内容 | 与计划哪条冲突 | 处置 |
|---|-----------|---------|----------------|------|
| H1 | docs/README.md:13 | 「GAME_RULES.md = **唯一真相来源**」（该文件不存在） | 与 AGENTS/CLAUDE「GAME_SPEC.md 为 source of truth」互相矛盾 | 改指 GAME_SPEC.md |
| H2 | docs/reports/raster-icon-review.md:52 | button_26 圆规「暂缓；登记为**弃用档**」 | 计划 G5 启用 button_26 分拆产出 compass_brass.png | 该行加注「已由 G5 启用」 |
| H3 | docs/reports/raster-icon-review.md:119 | 「计数牌映射可升级为 ENT/HOR/CV/BB 四牌齐备」 | G1 计数牌退役（地图不再引用） | 加注已过时 |
| H4 | docs/reports/raster-icon-review.md:133 | paper 归一目标色 (245,237,214) | D2 改为 (225,207,168) | 加注「D2 将更新」 |
| H5 | docs/plans/product-replica-plan.md G3（自身勘误） | 敌标「无 ENEMY 字」红方块方案 | 设计审计证实成品图为「红虚线圈+?+ENEMY」 | 已修正（用 enemy_marker.svg）✓ |

## 二、整份过时（标注或重写）

| 文件 | 问题 | 处置建议 |
|------|------|---------|
| **docs/design/TECH_ARCH.md** | 全篇仍描述 **Streamlit 时代**（app.py 入口/无 static/直接执行 handler/pending_suggestions 已废弃/NPC 仅 Browning）——与现役架构（原生 JS + pipeline + 审批流）及计划新增架构（theaters//GET /theater/航海参谋/routes）全面冲突 | 顶部标注「历史存档（已过时）」；重写另立项（建议随 Phase M 落地后重写为现代架构文档） |
| **docs/plans/implementation-plan.md** | 「当前状态：124 个测试全部通过」的现在时断言（实为历史快照，现 273）；其中 Phase 2.3「统一 Position 类」实际未落地 | 顶部加「已完成/历史存档」标注 |

## 三、过时数字与失效引用（指引类，低成本高价值，现在就该改）

| 文件:位置 | 内容 | 处置 |
|-----------|------|------|
| CLAUDE.md:78 | 「Run all tests (**230 collected**)」 | 改「273 passed（随计划增长，以 pytest 实况为准）」 |
| README.md:59 | 「pytest (**101 tests**)」 | 同上 |
| README.md:80-89 | API 端点表缺 /plan-strike、/confirm-strike、/reject-strike、/recall、/confirm-contact；后续还将增 /theater、/routes | 更新端点表 |
| README.md:93-98 | 6 条文档链接指向 docs/ 根（文件已迁 docs/design/、docs/reference/）——**全部失效** | 修正路径 |
| docs/README.md:3,13 | 「最后更新 2026-06-11」；缺 plans//reports//CHART_SYSTEM.md 索引 | 更新索引 |
| AGENTS.md:18,69 | plans 示例指向已完结的 ui-replication-plan.md；视觉基准声明仍指 15 项物料板（已被成品图取代） | 更新为成品图基准 + product-replica-plan.md 指针 |
| docs/plans/ui-fidelity-fix-plan.md | 无「已完成/存档」标注，现在时指令体易被误当当前计划拾起；内含过时快照（缓存号 1780997989、paper 目标色、物料板基准映射表） | 顶部加「已完成·历史存档」声明+指向 product-replica-plan.md |

### 处置记录（终审后修复，2026-09-12）

第三节 7 项已全部处置：

1. CLAUDE.md:78 — 「230 collected」已改「以 pytest 实况为准（当前 285 passed）」。
2. README.md:59 — 「101 tests」已改「285 tests」。
3. README.md 端点表 — 已补 /plan-strike、/confirm-strike、/reject-strike、/recall、/confirm-contact/{index}（按 server.py 实况核对方法与路径）。
4. README.md 文档链接 — 6 条失效链接已改为 docs/design/…、docs/reference/… 实际路径。
5. docs/README.md — 真相来源已改指 GAME_SPEC.md；「最后更新」改 2026-09-12；索引补 plans/、reports/、design/CHART_SYSTEM.md。
6. AGENTS.md — plans 示例改 product-replica-plan.md；Frontend 视觉目标句改成品图基准 + 现行计划指针。
7. docs/plans/ui-fidelity-fix-plan.md — 顶部已加历史存档标注（implementation-plan.md、TECH_ARCH.md 同批处理）。

## 四、需随计划任务同步更新的伴生项（已排期，执行时勿漏）

| 文件 | 冲突项 | 随哪个任务更新 |
|------|--------|----------------|
| docs/design/GAME_SPEC.md:269-274, 280, 438-440, 1122, 1931-1933 | 初始位 31.5°N 176.0°W / TF16→中途岛 211nm / 多处 TC 用例坐标 | M.1/M.4（scenario 驱动后同步） |
| docs/design/GAME_SPEC.md:1823-1830, 1784-1795, 1772-1773, 1782, 395 | §9.5 视觉位置=hex 公式 / §9.2.2 六边形网格+蓝绿敌标 / 舰队位圆心距离环 / GRID_RADIUS 边界 | M.3/M.4（§9 视觉节标注「被成品图取代」+ 事实位更新） |
| docs/design/GAME_SPEC.md:1251, 1317-1345 | ScoutMission.route=hex 坐标列表 | N.1（Route 统一模型时注明 hex 仅内部检测用） |
| docs/design/GAME_SPEC.md:1749 | 「海图参谋系统」（渲染层）与新「航海参谋」NPC（提案层）命名易混 | N.3（加注厘清） |
| docs/design/UI_DESIGN.md | 10 项：48px 顶栏/360px 侧栏/底栏浅色样式/浅纸消息卡/距离环 20-100nm/双线细框/舰队标记形态/按钮态/「❌外部图片」禁令措辞/边缘刻度 | E1/E2/E3/E7/D1/D3/G1 落地时逐项同步 |
| docs/design/ART_DIRECTION.md | 5 项：#f5edd6 主色/舰队标记十字线/仪表带浅字/通信面板浅底/NPC 标签五枚 | D2/E1/E2/N.3 落地时同步 |
| docs/design/GAME_DESIGN_V2.md:74-105, 428 | NPC 名册无航海参谋；关键文件表仍列 app.py Streamlit | N.3（增补航海参谋档案）+ M 批（文件表更新） |
| docs/design/NPC_PROFILES.md | 名册无航海参谋档案 | N.3（新增 Navigator 档案节+自主度表） |
| docs/reference/HISTORICAL_NOTES.md:15 | 史实巡弋位 32°N 175°W vs 游戏初始位（scenario 环礁西 35-55nm）——**史实与构图的真实张力** | M.4（保留史实数字+加注「游戏内初始位由 scenario 驱动」） |
| AGENTS.md:55 | 测试基数 273（将随计划增长） | V3（终验收口时更新） |
| docs/reports/ui-replication-report.md:3,41,69 | 基准声明/已知局限/hack 登记 | P0.1/M.4（已排期） |

## 五、无冲突确认（检查过、干净）

DICE_SYSTEM.md（后端 hex 检定逻辑保留）、COMMAND_TEMPLATE_DESIGN.md（与命令卡方向一致）、approval-engine-plan.md（纯历史存档）、UI_DESIGN.md:139 敌标与 ：142 章位（与成品图一致）、raster-icon-review 质量门判据（G1-G5）。

## 六、处置计划

1. **现在改**（本报告提交后一个任务，~1h）：第三节全部 7 项 + 第二节两处存档标注 + H2/H3/H4 三处加注。
2. **随任务更新**（已写入对应任务书）：第四节 11 项——各批次任务书已含同步指引，执行者按表核对。
3. **待用户拍板**：TECH_ARCH.md 重写时机（建议 Phase M 后）；GAME_SPEC §9 视觉规格「重写 vs 标注取代」（建议标注取代，重写随 Phase M 收口）。
