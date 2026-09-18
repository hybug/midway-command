# S3 参谋认知与判断系统规格（S3_COGNITION_SYSTEM）

> 状态：**现行规格**（Phase S3.0 产出，随实施阶段同步更新）
> 创建日期：2026-09-18
> 上级计划：`docs/plans/s3-staff-cognition-system-plan.md`（执行契约）
> 长期路线图：`docs/plans/gameplay-system-roadmap.md`
> 代码锚点：`src/cognition/`（contracts / models / engine / roster / context / …）

---

## 一、目的与边界

S3 定义参谋如何理解证据、形成判断、表达置信度和提出建议，并保证认知过程
可解释、可回放、可调参、可归因。认知链：

```text
EvidenceView → JudgmentTask → Candidate Hypotheses → evidence_fit
  → ActorProfile + Context + JudgmentDice → chosen_hypothesis
  → error semantics + confidence → JudgmentResult
  → LLM persona rendering → JudgmentMemory
```

边界：电文收发与证据权限属 S2；命令执行属 S5；战斗结算属 S6；参谋关系属 S4；
胜负复盘属 S7。判断建议不直接改变舰队状态（D5）。

## 1.1 对象谱系表

| 对象 | 产生者 | 产生时机 | 基于什么 | 载体 |
|---|---|---|---|---|
| JudgmentTask | 指挥官要求 / 工作项 / 参谋主动 | 需要判断时 | 问题 + 权限内证据集 + 上下文版本 | `state.judgment_tasks` |
| Hypothesis | LLM（候选生成） | 引擎执行中 | EvidenceView + 人物 prompt | 结果携带（规范化后） |
| EvidenceFit | 规则引擎 | 引擎执行中 | Hypothesis × EvidenceView（纯函数） | 审计记录 |
| JudgmentResult | 规则引擎 | 恰好一次 JUDGMENT_CHECK 后 | 候选评分 + 骰子偏差 + plausible_set | `state.judgment_results` |
| 人物化报告 | LLM（persona rendering） | 结果确定后 | JudgmentResult + 人物 prompt（不得改写结构化结论） | assessment.narrative / STAFF |
| JudgmentMemory | 规则引擎 | 结果落档时 | 自身结果（D8 按 actor 隔离） | `state.judgment_memories` |
| JudgmentAuditRecord | 规则引擎 | 与结果同时 | 公式版本/参数快照/候选评分/骰子/种子 | `state.judgment_audits` |

## 1.2 强制约束（计划 §二 D1–D20）

1. 判断以 `JudgmentTask → JudgmentResult` 为单位，聊天消息不直接产生持久判断（D1）。
2. LLM 生成候选与人物化文本；规则层负责 evidence_fit、候选选择、错误严重度（D2）。
3. 每次判断恰好一次 `JUDGMENT_CHECK`（D3）；骰子结构化输出进 CheckRecord 可回放。
4. 判断保留人物归属，不生成系统共识（D4）。
5. v0 只形成判断和建议，不执行作战状态变更（D5）。
6. NPC 只读按角色裁剪的 EvidenceView（D6，执行点 `context.actor_evidence_views`）。
7. NPC 默认不读其他 NPC 的私有 JudgmentMemory（D7）；信息流经玩家转述或正式简报分发。
8. 同一稳定键重复请求返回已有结果，禁止重骰（D9）。
9. `actual_enemy` 不进入实时判断，只用于战后复盘（D11）。

---

## 二、与 S2 JudgmentPolicy 的迁移方案

| S2 现状 | S3 处理 |
|---|---|
| `src/intel/policy.py` MechanicalPolicy（S2.3 纵切降级路径） | **保留不动**：S2 管线（run_intelligence_cycle）继续用它产出 NPCAssessment/IntelBrief/PlotProposal；S3 不偷换 S2 默认策略（回归测试锁定） |
| `src/intel/judgment.py` EvidenceView / ActorProfile / JudgmentDice | S3 复用 EvidenceView 与 JudgmentDice；S3 ActorProfile（五维校验）取代开放 dict 版本用于判断装配 |
| JUDGMENT_CHECK | S2 管线内的检定保持；S3 引擎执行时**另掷且恰好一次**（D3），骰子同落 RNGService/CheckRecord |
| 珊瑚海情报参谋研判 | S3.6 纵切：简报链（S2）产出后，三名参谋各自经 S3 引擎形成判断；intel_officer 的 S2 assessment 与 S3 JudgmentResult 并存、以 evidence_ids/task 关联 |

---

## 三、珊瑚海 v0 班子与参数理由（M3.1.5/M3.1.6）

