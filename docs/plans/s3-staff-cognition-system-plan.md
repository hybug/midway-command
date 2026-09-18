# S3 参谋认知与判断系统实施计划（s3-staff-cognition-system-plan）

> 状态：**现行专项实施计划**
> 创建日期：2026-09-18
> 上级路线图：`docs/plans/gameplay-system-roadmap.md`
> 上游依赖：`docs/plans/s2-intelligence-system-plan.md`、`docs/design/S2_INTEL_SYSTEM.md`
> 当前主攻：S3 参谋认知与判断系统
> UI 契约：`docs/plans/s8-ui-ux-system-plan.md`
> 首批场景：珊瑚海 1942-05-07

---

## 一、S3 的目标

让参谋基于自己可见的证据形成独立判断、建议和误差，并确保这些认知过程可解释、可回放、可调参、可归因。

S3 解决的核心问题不是“NPC 能不能聊天”，而是：

- 他看到什么。
- 他如何理解。
- 他是否形成判断。
- 他的判断是否正确。
- 如果他错了，错在什么地方、错得多严重。
- 他为什么提出这个建议。
- 哪些新证据会让他改变判断。
- 他是否承认证据不足或越出职责。

统一认知链：

```text
EvidenceView
  → JudgmentTask
  → Candidate Hypotheses
  → evidence_fit
  → ActorProfile + Context + JudgmentDice
  → chosen_hypothesis
  → error semantics + confidence
  → JudgmentResult
  → LLM persona rendering
  → JudgmentMemory
```

---

## 二、已经确认的设计原则

| 编号 | 原则 |
|---|---|
| D1 | S3 以 `JudgmentTask → JudgmentResult` 为基本单位，不以聊天消息为单位 |
| D2 | LLM 生成候选判断，规则引擎计算 `evidence_fit` |
| D3 | 每次判断只执行一次 `JUDGMENT_CHECK`，人物参数分配偏差影响 |
| D4 | 所有判断必须保留人物归属，不生成系统共识 |
| D5 | S3 v0 只形成判断和建议，不执行作战状态变更 |
| D6 | NPC 只能读取按角色裁剪的证据，不能读取完整 `GameState` |
| D7 | NPC 默认不能读取其他 NPC 的判断，信息流经玩家转述或正式简报分发 |
| D8 | 每名 NPC 拥有独立 `JudgmentMemory` |
| D9 | 同一问题、同一证据和同一处境返回稳定判断，禁止重复提问重骰 |
| D10 | 记忆只由自身判断、指挥官反馈、新证据和实际可观察结果更新 |
| D11 | `actual_enemy` 不进入实时判断，只用于战后复盘 |
| D12 | 错误分为“认知错误”和“事后事实错误” |
| D13 | 使用证据兼容集合，避免把合理的不确定判断判成错误 |
| D14 | 错误类型和严重度由结构化语义距离计算，不由骰子直接指定 |
| D15 | v0 使用一个通用 `JudgmentEngine`，不以 NPC 姓名拆分引擎 |
| D16 | 人物差异来自 ActorProfile、权限、记忆、prompt 和少量领域策略 |
| D17 | v0 只启用 competence / risk_tolerance / imagination / initiative / autonomy |
| D18 | skepticism / confidence_bias / stress_sensitivity 仅登记为候选维度 |
| D19 | 最终维度数量和权重通过公式、消融和历史案例确定 |
| D20 | 第一条纵切使用珊瑚海 1942-05-07 的米西马方向错误接触事件 |

---

## 三、系统边界

### S3 负责

- 结构化判断任务。
- 候选判断的生成与规范化。
- 证据适配评分。
- 人物参数的公式化行为。
- 单次判断检定。
- 判断选择、偏差和错误严重度。
- 三档置信度。
- 建议、反证和改变判断的条件。
- 判断记忆与修订。
- 角色内外的判断边界。
- 判断审计、回放和评估。

### S3 不负责

