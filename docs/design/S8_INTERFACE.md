# S8 交互与表现系统规格（S8_INTERFACE）

> 状态：**现行规格**（Phase UI.0 产出，随实施阶段同步更新）
> 创建日期：2026-09-18
> 上级计划：`docs/plans/s8-ui-ux-system-plan.md`（执行契约）
> 长期路线图：`docs/plans/gameplay-system-roadmap.md`
> 前端代码锚点：`static/js/{commandDesk,notificationCenter,commsDesk,staffDesk,logDesk,intelBoard}.js`

---

## 一、三层界面结构（1440×900 线框）

```text
┌────────────────────────────────────────────────────────────────────┐
│ TOPBAR 60px  旗·题名 | 日期·时钟 | AP | [ISSUE ORDER] [五工作台灯号] │ L0 全局层
├───────────────────────────────────────────────┬────────────────────┤
│ CHART（常驻海图）                              │ 值班栏 320px        │ L1 值班层
│  海图/舰队/航线/已批准标图/侦察区                │ ·当前工作台+未读角标│
│  ADVANCE/SITREP 控件留在底栏                    │ ·最高优先级事项     │
├───────────────────────────────────────────────┤ ·最近判断/电报     │
│ BOTTOM 56px  仪表盘 | ADVANCE · ISSUE ORDER    │ ·[打开案卷台]      │
└───────────────────────────────────────────────┴────────────────────┘
┌────────────────────────────────────────────────────────────────────┐
│ COMMANDER DESK（L2 案卷台，覆盖海图+底栏，保留 TOPBAR）               │
│  ┌ 工作台内路由：COMMS / INTEL / STAFF / LOG ────────────────────┐  │
│  │ 左：索引/名册        中：正文/对话/操作         右：档案/上下文  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  [ESC] 或 [返回海图] 关闭；打开/切换/关闭不推进时间                  │
└────────────────────────────────────────────────────────────────────┘
z-index 台账：chart/bottom/sidebar ≤10 < campaign-select 50 < commander-desk 60
< notification toast 70 < after-action 90 < vignette/noise 90/91（氛围层最后）
```

- 一级导航=五工作台 `CHART / COMMS / INTEL / STAFF / LOG`（替换旧 NPC 页签；
  NPC 选择下沉 STAFF）。
- CHART=默认态（不开案卷台）；其余四个打开 Commander Desk 并路由到对应区。
- 任意信息最多两次操作可达：L1 点灯（1 次）→ 案卷台正文（第 2 次）。

## 二、通知体系（M8.7）

| 级别 | 来源（后端白名单） | 行为 |
|---|---|---|
| INFO | advance 通知（例行） | 角标 +1，不打断 |
| ROUTINE | 例行工作项 | 角标 |
| URGENT | /intel/work-items urgent；待批提案 | 进待处理队列 |
| FLASH | inbox priority=flash 电文 | 顶部无线电提示条 → 链接 COMMS |
| STAFF_VISIT | S4 适配器（v0 fixture/事件桩） | 请求入舱卡：立即接见/暂缓 |
| CONFLICT | /intel 证据冲突 open | 更新 STAFF/INTEL 角标，不弹窗 |

行为纪律：已读/已处理/暂缓/忽略分别记录；打开案卷台不推进时间；
只有 FLASH 与 STAFF_VISIT 主动打断（toast），其余只更新角标与队列。

## 三、工作台与数据源对照（白名单接口）

| 工作台 | 区块 | 数据源（既有 ✓ / 本计划新增 +） |
|---|---|---|
| CHART | 海图/敌情 | /state（known_enemy=已批准标图视图 ✓）、/routes ✓ |
| COMMS | INCOMING/OUTGOING/TF17·TF11/CORRECTIONS/ARCHIVE | + /intel/inbox 扩展字段（origin_sender/relay_chain/routed_to）；+ /comms/outgoing（决议与命令日志） |
| INTEL | SITREP/BRIEFS/PLOTS/EVIDENCE | /intel/briefs ✓ /intel/plots(+history) ✓ /intel/work-items ✓ + /intel/evidence（已呈报证据链）+ /intel/sitrep |
| STAFF | 名册/对话呈报/极简档案 | + /staff/roster + /judgment/tasks + /npcs/{id}/judgments + /npcs/{id}/judgments/{rid}/reconsider；对话走 /chat ✓ |
| LOG | TIMELINE/ORDERS/AFTER ACTION | + /log/timeline（intel_audit+judgment+decisions 统一时间线）+ /intel/after-action ✓（含 S3 认知/事实误差扩展） |

## 四、跨系统数据契约对照（UI 只消费白名单视图）

### 来自 S3（src/cognition）
- JudgmentTask/JudgmentResult：chosen_hypothesis、plausible_set、confidence_band、
  recommendation、change_my_mind、error_type/severity、refusal_reason、修订链。
- 人物化报告文本（persona 渲染产物）与结构化结论分离展示。
- UI 不重算评分；STAFF 档案不显示 competence 等内部数值（极简档案四行）。

### 来自 S4（未实施——v0 只做前端契约与适配器）
- `StaffVisitEvent {actor_id, topic, at}`：STAFF_VISIT 通知的 payload 形状。
- `RelayRecord {from_actor, to_actor, summary, at}`：玩家转述链条目形状。
- `DossierSummary {actor_id, status_line, current_focus, recent[]}`：极简档案形状。
- `ConflictDossier {conflict_id, parties[], topic}`：分歧案卷形状。
- 适配器 `static/js/s4Adapter.js`：读取上述形状的事件源；现无后端时返回空/桩，
  UI 按「事件+自然语言摘要」渲染，不渲染关系数值。

### 权限红线（沿 S2/S3）
- UI 不读取 actual_enemy；未批准 PlotProposal 不进默认海图；
  未送达电文不可见；他人私有判断记忆不可见；聊天不直接触发正式命令
  （全局唯一正式入口=ISSUE ORDER）。

## 五、实施阶段对照（计划 §九）

| Phase | 内容 | 状态 |
|---|---|---|
| UI.0 | 信息架构与原型（本文件） | ✅ |
| UI.1 | Shell 与通知（五工作台导航/Commander Desk 壳/值班栏/NotificationCenter/ISSUE ORDER/移除全局聊天输入） | 进行中 |
| UI.2 | COMMS | — |
| UI.3 | INTEL | — |
| UI.4 | STAFF | — |
| UI.5 | LOG 与复盘 | — |
| UI.6 | S3/S4 联动 | — |
| UI.7 | 可读性、响应式与验收 | — |
