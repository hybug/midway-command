# S5 指挥、授权与执行系统实施计划（s5-command-execution-system-plan）

> 状态：**已执行（S5.0–S5.6 完成；按专项指令 AP 不在范围、cost_policy 仅占位，2026-09-19）**
> 创建日期：2026-09-19
> 上级路线图：`docs/plans/gameplay-system-roadmap.md`
> 前置计划：`docs/plans/ap-system-plan.md`
> 上游依赖：S2 通信、S3 判断、S4 指挥链
> UI 契约：`docs/plans/s8-ui-ux-system-plan.md`
> 动作规格：`docs/plans/action-semantics-remediation-plan.md`

---

## 一、目标

把 commander 的意图可靠地转换为可授权、可传达、可执行、可审计的 Order，同时保持信息迷雾。

S5 只负责：

- commander 想做什么。
- 授权到什么程度。
- 哪一岗位负责。
- Order 当前处于什么阶段。
- 实际结果如何回报 commander。

S5 不负责：

- 世界物理演算。
- 战斗与损失结算。
- 参谋判断和人物关系。
- AP 成本和行动经济。
- 舰艇、飞机和环境效果的具体计算。

核心原则：

> **S5 结构和控制 Order；S2 传达；S3 判断；S6 执行。**

---

## 二、确认的设计原则

| 编号 | 原则 |
|---|---|
| D1 | 所有正式命令统一使用 Order |
| D2 | Order 包含结构化执行边界和一等 commander_intent_text |
| D3 | v0 只支持 EXACT / INTENT |
| D4 | 参谋建议属于 S3，不直接成为 Order |
| D5 | 自然语言可生成可编辑草稿，确认后才能签发 |
| D6 | 一个 Order 只包含一个主要动作 |
| D7 | 每条 Order 只有一个主责任岗位 |
| D8 | Order 通过职责岗位路由，不直接绑定某个 NPC 姓名 |
| D9 | 命令端点不得直接修改舰队状态 |
| D10 | Order 通过 Pipeline 异步生效 |
| D11 | S2 负责送达和通信失败，S5 不做确认超时或自动重发 |
| D12 | 新 Order 必须做冲突检查，不静默覆盖 active Order |
| D13 | 修改和取消必须形成新 Order 记录 |
| D14 | 已发生效果不能回滚 |
| D15 | 部分完成放在 result，不增加额外状态 |
| D16 | 玩家只看到自己可确认的状态，隐藏执行事实通过报告获得 |
| D17 | 所有 Order 和生命周期事件追加保存 |
| D18 | AP 成本完全由独立 AP 专项定义，S5 只预留 cost_policy |
| D19 | S5 v0 只实现 SET_COURSE 和 LAUNCH_SCOUT 两条纵切 |
| D20 | 旧 suggestions/routes/strike 通过适配器逐步迁移，不做一次性大重构 |

---

## 三、S5 v0 范围

### 完整实现

- 统一 Order 模型。
- Order 编辑、签发和取消。
- 自然语言生成订单草稿。
- `SET_COURSE` 的 EXACT 流程。
- `LAUNCH_SCOUT` 的 INTENT 流程。
- 岗位路由。
- 冲突检查。
- Pipeline 集成。
- S2 消息关联。
- S6 结果回写。
- Order 事件审计。
- ISSUE ORDER 前端表单。

### 暂不实现

- SET_SPEED。
- ADJUST_CAP。
- RECALL_AIR_GROUP。
- PLAN_STRIKE / CONFIRM_STRIKE。
- 航线 Order 化。
- 自主执行。
- 抗命和独走。
- AP 成本。
- 完整命令批处理。
- 自然语言直接执行。

---

## 四、最小数据模型

## 4.1 Order

```text
id
order_type              fixed enum
target_refs[]
parameters              typed by order_type
commander_intent_text   required
authority_mode          exact / intent
priority                routine / urgent / flash
responsible_role        fixed role key
source_refs[]           情报 / 判断 / 标图
delivery_message_id
status                  internal state
reported_status         commander-known state
result                   OrderResult
cost_policy             预留，不在 S5 v0 解释
created_at
updated_at
```

## 4.2 OrderResult

