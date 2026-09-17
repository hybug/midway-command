# S2 感知与情报系统规格（S2_INTEL_SYSTEM）

> 状态：**现行规格**（Phase S2.0 产出，随实施阶段同步更新）
> 创建日期：2026-09-17
> 上级计划：`docs/plans/s2-intelligence-system-plan.md`（执行契约）
> 长期路线图：`docs/plans/gameplay-system-roadmap.md`
> 代码锚点：`src/intel/`（contracts / judgment / rng / models / …）

---

## 一、目的与边界

本规格固定 S2 的数据边界、命名、状态机、权限矩阵与防泄漏规范。S2 负责
「各方能知道什么、何时知道、依据是什么，以及情报如何被传播和污染」；
不负责世界真相推进、NPC 性格维度定稿、作战命令执行、战斗结算与胜负。

统一数据链（§四）：

```text
ActualWorld → SourceObservation → FiledMessage → ReceivedMessage → Evidence
  → IntelWorkItem → NPCAssessment → NPCClaim / IntelBrief → PlotProposal
  → CommanderDecision → ApprovedPlot → Chart
```

### 1.1 对象谱系表（每个对象都能回答"谁在何时基于什么产生了它"）

| 对象 | 产生者 | 产生时机 | 基于什么 | 载体 |
|---|---|---|---|---|
| SourceObservation | 规则侧（scouting 引擎） | 空间相遇 + DETECTION_CHECK 通过后 | actual_enemy 真值 + 观察者位置/能力 + OBSERVATION_QUALITY_CHECK | `observations`（规则侧，永不序列化给玩家/NPC） |
| FiledMessage | 报告 NPC（飞行员等 LLM） | 观测后按人物风格撰写 | 可见观测值（失真后），非真值 | `messages` |
| ReceivedMessage | 通信链（COMMUNICATION_CHECK） | 延迟到达旗舰时 | FiledMessage + 传输检定结果 | `messages`（同档，状态区分） |
| Evidence | 收报登记（系统规则侧） | ReceivedMessage 登记时 | 电文内容 + 来源可靠性 | `evidence` |
| IntelWorkItem | 通信官路由 / 指挥官要求 | 登记转递时 | Evidence | `intel_work_items` |
| NPCAssessment / NPCClaim | 情报参谋（LLM + JudgmentPolicy） | 参谋实际处理工作项时 | 权限内 EvidenceView + 工具调用 + JUDGMENT_CHECK | `assessments` |
| IntelBrief | 情报参谋 | 判断形成后 | NPCAssessment 集合 | `intel_briefs` |
| PlotProposal | 情报参谋 | 简报需上图时 | 证据几何 + Assessment | `plot_proposals` |
| 参谋长批注 | 参谋长（LLM） | 呈报前 | IntelBrief + PlotProposal | brief 注记字段（追加式） |
| CommanderDecision | 指挥官（玩家操作） | 审阅后 | 已呈报简报/提案 | decision 字段（追加式） |
| ApprovedPlot | 审批服务（规则侧） | 指挥官批准时 | PlotProposal（只读复制） | `approved_plots` |
| Chart 图层 | mapRenderer | 每帧 | ApprovedPlot（唯一输入） | 前端 |

### 1.2 强制约束（与计划 §四一致）

1. `SourceObservation` 及其 `internal_truth_ref` 只存在于规则侧，永不进入 NPC prompt、
   NPC 工具返回、玩家 API。
2. NPC 只能读取经过权限转换的 `EvidenceView`（`src/intel/judgment.py`）。
3. 玩家接口只下发收报档案、公开判断、已批准标图和工作队列（`PLAYER_VISIBLE_SCOPES`）。
4. 原始消息、判断、标图版本一律不可原地覆盖；勘误/修订/否定均为追加记录。
5. 任何派生认识引用产生它的 NPC 与工具调用（可审计）。
6. `actual_enemy` 不进入报告生成、情报工具、NPC prompt 或玩家 API。

---

## 二、状态机（代码：`src/intel/contracts.py`，测试：`tests/test_intel_contracts.py`）

### 2.1 消息（MessageStatus）

```text
DRAFT → FILED → IN_TRANSIT → RECEIVED → LOGGED → ROUTED → PROCESSED → ARCHIVED
                    ↘ LOST                        （RECEIVED 起）任何状态 ⇢ CORRECTED
```

- 玩家可读起点：RECEIVED。LOST 的内容永不泄露。
- CORRECTED 为追加状态：原电文保留原文，勘误以新电文引用旧电文（`supersedes_message_id`）。

### 2.2 通信完整性（CommCondition）

COMPLETE / PARTIAL / GARBLED / UNREADABLE / DUPLICATE / CORRECTED