- 电文收发和证据权限本身，属于 S2。
- 作战命令执行，属于 S5。
- 自动改变航向、起飞、攻击或标图。
- 战斗结算，属于 S6。
- 参谋关系、信任和派系，属于 S4。
- 胜负和历史结局，属于 S7。
- 情报 UI 本身，属于 S8。

---

## 四、系统上下文

### 输入

```text
JudgmentTask
EvidenceView[]
ActorProfile
ActorBeliefState
JudgmentMemory[]
当前时间与压力
职责和授权边界
一次 JudgmentDice
```

### 输出

```text
JudgmentResult
  chosen_hypothesis
  plausible_set
  error_type
  error_severity
  confidence_band
  recommendation
  assumptions
  change_my_mind
  refusal_reason
```

### 数据流

```text
S2 Evidence / WorkItem
  → S3 JudgmentTask
  → LLM Candidate Generation
  → S3 Evidence Fit
  → S3 Judgment Formula + Dice
  → S3 JudgmentResult
  → S3 Persona Rendering
  → S2 IntelBrief / NPC Report
  → S7 After Action
```

---

## 五、二级模块

## M3.1 人物模型与职责权限

### 目标

把人物历史、职责、权限和参数装配为判断输入，而不是把完整状态直接注入 prompt。

### 子模块

- `M3.1.1` ActorProfile schema。
- `M3.1.2` 职责领域与任务类型匹配。
- `M3.1.3` 角色证据权限。
- `M3.1.4` 人物历史资料与 prompt 来源。
- `M3.1.5` 战区 NPC 名册。
- `M3.1.6` 领域策略注册表。

### 验收

- 同一任务分给不同角色时，证据包和职责约束不同。
- 人物档案中没有未经史料确认的虚构事实。
- 所有参数和 prompt 版本可追溯。

## M3.2 判断任务与结果协议

### 目标

固定一次判断的输入输出，使 LLM、公式和记忆围绕同一协议工作。

### 子模块

- `M3.2.1` `JudgmentTask` 模型。
- `M3.2.2` 任务类型：assess / predict / recommend / compare / decide。
- `M3.2.3` `JudgmentResult` 模型。
- `M3.2.4` 稳定判断键。
- `M3.2.5` 任务来源与创建者。
- `M3.2.6` 拒绝和未知结果。
- `M3.2.7` 结果序列化与 API 白名单。

### 验收

- 聊天消息不会直接绕过 `JudgmentTask` 形成持久判断。
- 同一稳定键重复请求返回同一结果。
- 任务和结果可定位到具体人物、证据和上下文版本。

## M3.3 候选判断与证据适配

### 目标

让 LLM 提供有角色特色的候选解释，让规则层计算这些解释与证据的吻合度。

### 子模块

- `M3.3.1` `Hypothesis` 数据模型。
- `M3.3.2` 候选数量控制。
- `M3.3.3` 类型、数量、位置、航向、航速预测。
- `M3.3.4` 证据维度适配度。
- `M3.3.5` 证据冲突惩罚。
- `M3.3.6` 证据兼容集合。
- `M3.3.7` 候选去重和规范化。

### 验收

- LLM 不能自行覆盖 `evidence_fit`。
- 无证据维度不参与评分，权重重新归一化。
- 模糊局势可以产生多个合理候选。
- 候选不携带规则侧真值。

## M3.4 判断公式与骰子

### 目标

用有限维度产生稳定、可调、可解释的判断选择。

### 子模块

- `M3.4.1` 五项有效维度的归一化。
- `M3.4.2` evidence weight。
- `M3.4.3` risk bias。
- `M3.4.4` imagination novelty。
- `M3.4.5` 一次 `JUDGMENT_CHECK` 输出。
- `M3.4.6` deviation budget。
- `M3.4.7` 候选评分和选择。
- `M3.4.8` 公式版本和参数记录。

### 验收

- 不使用未记录的随机数。
- 高 competence 平均提高最佳候选选择率。
- 高 risk tolerance 产生稳定的乐观/进攻偏差。
- 高 imagination 产生更多新假设和更大偏差。
- 决定值不能超出配置边界。

