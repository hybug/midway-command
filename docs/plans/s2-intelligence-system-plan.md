# S2 感知与情报系统实施计划（s2-intelligence-system-plan）

> 状态：**现行专项实施计划（执行中）**
> 创建日期：2026-09-14
> 上级路线图：`docs/plans/gameplay-system-roadmap.md`
> 当前阶段：S2 感知与情报系统
> 产品形态：单场战役、60–120 分钟、强重玩、完整战后归因
> 执行规格：`docs/design/S2_INTEL_SYSTEM.md`（Phase S2.0 产出）

## 执行记录（各阶段收口时追加）

| Phase | 状态 | 收口摘要 |
|---|---|---|
| S2.0 | ✅ 完成（2026-09-17） | `src/intel/contracts.py`（五状态机+权限矩阵+数据流DAG+防泄漏规范）、`src/intel/judgment.py`（JudgmentPolicy 接口草案，不锁维度）、`docs/design/S2_INTEL_SYSTEM.md`（对象谱系/D1–D20 追溯/骰子缺口审计 7 项）、`tests/test_intel_contracts.py` 35 测试；全量 387 passed |
| S2.1 | ✅ 完成（2026-09-17） | `src/intel/rng.py`（RNGService+CheckRecord，种子=rng_seed:记录数）、GameState 增 rng_seed/check_records、dice.roll_check 支持注入骰源、scouting 管线全部随机迁移落记录（检定用执行单位 SBD 侦察中队 competence=6）、tools.py grid→expanding_square 映射修复、DICE_SYSTEM.md competence ×2 修订；tests/test_intel_rng.py 16 测试 + 旧种子循环测试改 state.rng_seed；全量 403 passed，回放测试逐字段一致 |
| S2.2 | ✅ 完成（2026-09-17） | `src/intel/models.py`（MessageEnvelope/Evidence/ContactHypothesis/BeliefState/NPCClaim/IntelAuditEntry/StatusChange）、`src/intel/service.py`（消息状态机推进+收报室/勘误追加制/证据登记替代否定/时间链校验/权限投影 evidence_view/信念隔离/接触转换 PLOTTED 需批准/候选关联不合并/claim 审计/known_enemy 兼容层）；GameState 增 messages/evidence/claims/contacts/beliefs/intel_audit/intel_id_counters；tests/test_intel_models.py 17 测试；全量 420 passed |

---

## 一、S2 的最终效果

玩家作为航母特混舰队指挥官，只能看到旗舰真正收到的信息：

```text
原始电文
    ↓
情报参谋整理后的书面判断
    ↓
参谋长筛选、批注与呈报
    ↓
指挥官讨论、修订和批准
    ↓
经批准的作战标图进入正式海图
```

玩家不能看到系统融合后的唯一答案，不能查询内部证据账本，也不能通过任何 NPC 读取 `actual_enemy`。

正式海图表示的是：

> 指挥官在不同时间正式采纳过的作战认识。

它不是战场事实的实时投影。

---

## 二、已经确认的设计原则

| 编号 | 原则 |
|---|---|
| D1 | 玩家是旗舰指挥官，不是系统管理员；只能阅读真正送达旗舰的材料 |
| D2 | 原始电文、情报简报和作战标图是不同对象 |
| D3 | 通信官负责收报与转递；情报参谋负责分析研判；作战参谋负责决心后的行动方案 |
| D4 | 原始记录不可覆盖；勘误、修订和否定均追加新版本 |
| D5 | 全局保存电文档案，但知识权限和 `BeliefState` 按角色隔离 |
| D6 | 紧急情报即时呈报，例行情报按简报批次处理 |
| D7 | S2 提供几何计算、冲突检测和证据工具；最终判断由参谋形成 |
| D8 | 置信度是多维状态，不是单一 high/medium/low |
| D9 | 海图接触是角色假设，不是敌军实体；允许多个竞争假设并存 |
| D10 | 失真和判断结果可由骰子系统产生，LLM 只解释和演绎 |
| D11 | `observed_at / filed_at / received_at / briefed_at` 构成证据时间链 |
| D12 | 新认知必须由具体参谋通过工具产生，系统不能静默完成判断 |
| D13 | 正式海图只显示经过指挥官批准的作战标图 |
| D14 | 已批准标图不可覆盖；新证据只能提出新版修订并再次审批 |
| D15 | 系统可通过工作队列自动触发参谋工作，但不能自动生成参谋结论 |
| D16 | 报告由 LLM-NPC 根据人物和历史撰写，文风与重点不统一 |
| D17 | NPC 可以推测、误判、异想天开，但不能越权读取或篡改原始记录 |
| D18 | 当前来源限定为空中搜索、舰艇瞭望/雷达/声呐、友军电报 |
| D19 | 第一批主纵切为舰载侦察机完整情报闭环 |
| D20 | NPC 维度数量和错误公式由 S3 通过公式、消融和历史校准最终确定 |