### 2.3 证据（EvidenceStatus）

ACTIVE → CORRECTED | SUPERSEDED | REJECTED（均为终态，原记录保留）

### 2.4 接触（ContactStatus）

```text
BEARING_ONLY → TENTATIVE → PLOTTED → STALE ⇢（重新接触）TENTATIVE/PLOTTED
任何未否定状态 ⇢ REJECTED（误报否定，终态）
任何状态 ⇢ SUPERSEDED → ARCHIVED
```

### 2.5 工作项（WorkItemStatus）

```text
QUEUED → ASSIGNED → IN_PROGRESS → SUBMITTED → ACKNOWLEDGED → CLOSED
                       ↕ WAITING_FOR_EVIDENCE
（FLASH 打断例行工作；ROUTINE 可合并定期简报）
```

### 2.6 审批（ApprovalStatus，简报与标图共用）

```text
DRAFT → PROPOSED → APPROVED → SUPERSEDED（唯一去向）
                  ⇢ REVISION_REQUESTED → PROPOSED（修订重报）
                  ⇢ PARTIALLY_APPROVED → APPROVED / …
                  ⇢ DEFERRED → PROPOSED | REJECTED
```

批准不等于确认事实，只表示正式采纳当前判断；已批准标图不可覆盖（D13/D14）。

---

## 三、权限矩阵

### 3.1 （角色, 可见域）白名单

| 角色 | 可见域 |
|---|---|
| PLAYER | inbox, briefs_submitted, approved_plots, work_queue |
| COMMS_OFFICER | inbox, transit |
| INTEL_OFFICER | evidence_scoped, inbox, work_queue, approved_plots |
| CHIEF_OF_STAFF | briefs_all, inbox, approved_plots, fleet_global, work_queue |
| CAPTAIN | own_carrier |
| NAVIGATOR | fleet_global |
| FRIENDLY_FORCE | own_force |

### 3.2 全角色禁读域（FORBIDDEN_SCOPES）

`actual_enemy`、`internal_truth_ref`、`unreceived_messages`——任何角色（含玩家 API、
LLM prompt、工具返回）都不得读取。

### 3.3 玩家 API 允许下发域（PLAYER_VISIBLE_SCOPES）

`inbox`、`briefs_submitted`、`approved_plots`、`work_queue`。

### 3.4 actual_enemy 防泄漏规范

1. **结构性防泄漏优先**：玩家 API（server.py）手写序列化白名单字段，不做
   `GameState.model_dump()` 直发；观测真值只存规则侧容器，不进公开模型字段。
2. **证据投影**：NPC 读取一律经 `EvidenceView` 装配，装配函数不接触 actual_enemy。
3. **自动扫描**：全量测试含泄漏扫描——对玩家/NPC 可见序列化结果递归检索键名与
   关键字段（`actual_enemy`、`internal_truth_ref`、未送达电文 `raw_text`）。
4. **LLM 行为评估**（S10）：固定场景检查 NPC 不读取 actual_enemy、不冒充他人发报。
5. 职责边界：通信官只登记转递不分析敌情；情报参谋只在权限内研判；作战参谋只在
   指挥官决心后编制方案；航海参谋不生成敌情。

---

## 四、S3 JudgmentPolicy 接口（`src/intel/judgment.py`）

```python
class JudgmentPolicy(Protocol):
    def assess(self, work_item, evidence: Sequence[EvidenceView],
               actor: ActorProfile, dice: JudgmentDice) -> AssessmentDraft: ...
```

- 输入：工作项 + 权限内 `EvidenceView` 序列 + `ActorProfile`（开放属性集）+
  `JudgmentDice`（骰子结构化输出：五级结果、错误方向、严重度、表达确定性）。
- 输出：`AssessmentDraft`（claims / confidence_dimensions（开放多维 dict，D8）/
  alternative_hypotheses / change_my_mind / recommended_action）。
- **不锁定维度数量与公式（D20）**：维度集合与错误公式由 S3 经公式、消融、历史校准定稿。
- 骰子由系统掷，NPC 只解释不重算（D10）；无 NPC 工具调用不得产生判断（D12/D15）。

---

## 五、骰子系统缺口审计（Phase S2.1 任务清单）

