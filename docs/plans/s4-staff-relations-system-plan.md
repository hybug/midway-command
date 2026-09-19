# S4 核心参谋沟通系统实施计划（s4-staff-relations-system-plan）

> 状态：**待执行（前置整改完成后启动）**
> 创建日期：2026-09-19
> 上级路线图：`docs/plans/gameplay-system-roadmap.md`
> 前置计划：`docs/plans/action-semantics-remediation-plan.md` Phase AS.0–AS.1
> UI 契约：`docs/plans/s8-ui-ux-system-plan.md`
> 首批场景：珊瑚海 1942-05-07 / 05-08

---

## 一、目标

让指挥官通过史实配置确定的沟通名单与参谋及指挥官联系，其余人员的信息沿指挥链上呈。

S4 v0 不是关系管理，也不是参谋社交网络。它只解决：

- 哪些史实人物能直接找 commander。
- commander 可以主动联系或召见哪些人。
- 其他报告如何逐级上呈。
- 核心参谋何时可以主动提出注意事项。
- STAFF 档案如何保持极简。

核心原则：

> **直接沟通名单由战区与日期的史实配置决定；其他人员按指挥链上呈。**

---

## 二、确认的设计原则

| 编号 | 原则 |
|---|---|
| D1 | v0 不建立好感度、信任值或关系雷达图 |
| D2 | 直接沟通名单由史实确认，数量和岗位不预先固定 |
| D3 | 未列入直接沟通名单的人员和单位不能主动直接联系 commander |
| D4 | 下级报告通过指挥链逐级上呈 |
| D5 | 名单内人员主动提醒由确定性事件触发，不能随机生成 |
| D6 | 同一核心参谋同时只保留一个未处理主动事项 |
| D7 | 主动事项不能直接改变舰队状态 |
| D8 | v0 不实现玩家转述、参谋互评、关系网、派系或分歧案卷 |
| D9 | STAFF 只显示核心参谋，其他角色只通过报告与记录出现 |
| D10 | 普通聊天不改变正式状态或产生主动事项 |
| D11 | 核心参谋名单必须经过史实考证 |
| D12 | 未确认人物只使用职务名，禁止凭印象补人 |
| D13 | 不同位置使用符合史实的通信渠道 |
| D14 | LLM 只能组织已触发事项和正式判断的表达 |
| D15 | 所有正式操作沿用固定动作与范围选项 |

---

## 三、S4 v0 范围

### 负责

- 史实核心参谋编制。
- commander 直接沟通名单与权限。
- 下级报告的指挥链上呈。
- 名单内人员主动提醒。
- 极简参谋档案。
- 与 S3 JudgmentTask / JudgmentResult 的连接。
- 与 S8 STAFF / COMMS / LOG 的连接。

### 不负责

- 参谋间自由通信。
- 玩家代为转述。
- 参谋互评和正式复核流程。
- 关系数值和人物政治。
- 派系、结盟或抗命。
- 自动改变舰队命令。
- 完整社交模拟。

---

## 四、直接沟通权限

直接沟通名单由 scenario roster 决定，数量不固定。每个联系人必须同时满足：

1. 史实上确有相应高级职务。
2. 有向 commander 呈报的职权。
3. 在当时的物理位置和通信条件下能够接触 commander。

建议权限类型：

```text
DIRECT_IN_PERSON   同舰，可当面呈报
DIRECT_RADIO       不同舰，可通过 TBS / 无线电联系
CHAIN_ONLY         只能逐级上呈
REPORT_ONLY        只能发送书面报告
NO_INITIATIVE      只能被动应答
```

席位数量、职务和权限均由 scenario roster 配置，不能只根据军衔决定。

不同舰艇上的高级军官即使军衔高，也可能只能是 `DIRECT_RADIO`，不能表现为走进旗舰舱室。

---

## 五、核心数据对象

## 5.1 CommanderContactChannel

```text
actor_id
name
rank
role
flagship
contact_permission
can_be_summoned
can_initiate
active_notice_id
```

## 5.2 CommanderNotice

```text
id
actor_id
topic
priority            routine / urgent / flash
source_ref
notice_reason       fixed enum
state               open / acknowledged / deferred / resolved / expired
created_at
cooldown_until
```

`notice_reason`:

```text
NEW_EVIDENCE
DECISION_REQUIRED
RISK_WARNING
OPPORTUNITY
REPORT_ESCALATION
CLARIFICATION_NEEDED
```