---

## 三、系统边界

### S2 负责

- 来源观测的规范化。
- 电文起草、通信、延迟与完整性。
- 旗舰收报室与消息档案。
- 证据账本与时间链。
- 角色可见范围和独立信念状态。
- 情报工作队列与处理状态。
- 情报参谋判断书。
- 标图提案、批准、修订和历史版本。
- 方位线、交叉定位、可能区域等推理工具。
- 接触生命周期与多维不确定度。
- 玩家情报界面和正式海图输入。

### S2 不负责

- `GameState` 中的世界真相推进。
- NPC 性格模型的最终维度选择与权重。
- 具体作战命令和授权执行。
- 攻击、损伤和战斗结算。
- 胜负条件和历史结局。
- 长期关系、信任和派系。

### 上游与下游

| 系统 | 关系 |
|---|---|
| S1 世界模拟 | 提供真实目标、舰艇、飞机、传感器位置和时间 |
| S3 参谋认知 | 消费证据工具，产生 NPC 判断、错误和报告 |
| S5 指挥执行 | 消费已批准标图制定命令；发送友军电报 |
| S6 行动后果 | 提供实际接触、战斗、损失和事件结果 |
| S7 叙事复盘 | 对比证据链、参谋判断、批准记录和实际结果 |
| S8 交互表现 | 收报室、简报、审图、正式海图和版本历史 |
| S10 LLM 质量 | 保证权限隔离、行为评估和可回放性 |

---

## 四、统一数据链

```text
ActualWorld
  → SourceObservation
  → FiledMessage
  → ReceivedMessage
  → Evidence
  → IntelWorkItem
  → NPCAssessment
  → NPCClaim
  → IntelBrief
  → PlotProposal
  → CommanderDecision
  → ApprovedPlot
  → Chart
```

### 强制约束

1. `SourceObservation` 可以使用真实世界数据，但只存在于规则侧。
2. NPC 只能读取经过权限转换的 `EvidenceView`。
3. 玩家接口只下发收报档案、公开判断、已批准标图和复盘数据。
4. 原始消息、判断和标图版本均不得原地覆盖。
5. 任何派生认识必须引用产生它的 NPC 和工具调用。
6. `actual_enemy` 不进入报告生成、情报工具、NPC prompt 或玩家 API。

---

## 五、二级模块

## M2.1 来源与传感器

### 目标

把不同来源转换为统一 `SourceObservation`，但不直接产生敌情或海图标记。

### 当前范围

- 舰载 SBD 侦察机。
- PBY 等空中巡逻机。
- 舰艇瞭望。
- 雷达。
- 声呐。
- TF16、TF17 等友军电报。

### 子模块

- `M2.1.1` 来源类型与数据集 schema。
- `M2.1.2` 空中搜索观测。
- `M2.1.3` 瞭望目视观测。
- `M2.1.4` 雷达与声呐接触。
- `M2.1.5` 友军报告适配。
- `M2.1.6` 观测真实值与 NPC 可见值分离。
- `M2.1.7` 传感器质量、环境修正和能力限制。

### 验收

- 同一真实目标可由不同来源产生不同观测。
- 观测不直接出现在玩家海图。
- 所有观测都具备来源、时间、观测者位置和能力信息。

## M2.2 电文与通信

### 目标

把观测转化为真实送达旗舰的通信产物，并完整记录传输过程。