```text
outcome                 success / partial / failed / cancelled
effects[]
deviations[]
reported_at
summary
```

部分完成：

```text
Order.status = COMPLETED
Order.result.outcome = partial
```

## 4.3 OrderEvent

```text
id
order_id
at
actor_id
event_type
summary
source_ref
```

首批事件：

```text
ORDER_CREATED
ORDER_ISSUED
ORDER_DELIVERED
ORDER_CLARIFICATION_REQUESTED
ORDER_ALTERNATIVE_PROPOSED
ORDER_APPROVED
ORDER_ACTIVATED
ORDER_CANCELLED
ORDER_COMPLETED
ORDER_FAILED
```

---

## 五、Order 类型

## 5.1 SET_COURSE

```text
order_type: SET_COURSE
target_refs: [task_force]
parameters:
  course: 0-359
authority_mode: EXACT
priority: routine / urgent / flash
commander_intent_text: required
```

行为：

- 按岗位路由。
- 校验目标有效和航向范围。
- 检查与当前 active 航向命令冲突。
- 通过 S2 传达。
- 在 Pipeline 生效。
- S6 执行实际转向。
- 结果通过报告回传。

## 5.2 LAUNCH_SCOUT

```text
order_type: LAUNCH_SCOUT
target_refs: [task_force]
parameters:
  search_objective
  search_area
  max_range_nm
  time_window
  constraints[]
authority_mode: INTENT
priority: routine / urgent / flash
commander_intent_text: required
```

责任参谋负责：

- 选择搜索模式。
- 选择航空兵数量和来源。
- 形成航线。
- 评估燃油和返航。
- 提交方案等待 commander 批准。

---

## 六、状态机

```text
DRAFT
ISSUED
PENDING_APPROVAL
ACTIVE
COMPLETED
FAILED
CANCELLED
```

EXACT：

```text
DRAFT → ISSUED → ACTIVE → COMPLETED / FAILED
```

INTENT：

```text
DRAFT → ISSUED → PENDING_APPROVAL → ACTIVE
      → COMPLETED / FAILED
```

任何未进入 ACTIVE 的状态可以：

```text
→ CANCELLED
```

规则：

- DRAFT 可编辑。
- ISSUED 后不得原地修改。
- PENDING_APPROVAL 可以由 commander 驳回或要求修改。
- ACTIVE 后只能取消或签发替代 Order。
- 被替代的旧 Order 标记 CANCELLED，并在 result 中记录 `superseded_by`。
- 不增加 ACKNOWLEDGED、PLANNING、PARTIAL 等状态。

---

## 七、职责路由

| Order | responsible_role |
|---|---|
| SET_COURSE | NAVIGATOR 或 scenario 指定的舰队机动责任岗位 |
| LAUNCH_SCOUT | AIR_OFFICER 或 scenario 指定的航空责任岗位 |

规则：

- 路由由 scenario roster 配置。
- 一条 Order 只有一个主责任岗位。
- `target_refs` 指定影响对象。
- commander 直接点某个 NPC 时，仍先归一化为岗位。
- 无责任岗位时，Order 不能 ACTIVE。
- NPC 的 autonomy 不改变责任归属。
- LLM 不能修改 responsible_role。

---

## 八、自然语言订单草稿

支持两种创建方式：

### 表单优先

```text
选择 Order 类型
→ 填写参数
→ 输入 commander intent
→ 校验
→ 确认签发
```

### 自然语言优先

```text
commander 输入命令
→ LLM 生成 Order 草稿
→ 展示类型、目标、参数、授权和歧义
→ commander 修改并确认
→ 正式签发
```

规则：

- 自然语言不能直接执行。
- commander_intent_text 原文永久保留。
- 结构化参数是硬约束。
- 文本与参数冲突时必须提示澄清。
- 一个 Draft 只包含一个主要 Order。
- 多动作文本拆为多个待确认草稿。
- 不自动批量签发。
- 无法确定的字段不能猜。

---

## 九、冲突检查

生效前检查同一实体、同一控制维度、时间窗口重叠。

典型冲突：

- 当前 active course 与新 course。
- 当前 active speed 与新 speed。
- 取消/召回与仍在执行的航空任务。
- 多任务争用飞机、甲板或燃油。