## 5.3 ChainReport

```text
id
origin_actor_id
current_holder_id
next_holder_id
source_type
source_id
summary
priority
state               in_chain / delivered / deferred / closed
at
```

## 5.4 DossierSummary

```text
actor_id
status_line
current_focus
recent[]
```

`recent` 最多两项。

---

## 六、指挥链上呈

默认流向：

```text
下级单位 / 舰长 / 专业参谋
  → 参谋长或所属高级指挥官
  → commander
```

规则：

- 所有正式报告保留原始来源。
- 上呈时可以附加上级批注，但不能改写原文。
- commander 只看到已经送达或明确呈报的内容。
- 下级参谋不能通过 LLM 绕过链条建立 `CommanderNotice`。
- 普通舰长只报告本舰事务。
- 情报和作战参谋的报告先进入核心参谋筛选。
- 通信官只负责收报与路由。
- 链中每个持有人和状态变化均记录时间。

---

## 七、名单内人员主动提醒

每次提醒必须来自固定业务理由：

- `NEW_EVIDENCE`：新证据影响现有判断或行动。
- `DECISION_REQUIRED`：需要 commander 做决定。
- `RISK_WARNING`：发现新的舰队或任务风险。
- `OPPORTUNITY`：出现明确攻击或行动窗口。
- `REPORT_ESCALATION`：下级报告达到必须上呈级别。
- `CLARIFICATION_NEEDED`：commander 命令或意图存在关键歧义。

性格只影响表达方式和紧迫感，不能创造主动理由。提醒必须关联具体证据、判断、报告或命令。


v0 使用简单规则，不做完整关系引擎。

触发条件：

```text
高优先级问题
+ 属于核心参谋职责
+ 尚未处理
+ 无有效冷却
```

优先级：

```text
FLASH     立即建立或升级提醒
URGENT    当前简报周期内处理
ROUTINE   进入下一次例行简报
```

规则：

- 同一 actor 同时只能有一个 open notice。
- 同一 topic 未解决时不重复创建。
- 主动提醒可被接见、暂缓、忽略或解决。
- 暂缓后进入冷却。
- 同一事项可升级一次优先级。
- 触发可以先用固定场景规则，不引入复杂概率模型。
- LLM 只负责把 notice 演绎成符合史实的沟通内容。

---

## 八、S3 与 S4 职责边界

```text
S3 认知层
  证据、候选判断、错误、置信度、判断记忆

S4 沟通层
  谁能说话、何时说、通过什么渠道说、是否已送达
```

- CommanderNotice 只决定是否提醒以及紧迫程度。
- CommanderNotice 不改变判断正确率、`evidence_fit` 或候选选择。
- commander 对判断的正式反馈进入 S3 判断记忆。
- 接见、暂缓或忽略提醒只改变沟通状态。
- 指挥链批注不得改写原始报告或正式判断。
- 主动提醒若需要新结论，必须创建新的 JudgmentTask。
- S4 不读取 `actual_enemy`，不能根据隐藏结果触发提醒。

## 八、STAFF 界面

STAFF 只列出 scenario 定义的 commander 直接沟通名单。

每名联系人显示：

```text
姓名 / 军衔 / 职务
当前状态
当前关注
最近两次互动
```

操作只有：

- 交谈。
- 要求正式判断。
- 回复主动提醒。
- 暂缓或关闭提醒。

不显示：

- 好感度。
- 信任值。
- 关系图。
- 其他参谋对 commander 的隐藏评价。
- 复杂关系事件历史；完整记录进入 LOG。

---

## 九、史实考证前置任务

进入 S4 前必须执行。

### 目标文档

```text
docs/reference/CORAL_SEA_COMMAND_ROSTER.md
```

### 必须记录

```text
姓名
军衔
职务
所属舰艇 / 编队
旗舰位置
指挥关系
通信渠道
能否主动接触 commander
史料依据
证据等级
备注
```

### 证据等级

```text
CONFIRMED   一手行动报告、官方编制表或官方人物记录直接确认
PROBABLE    多个可靠二手来源一致，缺少一手直接证明
UNKNOWN     无可靠来源，只能使用职务名
CONFLICTED  来源冲突，不进入运行配置
```

### 规则