### 子模块

- `M2.2.1` 电文信封：发报者、呼号、收报者、密级、优先级。
- `M2.2.2` 电文史料格式约束与非统一文风规则。
- `M2.2.3` LLM 生成本方报告，文风由人物与人设控制。
- `M2.2.4` 延迟、丢失、重复、残缺与转写错误。
- `M2.2.5` `observed_at / filed_at / received_at / briefed_at`。
- `M2.2.6` 勘误电报与旧消息关联。
- `M2.2.7` 旗舰统一收报室。
- `M2.2.8` 通信优先级与处理分流。

### 消息状态

```text
DRAFT
FILED
IN_TRANSIT
RECEIVED
LOGGED
ROUTED
PROCESSED
ARCHIVED
LOST
CORRECTED
```

### 通信完整性

```text
COMPLETE
PARTIAL
GARBLED
UNREADABLE
DUPLICATE
CORRECTED
```

### 验收

- 玩家只能读取 `RECEIVED` 及之后的消息。
- 未到达的通信不能泄露内容。
- 勘误不会覆盖原电文。
- 不同 NPC 对同一观测可以撰写不同风格和不同重点的报告。

## M2.3 证据账本

### 目标

把电文与观测转化为可检索、可引用、不可变的证据。

### 子模块

- `M2.3.1` `Evidence` 模型和唯一 ID。
- `M2.3.2` 来源与消息谱系。
- `M2.3.3` 来源可靠性评估。
- `M2.3.4` 识别、位置、数量、时间和意图维度。
- `M2.3.5` 相互印证、冲突和勘误关系。
- `M2.3.6` 证据权限与角色可见版本。
- `M2.3.7` 证据年龄和有效范围。

### 验收

- 同一证据可被多个判断引用。
- 修改认知不会修改原始证据。
- 证据可以追溯至具体电文和原始观测。
- NPC 无法读取无权限证据。

## M2.4 角色信念与接触

### 目标

为玩家和每名 NPC 维护独立战场认知。

### 子模块

- `M2.4.1` `BeliefState` 模型。
- `M2.4.2` `ContactHypothesis` 模型。
- `M2.4.3` 接触生命周期。
- `M2.4.4` 多维置信度。
- `M2.4.5` 候选关联与竞争解释。
- `M2.4.6` 陈旧、失去接触、否定和替代。
- `M2.4.7` 位置不确定区域。
- `M2.4.8` 信念变化审计。

### 接触状态

```text
BEARING_ONLY
TENTATIVE
PLOTTED
STALE
LOST
REJECTED
SUPERSEDED
ARCHIVED
```

### 置信度维度

- 来源可靠性。
- 目标识别精度。
- 位置精度。
- 数量精度。
- 证据一致性。
- 新鲜度。
- 参谋判断置信度。

### 验收

- 不同 NPC 可以形成不同信念。
- 多个竞争接触可以同时存在。
- 系统不会静默合并或删除接触。
- 所有状态变化有作者、时间、理由和证据依据。

## M2.5 情报工作队列与参谋处理

### 目标

让新情报触发参谋工作，但禁止系统直接生成结论。

### 子模块

- `M2.5.1` `IntelWorkItem` 模型。
- `M2.5.2` FLASH / URGENT / ROUTINE / CORRECTION 优先级。
- `M2.5.3` 自动分配与队列排序。
- `M2.5.4` NPC 工作状态和积压。
- `M2.5.5` 参谋工具调用和审计。
- `M2.5.6` 超时、未处理与升级。
- `M2.5.7` 指挥官主动要求研判。
- `M2.5.8` 工作完成的书面产出。

### 工作状态

```text
QUEUED
ASSIGNED
IN_PROGRESS
WAITING_FOR_EVIDENCE
SUBMITTED
ACKNOWLEDGED
CLOSED
CANCELLED
```

### 验收

- 系统可以唤醒 NPC 处理事项。
- 没有 NPC 工具调用时，不会产生判断或标图。
- FLASH 能打断例行工作。
- ROUTINE 可以合并到定期简报。

## M2.6 情报简报与标图审批

### 目标