## M3.5 错误语义与置信度

### 目标

把“错”定义为相对证据兼容集合的偏离，并与事后实际结果分开。

### 子模块

- `M3.5.1` 目标识别距离。
- `M3.5.2` 数量距离。
- `M3.5.3` 位置距离。
- `M3.5.4` 航向和航速距离。
- `M3.5.5` 最大距离与加权平均。
- `M3.5.6` 认知错误标记。
- `M3.5.7` low / medium / high 三档置信度。
- `M3.5.8` 事后事实误差复盘。

### 验收

- `actual_enemy` 不参与实时错误判定。
- 落在证据兼容集合内的候选不算认知错误。
- 错误类型至少能区分识别、数量、位置、运动。
- 置信度只由 evidence fit、兼容集合和证据强度决定。

## M3.6 判断记忆与修订

### 目标

让 NPC 能坚持、修订或推翻自己的判断，同时避免无原因漂移。

### 子模块

- `M3.6.1` JudgmentMemory 模型。
- `M3.6.2` 相关记忆检索。
- `M3.6.3` 锚定与坚持。
- `M3.6.4` 新证据触发修订。
- `M3.6.5` 指挥官反馈记录。
- `M3.6.6` 版本链和 supersedes。
- `M3.6.7` 未解决假设。
- `M3.6.8` 记忆可见范围。

### 验收

- NPC 不会无条件遗忘或每次重新随机。
- 修订必须引用新证据、反馈或可见结果。
- NPC 不会读取另一个 NPC 的私有判断。
- 旧判断在复盘中仍可查询。

## M3.7 不确定性与职责边界

### 目标

允许参谋承认不知道、证据不足或任务超出职责。

### 子模块

- `M3.7.1` 证据不足状态。
- `M3.7.2` 证据冲突状态。
- `M3.7.3` 职责外任务识别。
- `M3.7.4` 建议转交其他角色。
- `M3.7.5` 拒绝理由。
- `M3.7.6` 高 autonomy 的越权表达边界。
- `M3.7.7` 不把推测自动升级为事实。

### 验收

- NPC 能在没有可靠证据时明确说不知道。
- 职责外判断必须说明限制或转交对象。
- 拒绝和未知不会被强制生成一个自信答案。
- `autonomy` 可以改变表达，但不能绕过授权执行。

## M3.8 建议、反证与改变条件

### 目标

让判断形成对玩家有用的建议，而不是只有结论。

### 子模块

- `M3.8.1` `recommended_action`。
- `M3.8.2` 风险与收益说明。
- `M3.8.3` 替代方案。
- `M3.8.4` 关键假设。
- `M3.8.5` `change_my_mind`。
- `M3.8.6` 建议是否请求授权。
- `M3.8.7` 人物化叙述生成。
- `M3.8.8` 与 S5 要求授权接口对接。

### 验收

- 判断和建议可分离。
- 建议不能自动改变游戏状态。
- NPC 能说明什么新信息会使建议改变。
- 人物化叙述不能修改结构化结论。

## M3.9 判断审计、回放与评估

### 目标

让每次判断可重现、可校准、可定位责任。

### 子模块

- `M3.9.1` 判断审计记录。
- `M3.9.2` 公式版本与权重。
- `M3.9.3` 骰子记录关联。
- `M3.9.4` 确定性回放。
- `M3.9.5` 历史人物行为评估。
- `M3.9.6` 参数消融测试。
- `M3.9.7` 认知错误与事实错误分离报告。
- `M3.9.8` 战后归因数据输出。

### 验收

- 同种子和同输入可得到相同 JudgmentResult。
- 可以解释为何选择某个候选。
- 可以判断错误来自证据、公式、骰子、记忆还是职责限制。
- 可以比较不同人物的判断路径。

---

## 六、核心数据模型

## 6.1 ActorProfile

```text
actor_id
role
domain
attributes:
  competence
  risk_tolerance
  imagination
  initiative
  autonomy
  skepticism?          # 候选，v0 不启用
  confidence_bias?     # 候选，v0 不启用
  stress_sensitivity?  # 候选，v0 不启用
profile_version
persona_prompt_ref
```

