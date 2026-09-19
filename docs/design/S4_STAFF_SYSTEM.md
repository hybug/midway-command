# S4 参谋班子与关系系统规格（S4_STAFF_SYSTEM）

> 状态：**现行规格**（Phase S4.0 产出，随实施阶段同步更新）
> 创建日期：2026-09-19
> 上级计划：`docs/plans/s4-staff-relations-system-plan.md`（执行契约）
> 长期路线图：`docs/plans/gameplay-system-roadmap.md`
> 代码锚点：`src/staff/`（models / roster / service / hooks）
> 史实依据：`docs/reference/CORAL_SEA_COMMAND_ROSTER.md` + `docs/reference/coral-sea/`

---

## 一、目的与边界

S4 定义「谁能接触 commander、报告如何逐级上呈、核心参谋何时主动提醒」。

核心原则：**直接沟通名单由战区与日期的史实配置决定；其他人员按指挥链上呈。**

- S3 认知层管判断内容；S4 沟通层管谁能说、何时说、通过什么渠道、是否已送达。
- S4 不读取 `actual_enemy`，不改变判断正确率/evidence_fit/候选选择（§八边界）。
- 主动提醒不直接改变舰队状态（D7）；普通聊天不产生正式状态（AS.1/R1 已封）。

## 二、数据对象（src/staff/models.py）

| 对象 | 关键字段 | 载体 |
|---|---|---|
| CommanderContactChannel | actor_id / display_name / contact_permission / can_be_summoned / can_initiate / evidence_grade / source_ids | theaters/<id>/roster.json（静态） |
| CommanderNotice | id / actor_id / topic / priority(routine·urgent·flash) / notice_reason(固定六枚举) / state(open·acknowledged·deferred·resolved·expired) / cooldown_until / escalated | `state.staff_notices`（运行态） |
| ChainReport | id / origin_actor_id / route / current_holder_id / next_holder_id / source_type·source_id / state(in_chain·delivered·deferred·closed) / annotations | `state.staff_chain_reports`（运行态） |
| DossierSummary | actor_id / status_line / current_focus / recent(≤2) | 派生（/staff/roster + service.dossier_summary） |

## 三、运行名册（roster.json）

- 位置：`theaters/<id>/roster.json`；珊瑚海由 `CORAL_SEA_COMMAND_ROSTER.md` 派生（S4.0 冻结）。
- fail-fast 校验（src/staff/roster.py）：权限语义矛盾（NO_INITIATIVE 却可主动等）拒绝加载。
- 无 roster.json 的战区回退 MIDWAY_PROVISIONAL（active=False：S4 触发器不启用）。
- 纪律：UNKNOWN 证据等级人物 display_name 必带「（职务名）」；CONFLICTED 不入运行配置；
  校验器 `tools/validate_coral_sea_data.py` 与 `tests/test_coral_sea_reference_data.py` 双重把关。

## 四、指挥链上呈（service.file_chain_report / process_staff_step）

- 路由解析：origin 角色 → roster.chain_of_command BFS 至 COMMANDER；route=沿途 actor。
- Pipeline 步骤 `process_staff`（order 55）：每 tick 前进一跳；到 COMMANDER 即 DELIVERED。
- 纪律：来源不丢（source_type/source_id/origin 保留）；批注只追加不改写原文；
  未送达报告不出现在 /staff/reports；每跳时间在 history 留档。

## 五、主动提醒（service.raise_notice）

- 固定六理由：NEW_EVIDENCE / DECISION_REQUIRED / RISK_WARNING / OPPORTUNITY /
  REPORT_ESCALATION / CLARIFICATION_NEEDED。性格只影响表达，不创造理由。
- 规则：can_initiate 白名单（越级 PermissionError）；同 actor 同时只一个 open；
  同 topic 不重建；defer 进 60min 冷却（设计值）；同事项可升级一次优先级。
- 处置动作（固定枚举）：acknowledge（接见）/ defer（暂缓）/ dismiss（忽略）/ close（关闭），
  全部写 intel_audit 留档。
- 确定性业务钩子（hooks.py）：简报呈报→NEW_EVIDENCE；标图待批→DECISION_REQUIRED；
  批准上图→OPPORTUNITY；冲突登记→RISK_WARNING；加急报告送达→REPORT_ESCALATION；
  S5 Order 歧义→CLARIFICATION_NEEDED。roster 未激活时全部静默。

## 六、API 与 UI

- `GET /staff/channels`（S4.1 名单+活动通知）、`GET /staff/notices`、
  `POST /staff/notices/{id}/{action}`、`GET /staff/visit-events`（STAFF_VISIT 源）、
  `GET /staff/reports`（仅 delivered）。
- STAFF 工作台：名册下新增「直接沟通名单（史实配置）」区（权限标签 当面/无线电/链上/报告/被动）
  与「主动提醒板」（接见/暂缓/忽略/关闭，data-notice-action 固定动作）。
- s4Adapter：fetchVisitEvents 接 /staff/visit-events；fetchConflictDossiers 恒空（D8 延期）。

## 七、测试与实施记录

`tests/test_staff_system.py`（21 用例）+ `tests/test_coral_sea_reference_data.py` 名册纪律。

| Phase | 内容 | 状态（Commit） |
|---|---|---|
| S4.0 | 史实考证 + 运行名册 | ✅ caed964（考证/数据）+ 2d43421（roster.json） |
| S4.1 | CommanderContactChannel + 名单 UI | ✅ 2d43421 |
| S4.2 | ChainReport 指挥链上呈 | ✅ 2d43421 |
| S4.3 | CommanderNotice + 去重/冷却/升级 + STAFF_VISIT | ✅ 2d43421 |
| S4.4 | DossierSummary 极简档案 | ✅ 2d43421 |
| S4.5 | 珊瑚海 5/7 场景验收 + 越级阻断 + 聊天不改状态 | ✅ 2d43421 |

截图：`docs/reports/s4-s5/s4-staff-desk-1440x900.png`。

## 八、延期（不属于 v0）

参谋互评、ReviewNote、ConflictDossier、玩家转述（入口已删）、派系、抗命、关系数值。