把参谋判断转化为可供指挥官审阅、讨论和批准的标图版本。

### 子模块

- `M2.6.1` `NPCAssessment` 与 `NPCClaim`。
- `M2.6.2` `IntelBrief` 模型。
- `M2.6.3` `PlotProposal` 模型。
- `M2.6.4` 变更摘要与版本比较。
- `M2.6.5` 指挥官讨论和修改意见。
- `M2.6.6` 批准全部、批准部分、驳回、暂缓。
- `M2.6.7` `ApprovedPlot` 正式图层。
- `M2.6.8` 标图历史与责任人。

### 审批状态

```text
DRAFT
PROPOSED
REVISION_REQUESTED
PARTIALLY_APPROVED
APPROVED
REJECTED
DEFERRED
SUPERSEDED
```

### 验收

- 未批准情报不会进入正式海图。
- 批准不等于确认事实，只表示正式采纳当前判断。
- 新证据不会静默修改已批准标图。
- 指挥官可以只批准简报中的部分标图项。

## M2.7 推理与不确定度工具

### 目标

为参谋提供确定性的推理能力，但不让系统代替参谋下结论。

### 子模块

- `M2.7.1` 方位线与方位扇面。
- `M2.7.2` 距离圆和可能区域。
- `M2.7.3` 多方位线交点。
- `M2.7.4` 接触候选关联。
- `M2.7.5` 搜索覆盖缺口。
- `M2.7.6` 位置年龄和可能移动范围。
- `M2.7.7` 证据冲突检测。
- `M2.7.8` “判断依赖什么证据”的反查。
- `M2.7.9` 工具调用日志。

### 强制约束

- 工具只对已收到且当前 NPC 有权限的证据计算。
- 计算结果表达为候选几何关系，不输出唯一真值。
- 是否采用计算结果由情报参谋判断并写入简报。
- 没有任何参谋调用时，不自动生成不确定区域或修订接触。

### 验收

- 工具输出与真实敌情没有直接依赖。
- 相同输入和相同种子可复现相同结果。
- 工具调用可追踪到 NPC、时间和证据集合。

## M2.8 情报界面、海图与复盘

### 目标

让玩家真实体验“收报—读简报—审图—批准—生效”的流程。

### 子模块

- `M2.8.1` 旗舰收报室。
- `M2.8.2` 原始电文阅读器。
- `M2.8.3` 情报判断书。
- `M2.8.4` 参谋长批注。
- `M2.8.5` 标图审阅和历史版本比较。
- `M2.8.6` 正式海图已批准图层。
- `M2.8.7` 专业作战标图符号。
- `M2.8.8` 未处理、待审阅和紧急提醒。
- `M2.8.9` 战后证据链和归因视图。

### 正式海图表达

- 观测时位置。
- 当前位置可能区域。
- 方位线、距离和交点。
- 航向与航速矢量。
- 接触轨迹。
- 时间标注和证据编号。
- 来源、判断和批准版本。
- 新鲜、陈旧、失去接触和已否定状态。

### 验收

- 玩家能区分事实、参谋判断和批准标图。
- 所有正式标图都能反查证据和批准记录。
- 待批准内容不会冒充正式敌情。

---

## 六、核心数据对象

## 6.1 `SourceObservation`

```text
id
source_id
source_type
observer_actor_id
observer_position
observed_at
sensor_capability
environment
target_class_observation
bearing_observation
distance_observation
count_observation
raw_quality
internal_truth_ref        # 规则侧，不对 NPC/玩家序列化
```

## 6.2 `MessageEnvelope`

```text
id
sender_id
sender_call_sign
recipient_ids
priority
classification
channel
observed_at
filed_at
received_at
condition
message_kind
supersedes_message_id
raw_text
generated_by_npc
```

## 6.3 `Evidence`

```text
id
message_id
source_id
claim_scope
observed_at
received_at
source_reliability
identity_precision
position_precision
count_precision
corroboration
freshness_at
access_policy
status
supersedes_evidence_id
```

## 6.4 `BeliefState`

```text
actor_id
contacts
known_evidence_ids
open_questions
last_updated_at
version
```

