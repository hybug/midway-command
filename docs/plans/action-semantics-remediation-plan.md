# 操作语义固定化整改计划（action-semantics-remediation-plan）

> 状态：**现行跨系统专项计划**
> 创建日期：2026-09-19
> 适用范围：S2 / S3 / S4 / S5 / S8
> 目标：消除自由文本、LLM 猜测和遗留端点造成的操作歧义

---

## 一、整改目标

所有正式操作必须明确表达：

```text
做什么
对什么做
使用哪些范围或对象
是否要求回复
是否执行状态变更
由谁批准
```

采用统一原则：

> **内容自由文本，动作固定枚举，范围固定选项，执行明确确认。**

自然语言可以表达问题、说明、背景和电文正文，但不能替代动作类型、目标范围、权限和批准语义。

---

## 二、统一交互模型

每个正式操作拆为四层：

```text
Content    自由文本：问题、正文、备注、说明
Action     固定枚举：评估、复核、批准、驳回、发报、改变航向
Scope      固定对象：收件人、目标舰队、方案、标图版本、证据集
Confirm    明确确认：审批、执行、发送
```

统一命令信封：

```text
ActionCommand
  command_id
  action_type
  source_type
  source_id
  target_type
  target_id
  options
  recipients[]
  priority
  note
  requires_response
  requires_confirmation
  created_by
  created_at
```

各领域可以保留独立端点，但必须复用该语义模型，不能继续依赖自然语言推断动作。

---

## 三、动作目录

## 3.1 通信动作（v0）

```text
SEND_TELEGRAM
FORWARD_TO_CHAIN
```

`CC_MESSAGE / REVIEW / 互评 / 玩家转述` 均延期，不属于 S4 v0。下级信息由系统按指挥链自动上呈。

## 3.2 核心参谋动作（v0）

```text
REQUEST_ASSESSMENT
REQUEST_RECONSIDERATION
RECORD_COMMANDER_FEEDBACK
ACKNOWLEDGE_STAFF_NOTICE
DEFER_STAFF_NOTICE
CLOSE_STAFF_NOTICE
```

`REQUEST_REVIEW / COMMENT / DISSENT / CONFLICT` 延期。v0 只允许 commander 与史实配置的直接沟通名单交流。

## 3.3 情报与标图动作

```text
PROPOSE_PLOT
APPROVE_PLOT
REJECT_PLOT
DEFER_PLOT
REQUEST_PLOT_REVISION
MARK_CONTACT_STALE
REJECT_CONTACT
```

原 `confirm-contact` 不再作为独立动作；接触确认必须走 PlotProposal。

## 3.4 航线动作

```text
PROPOSE_ROUTE
APPROVE_ROUTE
CANCEL_ROUTE
REQUEST_ROUTE_REVISION
```

`REQUEST_ROUTE_REVISION` 应附固定修改类别：

```text
COURSE
WAYPOINTS
SPEED
TIMING
RISK_LIMIT
OTHER
```

## 3.5 正式命令动作

```text
SET_COURSE
SET_SPEED
ADJUST_CAP
LAUNCH_SCOUT
PLAN_STRIKE
CONFIRM_STRIKE
REJECT_STRIKE
RECALL_AIR_GROUP
```

正式命令与聊天严格分离。

---

## 四、现有入口审计

| 入口 | 当前状态 | 判定 | 整改 |
|---|---|---|---|
| 战役选择 /game/new | 固定 theater_id | ✅ | 保留 |
| ADVANCE +15MIN | 固定分钟 | ✅ | 保留，未来可选时间范围 |
| ISSUE ORDER 弹层 | 主要展示 pending suggestions | ⚠ | S5 增加命令类型与参数选择器 |
| suggestion approve/reject | 固定按钮，底层 action_type 可变 | ⚠ | 改为 typed proposal |
| plot approve/reject/defer/request-revision | 固定按钮 | ✅ | 保留并增加固定修订理由 |
| judgment feedback | 固定枚举 | ✅ | 保留 |
| judgment task | 固定 ASSESS，question 自由文本 | ✅ | 保留 |
| judgment reconsider | 固定动作，reason 自由文本 | ⚠ | 增加固定原因枚举，note 可选 |
| staff relay | 只有“转述给” | ❌ | v0 移除公开入口；未来如恢复，必须使用固定 intent |
| STAFF chat | 自由文本 | ⚠ | 只允许查询/交谈/提出建议，禁止写状态 |
| route approve/reject | 固定按钮 | ✅ | 保留 |
| route comment | prompt() 自由文本直接送 LLM | ❌ | 固定修订类别 + 可选说明 |
| navigator propose | 固定 propose_route 工具 | ✅ | 可保留，增加显式入口 |
| comms outgoing | 正文自由文本，收件人硬编码，优先级未暴露 | ⚠ | 固定收件人、消息类型和优先级 |
| confirm-contact | 地图点击直接转 known_enemy | ❌ | 删除公共入口，迁移到 PlotProposal |
| strike plan/confirm/reject/recall | 固定端点 | ✅ | 后续接入 typed ISSUE ORDER |
| NPC execute_action | LLM 可在聊天中直接改航向/航速/CAP | ❌ | 从聊天移除写工具，只允许 propose_action |

