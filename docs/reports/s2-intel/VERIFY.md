# S2 感知与情报系统 · 执行验证报告（Phase S2.0–S2.8 收口）

> 日期：2026-09-17 · 执行：ZCode 会话（契约：docs/plans/s2-intelligence-system-plan.md）
> 基线：352 passed → 收口：**474 passed**（+9 commits，全部 Conventional Commits）

## 一、逐阶段收口

| Phase | 提交 | 核心交付 | 测试 |
|---|---|---|---|
| S2.0 | 06e048e | contracts（五状态机/权限矩阵/DAG/防泄漏）+ judgment 接口 + 规格文档 | test_intel_contracts 35 |
| S2.1 | b3c0c9b | RNGService+CheckRecord（种子=rng_seed:记录数）、dice 骰源注入、scouting 全量迁移、grid 映射修复、DICE 文档 ×2 修订 | test_intel_rng 16 |
| S2.2 | db08305 | 电文信封/收报室/勘误追加制、证据账本/权限投影、BeliefState/ContactHypothesis、NPCClaim 审计、known_enemy 兼容层 | test_intel_models 17 |
| S2.3 | 5b2c79c | 纵切：观测→观察质检→飞行员 NPC→通信检定→通信官路由→工作项→研判→IntelBrief；/intel API 白名单 | test_intel_flow 10 + test_intel_api 3 |
| S2.4 | b681dcf | PlotProposal/几何/参谋长批注/批准驳回暂缓修订/ApprovedPlot/版本链/玩家敌情=已批准视图 | test_intel_plots 10 |
| S2.5 | dd9b0ec | 证据冲突登记/裁决/印证、接触衰老失联再接触、勘误到达处理、误报否定审批制、主动建议 | test_intel_conflicts 7 |
| S2.6 | 285948b | 瞭望/雷达/声呐/巡逻机传感器档案、友军转述链、同一证据协议无旁路 | test_intel_sources 6 |
| S2.7 | 5c0c07e | 方位线交叉/可能区域/覆盖缺口/冲突提示/依赖反查 + ToolCallRecord 审计与回放 | test_intel_reasoning 10 |
| S2.8 | （本提交） | 情报板 UI（收报室/简报/审图/复盘弹层/敌标 APPROVED 印记/一键反查）+ 纵切 e2e + 截图证据 | test_intel_ui 7 + test_vertical_slice 1 |

## 二、最终纵切（tests/test_vertical_slice.py，用户指定链路全通过）

SBD 发现 → 飞行员电文（人物风格，generated_by_npc 在案）→ 通信检定（transit_eta/LOST/GARBLED）
→ 收报 → 通信官登记路由 → 推理工具调用（possible_area，ToolCallRecord）→ 研判
（JUDGMENT_CHECK+CheckRecord）→ NPCAssessment/NPCClaim → IntelBrief → PlotProposal v1
→ 参谋长批注 → 指挥官批准 → ApprovedPlot active → **正式海图视图=v1**
→ 勘误电文到达（旧电文 CORRECTED、旧证据 SUPERSEDED、CORRECTION 工作项插队）
→ v2 修订提案（批准前海图保持 v1）→ 再批准 → 海图=v2、v1 SUPERSEDED、history 2 条
→ /intel/after-action 因果链完整（证据含 superseded/2 判断/2 决议/工具调用/骰子记录）
→ 同种子回放逐字段一致。

## 三、客观验证门（最终）

```
pytest tests/                       → 474 passed
node tests/ui/route_display.test.mjs → ROUTE-DISPLAY PASS
node tests/ui/geo_render.test.mjs    → GEO-RENDER PASS
python tools/validate_theater.py theaters/midway/     → PASS errors=0
python tools/validate_theater.py theaters/coral-sea/  → PASS errors=0
actual_enemy 泄漏扫描 → test_intel_api（键名+真值递归扫描）+ test_vertical_slice（玩家可见面全量扫描）+ contracts FORBIDDEN_SCOPES 白名单守卫
确定性回放 → test_intel_rng/test_intel_flow/test_intel_reasoning/test_vertical_slice 逐字段断言
```

## 四、截图证据（docs/reports/s2-intel/）

| 文件 | 内容 |
|---|---|
| s2-8-intel-fixture.png | 定妆：审图卡（PENDING 虚线圈+四动作钮+批注）+ APPROVED 印记 + AFTER ACTION 因果链（证据/判断/推测三色语义、批注、决议、工具调用、骰子记录） |
| s2-8-intel-inbox.png | 收报室：原始电文保留 + 勘误关联标记（corrected/routed·勘误） |
| s2-8-intel-brief.png | 判断书：【事实】墨 /【判断】红 /【推测】淡 强区分 + 证据编号 + 未决冲突 |
| s2-8-live-game-load.png | 实况载入完整性（开局层正常，无白屏/无弹层误显） |
| s2-8-live-game-intelboard.png | 实况战局：情报板嵌入右栏（四标签+计数+空态），整体布局无损 |

截图门实绩：抓到并修复 2 个真实缺陷——①intelBoard 独立加载缺 escapeHtml 兜底（fixture 渲染崩溃）；
②`#after-action` display:flex 压过 hidden 属性导致复盘弹层常驻游戏页（已补 `[hidden]` 规则）。

## 五、遗留与风险（移交下阶段）

1. S2.3 前 known_enemy 兼容写入（flow._write_legacy_known_enemy）在真局首图批准后自然失效
   （视图切已批准层），S3 期间可退役该写入。
2. LLM 行为评估（S10：不越权/不冒充/风格一致）尚未建固定场景集——S3 主攻时补。
3. 推理工具未接进 IntelOfficer NPC 的 function-calling 会话（schema 已备：INTEL_TOOLS_SCHEMA），
   S3 判断协议落地时接线。
4. ROUTINE 简报批次合并（D6 例行批次）只做了优先级插队，批次归并未实现（S3 工作队列细化）。
5. 珊瑚海战区未跑 S2 纵切实战验证（逻辑层战区无关；UI 舰名映射已数据面化）。