| # | 缺口（现状，已核代码） | 处理 | 阶段 |
|---|---|---|---|
| 1 | `src/dice.py` 用全局 `random`，无种子无记录 | RNGService + CheckRecord 落 state | S2.1 |
| 2 | `src/scouting.py` `distort_bearing/distort_distance/distort_count/compute_report_delay` 与损失概率直调 `random` | 迁移到 RNGService（检定或记录型抽取） | S2.1 |
| 3 | 侦察检定固定用 `NPC_REGISTRY["browning"]` 能力，非实际执行单位 | 用执行单位（中队/飞行员）能力参数 | S2.1 |
| 4 | `tools.py launch_scout`：`SearchPattern("grid")` 非法值会抛 ValueError；`SearchPattern.GRID` 成员不存在会抛 AttributeError | "grid" 映射到 EXPANDING_SQUARE，与 §6.2.1 一致 | S2.1 |
| 5 | `docs/design/DICE_SYSTEM.md` competence ×25 与代码 ×2 不一致 | 以代码（§7.3 ×2）为准修订文档 | S2.1 |
| 6 | 报告延迟抖动 `random.randint(-5,10)` 未记录 | 纳入 CheckRecord effects | S2.1 |
| 7 | `PendingReport.confidence` 单字符串 | 多维置信度（S2.2+ 模型），旧字段兼容保留 | S2.2 |

回放要求：同一局面 + 同一种子 ⇒ 相同检定序列（CheckRecord 可重放，不依赖全局随机态）。

---

## 六、D1–D20 追溯表

| 原则 | 规格落点 |
|---|---|
| D1 玩家只读送达材料 | §3.3 PLAYER_VISIBLE_SCOPES；消息状态机 RECEIVED 起点 |
| D2 电文/简报/标图是不同对象 | §1.1 谱系表；models 分模型 |
| D3 通信/情报/作战职责 | §3.5 职责边界；NPC prompt 与工具白名单 |
| D4 原始记录不可覆盖 | 消息/证据状态机追加制；勘误电文引用链 |
| D5 档案全局、知识按角色隔离 | Evidence 账本 + BeliefState（S2.2） |
| D6 紧急即报、例行批次 | WorkPriority FLASH/ROUTINE 分流（S2.3 起） |
| D7 工具提供几何，判断由参谋形成 | M2.7 工具只出候选关系；S2.7 |
| D8 置信度多维 | AssessmentDraft.confidence_dimensions 开放 dict |
| D9 接触是假设 | ContactStatus 竞争并存；ApprovedPlot 是"采纳的认识" |
| D10 骰子产生失真，LLM 演绎 | JudgmentDice 结构化输出；RNGService |
| D11 时间链 | observed_at/filed_at/received_at/briefed_at（models） |
| D12/D15 判断必须经 NPC 工具/工作项 | 工作项状态机 SUBMITTED 前置校验（S2.3） |
| D13 正式海图只显示 ApprovedPlot | mapRenderer 正式层唯一输入（S2.4） |
| D14 已批准标图不可覆盖 | APPROVED → SUPERSEDED 唯一去向；新版再审批 |
| D16/D17 报告人物化、可推测不可越权 | 报告 NPC（S2.3）；权限矩阵 + 行为评估 |
| D18 来源限定 | SourceType 六类 |
| D19 主纵切=舰载侦察机 | S2.3 纵切 |
| D20 维度/公式归 S3 | §四 JudgmentPolicy 接口 |

---

## 七、测试规范（最低集）

- 契约：`tests/test_intel_contracts.py`（枚举/状态机/DAG/权限/泄漏/JudgmentPolicy）。
- 每个 Phase 红灯先行：先写失败测试再实现；阶段收口跑全量 pytest + 静态守卫。
- 泄漏扫描：对 `/state`、`/intel/*` 响应与 NPC 可见装配递归断言无禁读键。
- 回放：同种子两次执行 CheckRecord 序列逐字段一致。

---

## 八、实施阶段对照（计划 §十三）

| Phase | 内容 | 状态 |
|---|---|---|
| S2.0 | 规格与基础契约 | ✅ 本文件 + src/intel/contracts.py + judgment.py |
| S2.1 | 骰子与可复现随机性 | ✅ src/intel/rng.py（RNGService/CheckRecord） |
| S2.2 | 电文、证据与角色信念 | ✅ src/intel/models.py + service.py |
| S2.3 | 舰载侦察机纵切 | ✅ src/intel/flow.py + agents/pilot.py + intel_analyst.py |
| S2.4 | 作战标图审批 | ✅ src/intel/plots.py |
| S2.5 | 冲突、陈旧与勘误 | ✅ src/intel/conflicts.py |
| S2.6 | 舰艇接触与友军电报 | ✅ src/intel/sources.py |
| S2.7 | 推理工具与不确定度 | ✅ src/intel/reasoning.py |
| S2.8 | 界面收口与复盘 | ✅ static/js/intelBoard.js + /intel/after-action + 定妆/实况截图 |

收口验证：474+ passed；纵切 e2e（tests/test_vertical_slice.py）含修订/回放/泄漏扫描；
证据：docs/reports/s2-intel/（VERIFY.md + 5 截图）。