## 6.5 `ContactHypothesis`

```text
id
actor_id
classification
status
observed_position
current_estimate
uncertainty_envelope
course_estimate
speed_estimate
confidence_dimensions
evidence_ids
first_seen_at
last_seen_at
association_candidates
supersedes_contact_id
created_from_assessment_id
```

## 6.6 `NPCAssessment`

```text
id
author_actor_id
created_at
based_on_evidence_ids
facts_used
claims
alternative_hypotheses
confidence
change_my_mind
recommended_action
dice_records
```

## 6.7 `IntelBrief`

```text
id
author_actor_id
created_at
briefed_at
audience
priority
new_evidence_ids
changed_judgments
plot_proposals
unresolved_questions
status
```

## 6.8 `PlotProposal`

```text
id
plot_id
version
author_actor_id
based_on_evidence_ids
assessment_ids
geometry
method
assumptions
confidence
change_summary
supersedes_version
status
```

## 6.9 `ApprovedPlot`

```text
plot_id
current_version
approved_by
approved_at
state
history
```

## 6.10 `CheckRecord`

```text
check_id
check_type
actor_id
game_time
random_seed
raw_roll
modifiers
final_roll
degree
effects
context
```

---

## 七、核心流程

## 7.1 空中侦察完整流程

```text
1. 玩家或参谋发起侦察
2. 飞机沿航线飞行
3. 世界模拟产生实际相遇
4. 骰子系统执行探测检定
5. 骰子系统执行观察质量检定
6. SourceObservation 产生
7. 报告 NPC 根据可见观测和人物风格撰写电文
8. FiledMessage 进入通信链
9. 骰子系统执行通信检定
10. ReceivedMessage 进入旗舰收报室
11. 通信官登记并路由给情报参谋
12. IntelWorkItem 进入处理队列
13. 情报参谋读取证据并调用推理工具
14. 骰子与判断模型产生判断结果、偏差和置信度
15. 情报参谋形成 Assessment 与 IntelBrief
16. 简报产生 PlotProposal
17. 参谋长批注并呈报
18. 指挥官讨论、修改、批准或驳回
19. 批准项进入 ApprovedPlot
20. 正式海图刷新
```

## 7.2 新旧判断冲突

```text
新证据到达
  → 情报参谋比较新旧证据
  → 判断是否需要修订
  → 形成新版 PlotProposal
  → 指挥官批准前保留旧标图
  → 批准后新版本生效，旧版本存档
```

## 7.3 勘误电报

```text
原电文 P1 已收到
  → 后续电文 P2 声明更正
  → P2 引用 P1
  → P1 标记为 CORRECTED
  → 情报参谋重新判断
  → 产生新版简报与标图提案
```

## 7.4 误报否定

```text
接触 H1 曾获批上图
  → 新证据表明 H1 为误报
  → 情报参谋提出 REJECTED 建议
  → 指挥官批准
  → H1 转为 REJECTED
  → 保留原图和所有历史版本
```

---

## 八、角色权限

| 角色 | 默认可见 | 默认产出 |
|---|---|---|
| 玩家 | 已收电文、已呈报判断、已批准标图 | 批准、驳回、要求修订 |
| 通信官 | 通信链内电文、收发状态 | 收报记录、路由和转发 |
| 情报参谋 | 有权限的完整证据集 | Assessment、Brief、PlotProposal |
| 参谋长 | 情报简报、关键原文、舰队态势 | 批注、优先级和呈报意见 |
| 舰长 | 本舰和授权态势 | 本舰战斗报告、状态电报 |
| 航海参谋 | 本舰队位置、战区和航线 | 航线建议，不生成敌情 |
| 友军部队 | 本方可见信息 | 友军状态、接触和请求电报 |

权限控制必须发生在状态转换层，不能只依赖 prompt 提醒。

---

## 九、骰子系统集成

### 需要的检定类型

```text
DETECTION_CHECK
OBSERVATION_QUALITY_CHECK
COMMUNICATION_CHECK
JUDGMENT_CHECK
CORRECTION_CHECK
```

`JUDGMENT_CHECK` 的具体公式与 NPC 维度由 S3 提供，S2 只定义输入输出。