---

## 五、P0 红线整改

### R1 聊天不得修改状态

- 从所有 `/chat` 可用工具集中移除 `execute_action`。
- NPC 可以调用只读工具。
- NPC 可以提出 `ProposedAction`，但必须由玩家在 ISSUE ORDER 中确认。
- 静态测试断言 chat 工具集不含写工具。

### R2 删除 confirm-contact 旁路

- 地图点击已收到接触时打开 INTEL 审图，不再确认成 `known_enemy`。
- `/confirm-contact/{index}` 标记 deprecated 并拒绝外部调用。
- 所有正式接触只能经 `PlotProposal → CommanderDecision → ApprovedPlot`。
- 前端移除 `onConfirmContact` 的旧接线。

### R3 移除 staff relay

- v0 删除 `/staff/relay` 的玩家公开入口和 UI 按钮。
- 下级信息只按指挥链自动上呈。
- 不实现跨参谋自由通信、互评、复核或分歧。
- 未来若重新引入跨参谋通信，必须使用固定 intent 和明确权限。

### R4 移除自由文本动作推断

- 禁止通过 `/chat` 文本创建正式评估、命令或通信动作。
- 禁止 `prompt()` 作为正式修改意见输入。
- 正式动作必须携带明确 `action_type`。
- LLM 可以建议动作，但 UI 必须让玩家点击固定按钮确认。

---

## 六、P1 文档与通信整改

### R5 航海提案修订

将自由文本 `feedback` 改为：

```text
revision_type
note
```

示例：

```text
revision_type: WAYPOINTS
note: 避开路易西亚德群岛北部浅礁
```

航海参谋仍可收到自然语言 note，但核心修改方向由固定选项决定。

### R6 COMMS 外发电报

发报表单固定：

- `recipient_ids`
- `message_type`
- `priority`
- `reply_required`
- `raw_text`

正文仍自由，收件范围与优先级不能依赖 LLM。

### R7 SITREP

当前“报告当前态势”不再走普通 chat。

改为固定动作：

```text
REQUEST_SITREP
recipient: chief_of_staff
```

结果进入正式 briefing/判断记录，而不是只存在于对话历史。

### R8 重新判断原因

固定枚举：

```text
NEW_EVIDENCE
NEW_COMMANDER_CONTEXT
CORRECTED_EVIDENCE
CONTRADICTION_FOUND
PREVIOUS_ASSUMPTION_INVALID
```

note 作为可选补充。

---

## 七、P2 正式命令系统

`ISSUE ORDER` 改为分步骤固定表单：

```text
1. 选择命令类型
2. 选择目标
3. 填写参数
4. 查看参谋解释和风险
5. 确认执行
```

命令类型从后端 `available_actions` 获取，不在前端硬编码不受控变化。

LLM 可以：

- 解释命令。
- 指出歧义。
- 提出替代方案。
- 请求澄清。
- 建议授权等级。

LLM 不可以：

- 直接执行。
- 自动补齐关键范围。
- 把聊天内容当命令。
- 跳过 commander 确认。

---

## 八、后端契约

## 8.1 Available Actions

对象详情接口应返回当前允许动作：

```text
available_actions:
  - action_type
  - label
  - required_options
  - allowed_recipients
  - enabled
  - disabled_reason
  - requires_confirmation
```

UI 只渲染后端允许的动作。

## 8.2 动作验证

后端必须验证：

- `action_type` 是否合法。
- 当前对象状态是否允许该动作。
- 调用者是否有权限。
- Scope 是否在允许范围。
- 是否缺少必填参数。
- 是否需要确认。
- 是否重复提交。

## 8.3 审计记录

每次动作写入：

```text
actor_id
action_type
source
targets
options
note
before_state
after_state
at
result
```

---

## 九、UI 规范

- 正式动作使用按钮、单选、多选和数值输入。
- 自由文本字段明确标注“说明/正文/备注”。
- 不允许按钮名称使用“处理”“转述”“确认一下”等模糊语义。
- 按钮文本使用明确动词：
  - 请评估
  - 请复核
  - 抄送
  - 批准上图
  - 要求修订
  - 发出命令
- 禁用按钮必须显示原因。
- 执行动作前显示目标和影响范围。
- 涉及状态改变的动作必须二次确认。
- 对话输入只出现在 STAFF 工作台。
- 聊天中建议的动作只显示“打开操作”，不能直接执行。