## 6.2 JudgmentTask

```text
id
task_type
domain
actor_id
question
question_normalized
evidence_ids
context_version
source
created_at
priority
stable_key
supersedes_task_id
```

## 6.3 Hypothesis

```text
id
text
predicted_class
predicted_count_range
predicted_position
predicted_position_model
predicted_course_range
predicted_speed_range
supporting_evidence_ids
assumptions
aggressiveness              # 规则可计算 [-1, 1]
novelty                     # 规则可计算 [0, 1]
```

## 6.4 EvidenceFit

```text
hypothesis_id
identity_fit
position_fit
count_fit
motion_fit
source_fit
freshness_fit
contradiction_penalty
weighted_fit
```

## 6.5 JudgmentResult

```text
id
task_id
actor_id
chosen_hypothesis_id
plausible_hypothesis_ids
dice_record_id
error_type
error_severity
confidence_band
recommendation
assumptions
change_my_mind
refusal_reason
formula_version
result_version
created_at
supersedes_result_id
```

## 6.6 JudgmentMemory

```text
id
actor_id
task_type
domain
result_id
selected_hypothesis
alternative_hypotheses
evidence_ids
confidence
assumptions
change_my_mind
created_at
status
supersedes_id
commander_decision
observable_outcome_ids
```

## 6.7 JudgmentAuditRecord

```text
id
task_id
result_id
actor_id
formula_version
attribute_snapshot
candidate_scores
plausible_set
dice_record_id
memory_ids
context_version
random_seed
created_at
```

---

## 七、v0 判断公式

### 7.1 归一化

```text
c = competence / 10
r = risk_tolerance / 10
m = imagination / 10
i = initiative / 10
a = autonomy / 10
```

### 7.2 证据适配

每个候选使用固定公式：

```text
fit(H) =
    normalized(
        w_identity  * identity_fit
      + w_position  * position_fit
      + w_count     * count_fit
      + w_motion    * motion_fit
      + w_source    * source_fit
      + w_freshness * freshness_fit
      - w_conflict  * contradiction_penalty
    )
```

没有对应证据的维度不参与，剩余权重重新归一化。

### 7.3 证据兼容集合

```text
max_fit = max(fit(H1), ..., fit(Hn))
plausible_set = {
    H | fit(H) >= max_fit - ambiguity_band
}
```

`ambiguity_band` 由 scenario 配置，默认必须足够允许合理的不确定判断。

### 7.4 候选评分

```text
score(H) =
    evidence_weight * fit(H)
  + risk_weight     * risk_bias(H)
  + imagination_weight * novelty(H)
  + deviation_budget   * persona_affinity(H)
```

v0 初始权重：

```text
evidence_weight   = 0.50 + 0.50 * c
risk_weight       = 0.20 * (r - 0.5)
imagination_weight= 0.15 * m
```

最终系数必须通过消融与珊瑚海历史案例校准，不能在业务代码中散落硬编码。

### 7.5 骰子偏差预算

`JUDGMENT_CHECK` 只生成一次质量等级，映射初始偏差预算：

```text
critical_success  0.00
success           0.05
partial           0.15
failure           0.30
critical_failure  0.45
```

实际预算：

```text
deviation_budget =
  base_budget(level) * (1.20 - c)
```

### 7.6 人物偏好

`persona_affinity(H)` 由规则计算，不采用 LLM 自评分：

- risk_tolerance 高：偏向进攻、乐观、低威胁候选。
- imagination 高：偏向假设更多、新解释和未知补全更多的候选。
- competence 高：提高证据权重并降低偏差预算。
- initiative / autonomy 不改变判断正确率，只影响是否主动发言和表达方式。

### 7.7 置信度

三档置信度由证据决定：