| actor | 类型 | 域 | competence | risk | imagination | initiative | autonomy | 参数理由（设计值，非历史断言） |
|---|---|---|---|---|---|---|---|---|
| fletcher | 玩家 | command | 6 | 5 | 4 | 6 | 8 | 决心者不进引擎；参数仅档案登记 |
| fitch | NPC | air | 7 | 5 | 4 | 6 | 5 | 航空兵出身、攻击果断（5/7 率先放飞建议），舰队安全上不冒进 |
| tf17_intel | NPC | intelligence | 6 | 3 | 3 | 4 | 3 | 谨慎条件式分析（与中途岛 intel_officer 同族）；5/7 误报主因是观测端 contact pad 错误而非参谋乐观 |
| tf17_ops | NPC | operations | 6 | 4 | 3 | 5 | 4 | 关注舰队风险与执行可行性，偏保守但不怯战 |

- 职务名说明：TF17 情报参谋与作战参谋一手报告未载可入档姓名，按计划用职务名，不虚构。
- 权限矩阵见 `src/cognition/roster.py::_PERMISSIONS`；测试 `test_permission_matrix_matches_plan_section_nine` 锁定 §九 可见信息。
- 约克城/列克星敦舰长：计划标注「后续」，v0 名册不含。

## 3.1 角色证据权限（D6 执行点）

```text
tf17_intel : raw=[INTEL_OFFICER]                    （S2 账本权限内现行有效证据）
fitch      : via=[briefed, approved_plots]          （已呈报简报引用的证据 + 已批准标图引用）
tf17_ops   : via=[approved_plots, briefed]          （同上，读取顺序不同）
fletcher   : via=[inbox, briefs_submitted, approved_plots]（=S2 PLAYER_VISIBLE_SCOPES）
全体       : 禁 actual_enemy / internal_truth_ref / 他人私有 JudgmentMemory
```

---

## 四、一手史料与事实边界（S3.0 登记）

| 键 | 文献 | 已核对的关键史实 |
|---|---|---|
| TF17_REPORT | [Commander Task Force 17 — Battle of the Coral Sea, May 4–8](https://www.ibiblio.org/hyperwar/USN/rep/Coral/TF17.html) | 5/7 向东北搜索因恶劣天气未完成；一架向西北搜索的侦察机报告米西马岛以北「两艘航母四艘巡洋舰」；据此放飞攻击群；返舰后发现 contact pad 使用错误（飞行员实际未见航母）；随后陆军飞机报告米西马附近航母群，攻击群被引导击中祥凤号。5/8 岸基机未找到翔鹤/瑞鹤，黎明 360° 搜索；列克星敦侦察机报告两航母四重巡多驱逐；报告由「航向 006°、120 海里、15 节」修正为「真方位 028°、175 海里」；09:08 Fitch 任 OTC |
| YORKTOWN_ACTION_REPORT | [USS Yorktown — Coral Sea Action Report](https://www.ibiblio.org/hyperwar/USN/ships/logs/CV/cv5-Coral.html) | 约克城放飞时序与舰载机作业、损失记录 |

事实边界：人物档案（display_name/role/duty_boundary）与纵切事件只允许引用上述
已登记史料；引擎参数（attributes）是设计值并在 §三登记理由，不冒充史实。

---

## 五、实施阶段对照（计划 §十四）

| Phase | 内容 | 状态（Commit） |
|---|---|---|
| S3.0 | 契约与战区班子 | ✅ 1a1a4df（tests/test_cognition_contracts.py） |
| S3.1 | 候选与 evidence_fit（candidates.py/evidence_fit.py） | ✅ bacbda8 |
| S3.2 | 判断公式与骰子（formula.py/rule_engine.py/errors.py+置信度） | ✅ 336d7db |
| S3.3 | 错误、置信度与建议（建议域转移/认知-事实误差分离） | ✅ d949158 |
| S3.4 | 判断记忆与修订（memory.py 召回/锚定/supersedes/反馈） | ✅ 15b1f5d |
| S3.5 | LLM 候选生成与人物化表达（persona.py+refusal 路径+降级） | ✅ 54a0ab1 |
| S3.6 | 珊瑚海五月七日纵切（scenarios/coral_may7.py） | ✅ a254ba6 |
| S3.7 | 珊瑚海五月八日扩展（scenarios/coral_may8.py+revision_comparison+OTC） | ✅ 3679ce5 |
| S3.8 | 调参、评估与界面 | ◐ UI/认知链展示已由 S8 UI.4/UI.5 落地；统计方向评估已建（S3.2 方向测试）；权重冻结与真实 LLM 行为评估待接入真实 LLM |