---

## 十、LLM 边界

数据边界不变：动作命令的 source/target/options 只能由玩家可见对象或调用者有权限的对象组成；`actual_enemy` 永远不能成为动作输入、输出或前端 payload。


LLM 可以输出：

```text
suggested_action
suggested_target
suggested_options
clarification_question
risk_note
```

LLM 不可以直接：

- 修改 GameState。
- 调用写工具。
- 创建正式命令。
- 创建正式标图审批。
- 创建正式关系变化。
- 越过 UI 确认。

---

## 十一、实施阶段

## Phase AS.0：契约与审计基线

- 建立 ActionCommand / AvailableAction / AuditRecord。
- 把本审计表转成自动化静态检查清单。
- 标记 deprecated 端点。
- 更新 S4/S5/S8 规格。

## Phase AS.1：P0 红线

- 移除 chat 写工具。
- 删除 confirm-contact 前端接线。
- 删除自由文本正式动作推断。
- 删除玩家转述入口，改由指挥链路由。
- 增加绕过测试。

## Phase AS.2：P1 文档与通信

- 路线修订固定选项。
- COMMS 发报表单。
- SITREP 正式化。
- Reconsider reason 固定化。
- 更新 STAFF / COMMS / INTEL UI。

## Phase AS.3：P2 正式命令

- ISSUE ORDER 类型化。
- 命令目标与参数选择。
- 参谋解释、风险与确认。
- 命令审计和复盘。

## Phase AS.4：收口

- 全入口审计。
- UI 截图。
- 静态守卫。
- 端到端动作跟踪。

---

## 十二、测试

### 静态守卫

- `/chat` 工具集中无写工具。
- 前端无正式动作 `prompt()`。
- confirm-contact 无生产接线。
- 所有正式按钮带 `data-action`。
- UI 不硬编码未经后端允许的动作。

### 后端测试

- 非法 action_type 被拒绝。
- 越权 scope 被拒绝。
- 非法 recipients 被拒绝。
- 状态不允许的动作被拒绝。
- 重复提交被阻止。
- 每次动作生成审计记录。

### 端到端测试

- 指挥链自动上呈一份下级报告。
- commander 向核心参谋要求正式判断。
- 要求航线修订。
- 发出指定优先级的外发电报。
- 下达 typed command。
- 确认不能通过 chat 改航向。
- 确认不能绕过 PlotProposal 修改正式海图。

---

## 十三、验收标准

1. 所有状态改变和关系相关操作使用固定动作枚举。
2. 自然语言只承载内容、问题、说明和备注。
3. LLM 不能直接执行操作。
4. 聊天不能修改游戏状态。
5. confirm-contact 旁路被关闭。
6. STAFF 通信明确区分抄送、评论、评估、复核。
7. COMMS 发报范围和优先级为固定选项。
8. 航海修订具有固定修改类别。
9. ISSUE ORDER 使用 typed command。
10. 所有动作产生统一审计记录并可回放。
11. UI 不存在模糊的正式动作按钮。
12. 原有 S2/S3/S8 合法流程不回归。

---

## 十四、依赖与顺序

- P0 必须在 S4 主动来访和跨参谋通信正式实现前完成。
- P1 应与 S4 关系事件和 S5 命令规划并行完成。
- P2 属于 S5 指挥执行系统。
- S8 负责 UI 选项、确认和审计展示。
- S10 负责验证 LLM 不会绕过动作协议。

---

## 十五、下一步

首先执行 `Phase AS.0`：

- 完成本计划引用的设计规格。
- 建立动作类型与审计 schema。
- 建立静态审计清单。
- 确认受影响的 S2/S3/S4/S5/S8 测试范围。

在 AS.0 完成前，不修改运行时代码。

---

## 十六、执行记录（2026-09-19：AS.0–AS.1 按 S4/S5 必需最小范围完成）

| Phase | 内容 | 状态（Commit） |
|---|---|---|
| AS.0 | ActionCommand/AvailableAction/AuditRecord 契约（src/actions/contracts.py）+ v0 动作目录 + 静态守卫清单（tests/test_action_semantics.py） | ✅ 373bf9d |
| AS.1 | R1 聊天写工具 execute_action 移除（TOOLS_SCHEMA+npc_config+提示词）；R2 confirm-contact 端点 410+前端接线删除；R3 /staff/relay(+s) 410+UI 转述按钮删除；R4 提示词不再指示执行 | ✅ 373bf9d |

AS.2（P1 文档通信整改）与 AS.3（P2 ISSUE ORDER 类型化）未在本轮范围——其中 ISSUE ORDER
类型化已由 S5.6 提前落地（3247a56）；AS.2 各项保留待后续。