```text
high:
  chosen_hypothesis 位于 plausible_set
  且 fit >= 0.75
  且 evidence_strength >= 0.70

medium:
  chosen_hypothesis 位于 plausible_set
  但 fit < 0.75
  或 fit_margin < 0.15

low:
  证据弱、冲突高、报告陈旧
  或 chosen_hypothesis 不在 plausible_set
```

人物的自信语气由 prompt 控制，不另算 expressed certainty。

### 7.8 错误距离

```text
d_identity
d_count
d_position
d_course
d_speed
```

综合：

```text
D_error =
    0.70 * max(distances)
  + 0.30 * weighted_mean(distances)

error_severity = clamp(D_error, 0, 1)
error_type = 最大距离对应的维度
```

如果 `chosen_hypothesis` 在 `plausible_set` 中：

```text
error_type = none
error_severity = 0
```

---

## 八、判断工作流

## 8.1 新判断

```text
1. 接收 JudgmentTask
2. 计算 stable_key
3. 查询已有 JudgmentResult
4. 若问题、证据和上下文版本未变化，返回已有结果
5. 装载 ActorProfile、BeliefState 和 JudgmentMemory
6. 裁剪角色可见 EvidenceView
7. LLM 生成 1–3 个结构化 Hypothesis
8. 规则层去重并补齐结构化字段
9. 计算每个 Hypothesis 的 evidence_fit
10. 计算 plausible_set
11. 执行一次 JUDGMENT_CHECK
12. 用公式选择候选
13. 计算认知错误、严重度和置信度
14. 生成 JudgmentResult
15. LLM 根据结果和人物 prompt 生成报告
16. 写入 JudgmentMemory 和 AuditRecord
```

## 8.2 新证据到达

```text
新 EvidenceView
  → 找到受影响的 open JudgmentMemory
  → 创建新 JudgmentTask 版本
  → 重新生成候选
  → 重新计算 evidence_fit 和 plausible_set
  → 重新判断
  → 记录修订原因
  → 保留旧结果
```

## 8.3 指挥官反馈

```text
 commander 批准 / 驳回 / 暂缓 / 要求修订
  → 记录 commander_decision
  → NPC 得知反馈
  → 反馈进入后续 JudgmentMemory
  → 不直接改变原 JudgmentResult
```

## 8.4 职责外任务

```text
任务超出角色职责
  → 检查 autonomy
  → 默认给出职责限制并转交正确角色
  → 如人物设定允许，可给明确标注的非正式意见
  → 不进入正式判断书，除非玩家明确要求
```

---

## 九、角色与信息装配

### 珊瑚海 v0 班子

| 角色 | 类型 | 判断重点 |
|---|---|---|
| Frank Jack Fletcher | 玩家 | 最终决心、授权、资源取舍 |
| Aubrey Fitch | NPC | 航空作战、攻击窗口、航空兵协调 |
| TF17 情报参谋 | NPC，暂用职务名 | 证据可靠性、敌人身份和位置 |
| TF17 作战参谋 | NPC，暂用职务名 | 舰队风险、机动、CAP 和执行可行性 |
| Yorktown 舰长 | NPC，后续 | 本舰安全与执行条件 |
| Lexington 舰长 | NPC，后续 | 本舰安全与执行条件 |

### 可见信息

- 情报参谋：完整权限内证据、冲突、来源、历史判断。
- Fitch：情报简报、航空兵状态、距离和天气。
- 作战参谋：已批准标图、舰队位置、航向、CAP 和燃油。
- 玩家：已收电文、已呈报简报、已批准标图和参谋建议。
- 所有角色：禁止 `actual_enemy`。

### 跨 NPC 信息

- NPC 默认看不到其他人的判断。
- 玩家转述必须记录转述者和被转述者。
- 正式简报抄送是明确的分发事件。
- S4 才实现 NPC 互评、争论和主动共享。

---

## 十、珊瑚海 v0 历史基线

### 一手资料