### S2 对骰子系统的要求

- 支持显式随机种子。
- 保存 `CheckRecord`。
- 支持检定类型和效果域。
- 支持多阶段独立检定。
- 支持错误方向、严重度和表达确定性的结构化输出。
- 支持回放，不依赖未记录的全局随机状态。
- 不要求 LLM 重新计算骰子结果。

### 需优化的现有问题

- `src/scouting.py` 中绕过骰子的 `random` 调用应逐步迁移。
- 侦察检定应使用实际执行单位的能力，而非固定 Browning。
- `grid` 与 `SearchPattern` 的映射问题必须修复。
- 骰子文档与代码中的 competence 权重需要统一。
- 全局随机状态需要迁入可记录、可复现的 RNG 服务。

---

## 十、接口建议

### 玩家查询

```text
GET /intel/inbox
GET /intel/messages/{message_id}
GET /intel/briefs
GET /intel/briefs/{brief_id}
GET /intel/plots
GET /intel/plots/{plot_id}/history
GET /intel/work-items
```

### 玩家操作

```text
POST /intel/briefs/{brief_id}/request-revision
POST /intel/plots/{plot_id}/approve
POST /intel/plots/{plot_id}/reject
POST /intel/plots/{plot_id}/defer
POST /intel/work-items/{item_id}/request
```

### 禁止暴露

- `internal_truth_ref`
- `actual_enemy`
- 未收到电文原文
- 无权限 NPC 的 BeliefState
- 未经选择的全部内部证据
- 未经批准的 PlotProposal 正式层

---

## 十一、现有实现迁移

| 当前对象 | 目标处理 |
|---|---|
| `actual_enemy` | 继续作为规则侧真相，禁止直接生成玩家敌情 |
| `known_enemy` | 拆为角色 BeliefState 与 ApprovedPlot，不再全局共享 |
| `pending_reports` | 拆为 FiledMessage / InTransitMessage / Evidence |
| `incoming_messages` | 迁移为 MessageArchive 和收报室 |
| `ScoutMission.detections` | 保存内部观测 ID，不直接写玩家敌情 |
| `confirm_contact()` | 废弃；改为 PlotProposal + CommanderApproval |
| `confidence` 字符串 | 替换为多维置信度 |
| `/state.known_enemy` | 改为玩家当前已批准标图的公共视图 |
| 海图敌标 | 只渲染正式 ApprovedPlot 及其历史 |

迁移期间应保留兼容读取层，避免一次性破坏现有 UI 和测试。

---

## 十二、测试与评估

### 单元测试

- 八类核心模型 schema 和序列化。
- 时间链一致性与时区处理。
- 消息状态机。
- 证据不可变与勘误链。
- 权限过滤。
- 角色 BeliefState 隔离。
- Contact 生命周期。
- PlotProposal 审批与版本。
- Approval 后才进入正式图层。
- 随机种子和 CheckRecord 可回放。
- `actual_enemy` 不进入任何公开视图。

### 集成测试

- SBD 完整纵切。
- FLASH 打断 ROUTINE。
- 两个互相矛盾的侦察报告。
- 后续勘误。
- 误报否定。
- 陈旧接触和重新接触。
- 相同观测由不同 NPC 撰写不同报告。
- 指挥官批准部分标图项。

### LLM 行为评估

固定场景不要求固定文本，但检查：

- 通信官不越权分析敌情。
- 情报参谋不读取无权限证据。
- Browning 可以激进建议，但不能创造秘密事实。
- 低能力 NPC 可以犯错，错误有可回放来源。
- 高想象 NPC 可以给出无证据推测，但不会被误存为证据。
- NPC 不读取 `actual_enemy`。
- NPC 不冒充其他人物发报或修改他人报告。
- 报告与人物历史风格一致。

### UI 验证

- 收报室和未读状态。
- 电报原文、发报时间和收报时间。
- 简报、批注与标图建议。
- 批准前/批准后的海图差异。
- 版本历史和变更摘要。
- 复盘证据链。
- 静态守卫测试和浏览器截图验证。

---

## 十三、实施阶段

## Phase S2.0：规格与基础契约