规则：

- 不静默覆盖 active Order。
- 冲突时显示旧 Order、旧参数和新参数。
- commander 可选择取消旧 Order、修改新 Order、暂缓或放弃。
- 冲突检查不能因 FLASH 优先级被绕过。
- 旧 Order 的历史完整保留。

---

## 十、通信与时间

S5 不计算实际送达，只关联 S2：

```text
delivery_message_id
```

流程：

```text
签发 Order
→ 创建 outgoing message
→ S2 处理延迟 / 丢失 / 送达
→ 成功送达后，责任岗位可处理
```

规则：

- 不使用 S5 内部 ACK 超时。
- 不自动重发。
- 通信失败显示在 COMMS。
- 玩家可主动决定重新发送命令。
- ACTIVE 必须晚于正式送达。
- 所有游戏时间来自 GameClock。

---

## 十一、玩家可见状态

玩家立即知道：

```text
DRAFT
ISSUED
PENDING_APPROVAL
CANCELLED
AWAITING_REPORT
```

内部可以记录：

```text
ACTIVE
COMPLETED
FAILED
```

但这些状态必须通过 S2 报告变为 commander 已知事实。

规则：

- 不向玩家直接泄露实际执行状态。
- 报告的到达可能有延迟或丢失。
- `reported_status` 是 UI 使用的字段。
- `status` 是规则侧状态。
- 战后复盘同时展示两者。

---

## 十二、S2 / S3 / S6 边界

数据边界：Order、intent 和结果均不得携带或读取 `actual_enemy`；只能引用玩家或责任角色有权知道的报告、判断、标图和状态。


| 系统 | 责任 |
|---|---|
| S2 | 命令通信、送达、丢失、报告回传 |
| S3 | 参谋理解、可行性判断、替代建议 |
| S4 | 责任参谋是否可沟通及指挥链 |
| S5 | Order 结构、授权、状态、冲突与审计 |
| S6 | 实际动作、时间消耗、效果与失败 |
| S8 | Order 表单、状态展示和 LOG |
| AP 专项 | cost_policy，不在 S5 内定义 |

---

## 十三、审计

每次 Order 生命周期变化写入 OrderEvent。

保存：

```text
order_id
at
actor
event_type
source_ref
summary
```

必须能够回答：

- commander 下达了什么。
- 他为什么下达。
- 哪条判断或标图支持它。
- 谁负责。
- 命令何时送达。
- 是否发生澄清、修改或取消。
- 是否实际执行。
- commander 当时知道什么。
- 最终真实结果是什么。

---

## 十四、实施阶段

## Phase S5.0：契约

- 完成 Order / OrderResult / OrderEvent schema。
- 定义 SET_COURSE 和 LAUNCH_SCOUT 参数。
- 定义状态与事件流转。
- 定义 S2/S3/S6 接口。
- 完成旧流程迁移映射。

## Phase S5.1：校验与路由

- 实现 Order 参数校验。
- 实现 responsible_role 路由。
- 实现冲突检查。
- 实现 ORDER_CREATED / ISSUED / CANCELLED。

## Phase S5.2：自然语言草稿

- 实现自然语言到 Order 草稿。
- 实现歧义和缺失字段提示。
- 保证不能直接签发或执行。
- 实现多动作拆分建议。

## Phase S5.3：SET_COURSE 纵切

- 表单创建、草稿确认、岗位路由。
- S2 发报和送达。
- Pipeline 生效。
- S6 转向结果。
- 报告与 LOG 回传。

## Phase S5.4：LAUNCH_SCOUT 纵切

- INTENT 授权。
- 责任岗位生成方案。
- PENDING_APPROVAL。
- commander 批准。
- S6 启动侦察。
- 报告和复盘。

## Phase S5.5：取消与替代

- 实现 CANCEL_ORDER。
- 实现取消太迟。
- 实现 superseded_by。
- 保证旧 Order 不可覆盖。

## Phase S5.6：UI 与验收

- ISSUE ORDER 表单。
- Order 列表和详情。
- 冲突提示。
- 报告状态和真实状态分离。
- LOG 审计链。
- 截图与端到端验收。

---

## 十五、测试

### 单元测试