- [Commander Task Force 17 — Battle of the Coral Sea, May 4–8](https://www.ibiblio.org/hyperwar/USN/rep/Coral/TF17.html)
- [USS Yorktown — Coral Sea Action Report](https://www.ibiblio.org/hyperwar/USN/ships/logs/CV/cv5-Coral.html)

### 5 月 7 日场景

已核对的关键史实：

- 向东北方向的搜索因恶劣天气没有完成。
- 一架向西北搜索的侦察机报告米西马岛以北有“两艘航母和四艘巡洋舰”。
- 美军据此放飞攻击群。
- 侦察机返舰后发现 contact pad 使用错误，飞行员实际没有看到航母。
- 随后陆军飞机报告米西马附近有航母群，攻击群被引导并击中祥凤号及其护航舰。

第一纵切的判断问题：

> 这份米西马方向接触报告是否足以支持立即放飞全力攻击？

候选假设：

```text
H1：发现日军主力航母群，应立即全力攻击。
H2：发现的是莫尔兹比港掩护群，甚至包括轻航母。
H3：标图、基准点或通信发生错误，当前报告不可靠。
```

### 5 月 8 日扩展场景

- 因岸基飞机没有找到翔鹤、瑞鹤，无线电情报无法确定敌军在东侧还是西侧，美军黎明实施 360°搜索。
- 列克星敦侦察机报告两艘航母、四艘重巡洋舰、多艘驱逐舰。
- 报告从“航向 006°、120 海里、航速 15 节”修正为“真方位 028°、175 海里”。
- `09:08` Fitch 被指定为 Officer in Tactical Command。

该场景用于验证：

- 多阶段报告到达。
- 基准点变化。
- 从模糊到较精确的位置修订。
- 记忆锚定和重新判断。

---

## 十一、LLM 与结构化引擎的职责

### LLM 负责

- 理解自然语言问题。
- 生成有角色特色的候选解释。
- 补全结构化候选预测和假设。
- 根据最终 JudgmentResult 写成报告。
- 体现人物历史、职责、语气和重点。

### 规则引擎负责

- 权限裁剪。
- 候选规范化和去重。
- evidence_fit。
- plausible_set。
- 人物参数、偏差预算和候选选择。
- 错误类型和严重度。
- 置信度。
- 记忆版本和稳定键。
- 骰子记录和回放。

### LLM 不允许

- 读取权限外证据或 `actual_enemy`。
- 给候选自评分并覆盖 `evidence_fit`。
- 改变已经选定的 `chosen_hypothesis`。
- 将推测自动写成舰队事实。
- 绕过一次 JUDGMENT_CHECK。
- 通过改述规避职责边界。

---

## 十二、接口建议

### 内部接口

```python
class JudgmentEngine(Protocol):
    def assess(self, task: JudgmentTask, context: JudgmentContext) -> JudgmentResult:
        ...
```

### NPC 接口

```text
POST /judgment/tasks
GET  /judgment/tasks/{task_id}
GET  /judgment/results/{result_id}
GET  /npcs/{npc_id}/judgments
POST /npcs/{npc_id}/judgments/{result_id}/reconsider
```

`reconsider` 只有在存在新证据、新反馈或上下文变化时才能创建新版本。

### 禁止暴露

- `actual_enemy`
- 无权限 EvidenceView
- 其他 NPC 的私有 JudgmentMemory
- 候选内部评分中的规则侧真值
- 未选择的候选作为其他角色已知事实

---

## 十三、测试与评估

### 单元测试

- ActorProfile 参数边界。
- Stable key 对相同输入的稳定性。
- 新证据和上下文变化产生新版本。
- Hypothesis schema 校验。
- Evidence fit 权重归一化。
- 无证据维度不会伪造分数。
- Plausible set 边界。
- 单次 JUDGMENT_CHECK。
- 错误距离计算。
- 置信度分档。
- JudgmentMemory 追加和 supersedes。
- 角色权限过滤。
- `actual_enemy` 防泄漏。
- 同种子回放一致。

### 统计性公式测试

- competence 提高时，最佳候选选择率平均上升。
- risk_tolerance 提高时，风险偏向可复现。
- imagination 提高时，候选多样性和偏离度上升。
- initiative 改变主动输出频率，不改变相同任务的正确率。
- autonomy 不改变认知错误率。
- 参数消融能说明维度是否独立有效。

### LLM 行为评估

- 情报参谋不越权制定航空攻击细节。
- Fitch 给出航空判断，不冒充情报来源。
- 作战参谋关注舰队风险，不修改敌情判断。
- NPC 能报告不知道和证据不足。
- NPC 能引用自己的旧判断并解释修订。
- NPC 不读取其他 NPC 的私有判断。
- NPC 不读取 actual_enemy。
- 人物化表达不会改变结构化结论。
- 低能力或高想象人物可以产生错误，但错误来自已记录的公式路径。

### 珊瑚海集成测试

第一条纵切：

```text
米西马方向接触报告
  → 情报参谋评估候选和可靠性
  → Fitch 给出航空建议
  → 作战参谋给出舰队风险
  → 玩家得到三份人物化建议
  → 新报告或勘误到达
  → 各 NPC 按记忆和新证据坚持或修订
  → 战后复盘区分认知错误与事实结果
```

验收必须覆盖：

- 错误报告导致候选偏离。
- 搜索空白区影响 evidence_strength。
- contact pad 错误表现为证据/标图问题。
- Fitch 的建议可以激进，但不能篡改情报。
- 作战参谋可以反对攻击，但由玩家决定。
- 新证据后至少一名 NPC 修订，一名可选择坚持。
- 每名 NPC 的结果可独立回放。

---

## 十四、实施阶段

## Phase S3.0：契约与战区班子

### 任务

- 建立 ActorProfile / JudgmentTask / Hypothesis / JudgmentResult / JudgmentMemory。
- 定义角色权限与 stable key。
- 定义 JudgmentEngine 接口。
- 为珊瑚海增加玩家 Fletcher、Fitch、情报参谋、作战参谋名册。
- 记录一手史料链接与事实边界。

### 验收

- 建模测试全绿。
- 中途岛现有 NPC 行为不回归。
- 珊瑚海名册与可见信息不包含 actual_enemy。

## Phase S3.1：候选与 evidence_fit

### 任务

- 实现 Hypothesis 规范化和去重。
- 实现维度适配评分。
- 实现权重归一化。
- 实现 plausible_set。
- 为候选生成增加 fake LLM 测试。

### 验收

- LLM 无法覆盖 scoring。
- 模糊证据产生多个合理候选。
- 无证据维度不会给出虚假 fit。

## Phase S3.2：判断公式与骰子

### 任务

- 扩展 JUDGMENT_CHECK 到 deviation budget。
- 实现五项有效维度公式。
- 实现候选选择。
- 记录公式版本、权重和输入快照。
- 增加稳定键和防重骰。

### 验收

- 同输入返回同结果。
- 统计测试验证人物参数方向。
- 骰子记录完整且可回放。

## Phase S3.3：错误、置信度与建议

### 任务

- 实现结构化错误距离。
- 实现 error_type / error_severity。
- 实现三档 confidence_band。
- 实现 recommendation、assumptions、change_my_mind。
- 区分 cognition_error 和 factual_error。

### 验收

- 合理候选不会被判错。
- 认知错误不依赖 actual_enemy。
- 置信度和建议可解释。

## Phase S3.4：判断记忆与修订

### 任务

- 实现 JudgmentMemory 检索和更新。
- 实现 commander feedback。
- 实现新证据触发的 task version。
- 实现坚持、修订和 supersedes。
- 实现记忆权限。

### 验收

- NPC 不会忘记或随机漂移。
- 修订必须引用新证据或反馈。
- 旧版本完整保留。

## Phase S3.5：LLM 候选生成与人物化表达

### 任务

- 接入候选生成 Prompt。
- 接入人物 Persona。
- 接入结构化结果到报告渲染。
- 接入拒绝、不知道和职责外表达。
- 保证 LLM 不改写 chosen_hypothesis。

### 验收

- 同类任务下不同人物有稳定差异。
- 人物化输出不越权、不泄密。
- 无 LLM 时可以机械降级，但明确标记非正式玩法路径。

## Phase S3.6：珊瑚海五月七日纵切

### 任务

- 构建米西马方向接触场景。
- 实现 Fletcher / Fitch / 情报参谋 / 作战参谋的独立判断。
- 接入错误 contact pad 事件。
- 接入后续陆军接触报告和判断修订。
- 接入玩家比较和 commander decision。

### 验收

- 四角色职责边界成立。
- 候选判断、公式选择、报告和记忆全链贯通。
- 错误和修订可复现、可归因。

## Phase S3.7：珊瑚海五月八日扩展

### 任务

- 实现多阶段侦察报告。
- 实现基准点变化和真方位修正。
- 比较坚持与修订。
- 接入 Fitch 指挥权变化。

### 验收

- 同一 NPC 能处理多版本证据。
- 新旧判断链完整。
- 玩家可以比较参谋是否因证据合理改变。

## Phase S3.8：调参、评估与界面

### 任务

- 建立人物历史行为评估集。
- 运行参数消融。
- 调整权重并记录版本。
- 在 UI 中区分 NPC 判断、依据、建议和修订。
- 增加战后认知链展示。
- 完成截图和实机验收。

### 验收

- 每项维度均有可证明效果。
- 至少完成 Browning 风格、谨慎情报官、航空指挥官三类行为验证。
- 珊瑚海纵切可在真实 UI 中完整操作。

---

## 十五、总体验收标准

S3 v0 只有在以下条件全部满足时才可宣告完成：

1. 每次判断都以 JudgmentTask 为单位。
2. LLM 只生成候选和叙述，规则层负责评分和选择。
3. 每次判断只使用一次 JUDGMENT_CHECK。
4. 不使用 actual_enemy 实时裁定判断对错。
5. 模糊证据允许多个合理候选。
6. 同问题、同证据、同处境不能重骰。
7. 每名 NPC 有独立判断和记忆。
8. NPC 默认不能读取其他 NPC 的私有判断。
9. 判断、建议和实际执行严格分离。
10. 珊瑚海五月七日纵切完整通过。
11. 五月八日多阶段报告能够触发合理修订。
12. 错误可归因到证据、公式、人物倾向、骰子或职责限制。
13. 全部公式和记忆结果可回放。
14. 现有 S2、UI 和战区功能不回归。

---

## 十六、暂不纳入本计划

- 参谋关系、信任和好感。
- 主动上门、转述和 NPC 互评。
- 自主执行、抗命和越权行动。
- 完整指挥命令系统。
- 战斗结算和真实损失。
- 长期跨战役记忆。
- 最终五维或更多维度的冻结。
- 真人心理建模或开放式情绪系统。

---

## 十七、主要风险

| 风险 | 处理 |
|---|---|
| LLM 候选过于相似 | 人物 Prompt、领域约束和候选数量测试 |
| 公式过于复杂 | v0 只启用五项维度，其他参数后置 |
| 玩家刷骰子 | stable_key 和判断结果缓存 |
| 人物差异被公式抹平 | 人物 Prompt、偏差方向和历史行为评估 |
| 公式压过 LLM 人物感 | 只约束核心结论，文本表达仍归 LLM |
| NPC 越权读取 | 角色证据包在进入 prompt 前裁剪 |
| 误把事实结果当判断标准 | plausible_set + 事后复盘分离 |
| 记忆无限膨胀 | 按 actor/domain/evidence 检索，限制注入条数 |
| 珊瑚海名册与中途岛冲突 | 战区名册和角色槽位装配 |
| 历史细节不足 | 使用一手行动报告，缺证处用职务名而非虚构姓名 |

---

## 十八、下一步

批准本计划后，首先执行 `Phase S3.0`，输出：

- S3 核心数据模型。
- 珊瑚海角色名册与权限矩阵。
- JudgmentEngine 接口。
- Coral Sea 一手资料登记。
- 与 S2 JudgmentPolicy 的迁移方案。
- S3.0 测试清单。

在 S3.0 通过评审前，不开始修改运行时代码。