### 任务

- 固定 S2 数据边界和命名。
- 定义角色权限与 `actual_enemy` 防泄漏规则。
- 定义消息、证据、判断、简报、标图版本状态机。
- 定义与 S3 的 `JudgmentPolicy` 接口。
- 审计骰子系统缺口并形成优化任务。

### 验收

- 数据流图无循环状态。
- 每个对象都能回答“谁在何时基于什么产生了它”。
- 所有已确认 D1–D20 均有对应规格。

### 执行记录（S2.0，2026-09-17）

- 新增 `src/intel/contracts.py`：MessageStatus/CommCondition/EvidenceStatus/ContactStatus/
  WorkItemStatus/WorkPriority/ApprovalStatus/CheckType/SourceType/ActorRole 枚举；五类
  状态机转换表 + `require_transition` 守卫；`_ROLE_SCOPES` 权限白名单 +
  `FORBIDDEN_SCOPES`（actual_enemy/internal_truth_ref/unreceived_messages）+
  `PLAYER_VISIBLE_SCOPES`；`DATA_FLOW_EDGES` 统一数据链（测试守卫为 DAG）。
- 新增 `src/intel/judgment.py`：`JudgmentPolicy` Protocol（runtime_checkable）+
  `EvidenceView`（无真值字段）/`ActorProfile`（开放属性集）/`AssessmentDraft`
  （开放多维置信 dict）/`JudgmentDice`（骰子结构化输出）。维度数量与公式未锁定（D20）。
- 新增 `docs/design/S2_INTEL_SYSTEM.md`：对象谱系表、状态机、权限矩阵、
  actual_enemy 防泄漏规范、骰子缺口审计（7 项，全部带入 S2.1）、D1–D20 追溯表。
- 新增 `tests/test_intel_contracts.py`：35 测试（枚举一致性/状态机合法转换/
  DAG 无环/权限矩阵/防泄漏/JudgmentPolicy 接口）。
- 验收核对：数据流无循环 ✅（Kahn 守卫）；对象谱系表 ✅（§1.1）；D1–D20 全覆盖 ✅（§六）。

## Phase S2.1：骰子与可复现随机性

### 任务

- 引入游戏级随机种子和 RNG 服务。
- 扩展 `CheckRecord`。
- 增加 S2 检定类型。
- 逐步替换 `scouting.py` 的直接随机调用。
- 修复侦察执行者能力和搜索模式映射。

### 验收

- 同一局面同一种子可重放相同结果。
- 每次检定都有理由、输入、骰值和效果记录。
- 现有 352 项测试保持通过。

## Phase S2.2：电文、证据与角色信念

### 任务

- 实现消息信封、收报室和消息状态机。
- 实现 `Evidence`、时间链和权限视图。
- 实现 `BeliefState` 和 `ContactHypothesis`。
- 实现 `NPCClaim` 审计。
- 建立旧 `known_enemy` 兼容层。

### 验收

- 同一报告不会进入所有 NPC 的全局敌情表。
- 勘误不会覆盖原始电文。
- 玩家和 NPC 只能看到权限内证据。

## Phase S2.3：舰载侦察机纵切

### 任务

- 接入探测和观察质量检定。
- 实现报告 NPC 的消息撰写。
- 实现通信检定与延迟。
- 实现通信官路由。
- 实现情报参谋工作项。
- 实现第一版 `IntelligenceBrief`。

### 验收

- 从 SBD 实际发现到玩家看到简报可完整运行。
- 能区分漏报、误判、通信损坏和参谋误判。
- 未收到电报不会泄露内容。

## Phase S2.4：作战标图审批

### 任务

- 实现 `PlotProposal`。
- 实现方位线、距离和接触几何。
- 实现参谋长批注。
- 实现指挥官批准、驳回、暂缓和修订。
- 实现 `ApprovedPlot` 和正式海图图层。
- 实现版本比较和历史。

### 验收

- 未批准标图不会进入正式海图。
- 新证据不会静默覆盖已批准标图。
- 批准、修订和否定全程可追溯。

## Phase S2.5：冲突、陈旧与勘误

### 任务

