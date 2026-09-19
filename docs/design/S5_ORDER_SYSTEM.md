# S5 指挥、授权与执行系统规格（S5_ORDER_SYSTEM）

> 状态：**现行规格**（Phase S5.0 产出，随实施阶段同步更新）
> 创建日期：2026-09-19
> 上级计划：`docs/plans/s5-command-execution-system-plan.md`（执行契约）
> 长期路线图：`docs/plans/gameplay-system-roadmap.md`
> 代码锚点：`src/orders/`（models / service）+ `static/js/ordersDesk.js`
> 动作语义：`docs/plans/action-semantics-remediation-plan.md`（AS.0 契约 `src/actions/contracts.py`）

---

## 一、目的与边界

**S5 结构和控制 Order；S2 传达；S3 判断；S6 执行。**

- 命令端点不得直接修改舰队状态（D9）；所有效果经 Pipeline 步骤 `process_orders`
  （order 57）生效（D10）。
- S2 独占送达/延迟/丢失；S5 无确认超时、无自动重发（D11）；手动重发=签发新 Order。
- AP 成本：`cost_policy` 字段仅占位，不在 S5 解释（D18，AP 专项另议）。

## 二、Order 模型（src/orders/models.py）

```text
Order: id / order_type(SET_COURSE|LAUNCH_SCOUT) / target_refs[] / parameters
       commander_intent_text(必填一等输入，签发后不可改写) / authority_mode(exact|intent)
       priority / responsible_role / responsible_actor_id / source_refs[]
       delivery_message_id / status / reported_status / result(OrderResult)
       cost_policy(占位) / plan(INTENT 方案)
       [规则侧内部] delivery_eta / delivery_will_lose / delivery_confirmed / activated_at
OrderEvent: id / order_id / at / actor_id / event_type(10 枚举) / summary / source_ref
OrderResult: {outcome: success|partial|failed|cancelled, effects[], deviations[],
              reported_at, summary, superseded_by?}
```

状态机（七态，无 PARTIAL/ACKNOWLEDGED 等新增）：

```text
DRAFT → ISSUED → (EXACT) ACTIVE → COMPLETED/FAILED
              → (INTENT) PENDING_APPROVAL → ACTIVE → COMPLETED/FAILED
任何未完成态 → CANCELLED（已执行完成拒绝取消——效果不可回滚）
```

部分完成：`status=COMPLETED` + `result.outcome=partial`（如可用机不足缩减编队）。

## 三、签发与执行链

```text
创建草稿（表单 /orders 或 NL /orders/draft——只产草稿不执行）
→ issue：roster 岗位路由（SET_COURSE→NAVIGATOR→现任者；LAUNCH_SCOUT→AIR_OFFICER）
   + 冲突检查（同实体同维度 ISSUED/ACTIVE 即冲突；FLASH 不可绕过；supersede_ids 显式替代）
   + S2 发报（MessageEnvelope kind=order；通信检定决定延迟/丢失；eta 入档）
→ process_orders（Pipeline）：
   送达 tick：EXACT → ACTIVE（记录 activated_at）；INTENT → PENDING_APPROVAL + 责任参谋方案
   下一 tick：执行（SET_COURSE 转向 / LAUNCH_SCOUT 放飞）→ COMPLETED + S2 报告回传
   报告送达 tick：reported_status ← 真实状态（指挥官可知）
丢失：Order 停在 ISSUED 永不 ACTIVE；无自动重发；玩家手动重发=新 Order+旧单 superseded。
```

## 四、玩家可见状态（D16）

- UI 使用 `reported_status`：draft / issued / pending_approval / cancelled /
  awaiting_report /（报告送达后）completed / failed。
- 内部执行事实（ACTIVE/COMPLETED/FAILED、丢失）不直出管线通知，只能经 S2 报告成为
  指挥官已知；战后复盘（/orders/{id}/audit）同时展示两者。

## 五、API 与 UI

- `GET /orders/catalog`（AvailableAction 契约，UI 不硬编码动作）、`POST /orders`、
  `POST /orders/draft`（NL→草稿）、`GET /orders`（玩家视图）、`POST /orders/{id}`（改 DRAFT）、
  `/issue`（409 冲突带在位命令）、`/cancel`、`/approve`（INTENT）、`/audit`。
- ISSUE ORDER 弹层新增类型化面板（ordersDesk.js）：目录驱动表单 + 意图必填 +
  二次确认签发 + NL 草稿区 + 冲突展示「以新代旧」+ 在案命令（玩家可见状态）。
- LOG ORDERS 视图并入 Order 列表（status_visible）。

## 六、边界与泄漏纪律

- Order/intent/结果不携带 `actual_enemy`；target_refs 只引用玩家可见对象。
- NL 草稿解析（service.draft_from_text）为确定性规则；LLM 生成器为后续接入点
  （接口已留），同样只产草稿、字段不猜（无法解析返回空）。

## 七、测试与实施记录

`tests/test_orders_system.py`（25 用例：schema/状态机/路由/冲突/取消替代/partial/
reported 分离/两纵切/丢包/回放/API e2e）。

| Phase | 内容 | 状态（Commit） |
|---|---|---|
| S5.0 | Order/OrderResult/OrderEvent 契约 + 迁移映射 | ✅ 3247a56 |
| S5.1 | 校验、路由、冲突检查、CREATED/ISSUED/CANCELLED | ✅ 3247a56 |
| S5.2 | NL 草稿（拆分/不猜/不执行） | ✅ 3247a56 |
| S5.3 | SET_COURSE EXACT 纵切 | ✅ 3247a56（实况验证 432d0f7 截图） |
| S5.4 | LAUNCH_SCOUT INTENT 纵切（方案/批准/shortfall→partial） | ✅ 3247a56 |
| S5.5 | 取消/太迟/superseded_by/旧单不可覆盖 | ✅ 3247a56 |
| S5.6 | ISSUE ORDER 面板 + LOG 订单视图 + 玩家/真实状态分离 + D16 收口 | ✅ 3247a56 + 432d0f7 |

截图：`docs/reports/s4-s5/s5-issue-order-1440x900.png`、`s5-coral-chart-1280x720.png`。

## 八、暂缓

SET_SPEED / ADJUST_CAP / RECALL / PLAN_STRIKE 等其余命令类型（走旧路径，逐类迁移）；
自主执行与抗命；AP 成本；LLM 自然语言草稿生成器接入真实 LLM。