- Order schema。
- 类型化参数校验。
- commander_intent_text 必填。
- 状态机合法转换。
- 非法转换拒绝。
- 岗位路由。
- 冲突检查。
- 不静默覆盖。
- 取消和 superseded_by。
- 部分完成落入 result。
- reported_status 与 status 分离。

### 集成测试

- SET_COURSE 全链。
- LAUNCH_SCOUT 全链。
- S2 丢包时 Order 不进入 ACTIVE。
- 手动重发不自动创建新 Order。
- S3 建议转 Order 草稿但不直接执行。
- S6 执行结果写回 Order。
- 玩家未收到报告时看不到隐藏结果。
- LOG 完整重放。

### UI 测试

- 表单创建 Order。
- 自然语言草稿确认。
- 多动作拆分。
- 冲突提示。
- 取消和替代。
- 状态和报告区分。
- 每步来源跳转。

---

## 十六、验收标准

1. 所有新正式命令使用统一 Order。
2. 没有命令端点直接修改舰队状态。
3. EXACT / INTENT 路径均可运行。
4. 参谋建议不能自动变成 Order。
5. 自然语言只能创建待确认草稿。
6. 一条 Order 只有一个主要动作和一个主责任岗位。
7. 冲突不会静默覆盖。
8. 修改和取消均保留历史。
9. S2 独占通信送达，S5 无自动重发。
10. 玩家不会实时看到隐藏执行状态。
11. 部分完成不新增 Order 状态。
12. SET_COURSE 和 LAUNCH_SCOUT 纵切通过。
13. 全部 Order 事件可审计、可回放。
14. AP 成本未硬编码。

---

## 十七、暂缓

- AP 成本。
- 自主执行。
- 抗命和独走。
- 完整命令批处理。
- 所有旧命令一次迁移。
- 复杂授权等级。
- 自由文本直接执行。

---

## 十八、下一步

等待 AP 专项完成后：

1. 执行 Phase S5.0。
2. 建立 Order 契约。
3. 完成 SET_COURSE EXACT 纵切。
4. 完成 LAUNCH_SCOUT INTENT 纵切。
5. 再逐类迁移其他命令。

---

## 十九、执行记录（2026-09-19）

| Phase | 内容 | 状态（Commit） |
|---|---|---|
| S5.0 | Order/OrderResult/OrderEvent 契约；七状态机；SET_COURSE/LAUNCH_SCOUT 参数表；旧流程迁移映射（其余命令保留旧路径） | ✅ 3247a56 |
| S5.1 | 类型化参数校验；roster 岗位路由（无责任岗位不能签发）；冲突检查（不静默覆盖/FLASH 不可绕过/supersede） | ✅ 3247a56 |
| S5.2 | 自然语言草稿（确定性解析；多动作拆分；字段不猜；绝不执行；LLM 接入点已留） | ✅ 3247a56 |
| S5.3 | SET_COURSE EXACT 纵切（表单→签发→S2 传达→Pipeline 激活→执行→报告回传）；实况浏览器验证 | ✅ 3247a56 / 432d0f7 |
| S5.4 | LAUNCH_SCOUT INTENT 纵切（送达→PENDING_APPROVAL+方案→批准→放飞；shortfall→partial） | ✅ 3247a56 |
| S5.5 | 取消/取消太迟拒绝/superseded_by/旧单历史完整保留 | ✅ 3247a56 |
| S5.6 | ISSUE ORDER 类型化面板（目录驱动/意图必填/二次确认/409 冲突处置）+ LOG 订单视图 + reported/status 分离 + D16 收口（执行事实不直出通知） | ✅ 3247a56 / 432d0f7 |

规格：`docs/design/S5_ORDER_SYSTEM.md`；测试：`tests/test_orders_system.py`（25，含同种子回放）。
边界实录：S2 独占传达（kind=order/report 电文绕过收报室，由 orders 步骤经 S2 服务送达）；
丢包时 Order 停在 ISSUED 永不 ACTIVE；无自动重发；cost_policy 全程 None 占位，未新增任何 AP 扣减。
截图：`docs/reports/s4-s5/s5-issue-order-1440x900.png`、`s5-coral-chart-1280x720.png`。