- 实现多证据冲突。
- 实现候选关联但禁止静默合并。
- 实现接触陈旧与失去接触。
- 实现勘误电报。
- 实现误报否定。
- 实现参谋主动更新建议。

### 验收

- 多份矛盾报告可以并存。
- 旧接触能显式衰老或被新判断替代。
- 原版本和修订理由均可复盘。

## Phase S2.6：舰艇接触与友军电报

### 任务

- 接入瞭望、雷达和声呐来源。
- 接入 TF16、TF17 友军报文。
- 按同一证据协议处理。
- 增加来源特有的质量与误差规则。

### 验收

- 非航空来源不会绕过通信和情报流程。
- 友军报告会保留转述层级与原发送者。
- 不同传感器的识别差异可感知。

## Phase S2.7：推理工具与不确定度

### 任务

- 实现方位线交叉。
- 实现可能区域和位置年龄。
- 实现覆盖缺口。
- 实现证据冲突提示。
- 实现工具调用记录和确定性回放。

### 验收

- 工具输出是候选关系而非唯一真值。
- 结果只能由 NPC 工具调用产生。
- 玩家可以在复盘中看到参谋是否使用过这些工具。

## Phase S2.8：界面收口与复盘

### 任务

- 完成收报室、简报、审图和历史比较。
- 完成专业作战标图视觉语言。
- 完成待处理、紧急和待批准提醒。
- 完成战后证据—判断—批准—结果链。
- 完成浏览器截图和交互验证。

### 验收

- 新玩家能理解事实、判断和批准标图之间的区别。
- 所有正式海图标图都能一键反查来源和批准记录。
- 一局失败可以明确指出责任链。

---

## 十四、总体验收标准

S2 只有在以下条件全部满足时才可宣告完成：

1. 玩家看不到 `actual_enemy` 或系统融合答案。
2. 玩家能查看所有真正收到的原始电文。
3. 情报参谋基于权限内证据形成判断书。
4. 不同 NPC 能写出风格、重点和错误不同的报告。
5. 系统可以触发参谋工作，但不能代替参谋下结论。
6. 海图接触是假设，允许多个竞争解释并存。
7. 正式海图只显示经过指挥官批准的标图。
8. 已批准标图不可覆盖，修订必须重新审批。
9. 报告、判断、标图和批准均有完整时间链。
10. 所有失真和判断偏差可回放、可追责。
11. 示例纵切“SBD 发现目标 → 收报 → 研判 → 呈报 → 批准 → 上图 → 修订”完整通过。
12. 现有功能不回归，新增规则和 LLM 行为均有测试。

---

## 十五、暂不纳入本计划

- JN-25 和其他战略破译情报。
- 海岸观察者、潜艇和无线电测向。
- 完整天气系统。
- 完整战斗和损伤演算。
- 参谋关系、信任与派系。
- 多战役长期记忆。
- 无线电通信对敌方侦察的暴露模型。

这些能力应保留扩展接口，但不进入 S2 第一批实现。

---

## 十六、主要风险

| 风险 | 处理 |
|---|---|
| 流程过于繁琐 | 紧急单报、例行批次、支持批准全部 |
| LLM 输出越权 | 权限数据在 prompt 外裁剪，工具层再次校验 |
| 参谋工作不确定性 | 工作队列、超时和主动催促 |
| 情报对象过多 | 严格复用统一数据链，来源只做适配 |
| 历史画图不准确 | 后续增加史实绘图规范考证与图示验收 |
| 骰子不可回放 | S2.1 前置完成种子与 CheckRecord |
| 新旧状态迁移破坏 UI | 保留兼容读取层，分阶段迁移 |
| 参谋判断过于频繁或稀少 | 由 S3 公式、行为评估和消融测试调节 |

---

## 十七、下一步

批准本计划后，首先执行 `Phase S2.0`，输出：

- S2 数据模型定义。
- 权限矩阵。
- 状态机与接口清单。
- `actual_enemy` 防泄漏测试规范。
- S3 `JudgmentPolicy` 接口草案。
- 骰子系统优化任务清单。

在 `Phase S2.0` 通过评审前，不开始修改运行时代码。