- 一手行动报告和官方编制记录优先。
- 单来源人物标 PROBABLE。
- 未确认姓名必须使用职务名。
- 不根据影视、小说或游戏补全人物。
- 不把战后职务倒推至珊瑚海当天。
- 职务变化必须按日期标注。
- 物理位置与通信能力分别考证。
- 考证完成后才能建立 `CommanderContactChannel`，数量不预设。

---

## 十、实施阶段

## Phase S4.0：史实参谋编制与沟通名单考证

- 完成 `CORAL_SEA_COMMAND_ROSTER.md`。
- 确定核心参谋编制、直接沟通名单、位置、权限和通信渠道。
- 评审后生成运行 roster。

## Phase S4.1：Commander 联系名单

- 实现 `CommanderContactChannel`。
- STAFF 只显示史实配置的沟通名单。
- 接入现有 S3 正式判断。
- 保持每名核心参谋独立会话。

## Phase S4.2：指挥链上呈

- 实现 `ChainReport`。
- 下级报告按职责和指挥关系自动流转。
- 保留来源、上级批注和送达状态。
- 未送达 report 不暴露给 commander。

## Phase S4.3：主动提醒

- 实现 `CommanderNotice`。
- 实现优先级、去重、冷却和升级。
- 接入 S8 `STAFF_VISIT`。
- 实现接见、暂缓、忽略和关闭。

## Phase S4.4：极简档案

- 实现 DossierSummary。
- 只显示身份、状态、关注和最近互动。
- 接入 LOG 的完整事件记录。

## Phase S4.5：验收

- 珊瑚海 5 月 7 日、8 日场景。
- 验证沟通名单权限和指挥链。
- 验证非核心角色不能越级。
- 验证普通聊天不改变状态。
- 验证未确认姓名不会被硬编码。

---

## 十一、测试

### 单元测试

- CommanderContactChannel 权限。
- ChainReport 状态机。
- ChainReport 来源不丢失。
- 未送达内容不可见。
- CommanderNotice 去重和冷却。
- 非核心角色不能创建 notice。
- DossierSummary 只含四个字段。
- 未考证人物不能进入 roster。

### 集成测试

- 舰长报告沿指挥链到达 commander。
- 参谋长筛选并附加批注。
- 核心参谋请求 commander 注意。
- commander 接见、暂缓、忽略和关闭均留档。
- 普通参谋不能直接触发 STAFF_VISIT。
- S3 判断仍可正常发起和展示。
- S8 STAFF / COMMS / LOG 数据一致。

### 历史验收

- 每个核心人物都有来源和证据等级。
- 直接沟通权限符合职务、位置和通信条件。
- 未确认人物使用职务名。
- 不出现虚构参谋或战后职务倒推。

---

## 十二、验收标准

1. STAFF 只显示史实配置的直接沟通名单。
2. 其他人员只能沿指挥链上呈。
3. 下级不能越级主动联系 commander。
4. 名单内人员主动提醒有确定来源。
5. 主动事项不重复轰炸。
6. 主动行为不直接改变舰队状态。
7. 参谋编制和直接沟通名单完全依据考证文档。
8. 未确认人物只使用职务名。
9. 极简档案只有身份、状态、关注和最近互动。
10. v0 不出现关系数值、互评、转述、派系或分歧案卷。
11. 普通聊天不改变正式状态。
12. 所有报告与操作可追溯、可回放。

---

## 十三、暂缓到后续版本

以下能力不属于 S4 v0：

- 参谋之间的关系。
- 跨 NPC 互评。
- 正式复核流程。
- ConflictDossier。
- 玩家转述和参谋间自由通信。
- 派系、结盟和政治冲突。
- 抗命与独走。
- 完整主动性评分模型。

只有 v0 试玩证明现有沟通结构不足时，才逐步引入这些模块。

---

## 十四、依赖

- `AS.0–AS.1` 必须先完成。
- S3 JudgmentTask / JudgmentResult / commander feedback 必须可读。
- S8 STAFF / COMMS / LOG 接口必须稳定。
- S5 负责后续命令执行和抗命，不混入 S4 v0。
- S4 不直接读取 `actual_enemy`；只能使用角色可见信息。

---

## 十五、下一步

1. 完成操作语义整改 AS.0–AS.1。
2. 执行 S4.0 史实考证。
3. 评审 `CORAL_SEA_COMMAND_ROSTER.md`。
4. 冻结参谋编制、直接沟通名单与通信权限。
5. 再实现核心参谋频道、指挥链上呈和主动提醒。
