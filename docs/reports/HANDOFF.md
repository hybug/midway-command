# 交接文档：Midway Command 复现工程 + 核心玩法方向

> 交接日期：2026-09-13 · 交接人：ZCode 执行会话 · 接收人：后续会话/维护者
> 仓库：`/Users/doqinvera/Desktop/hanyu/workspace/midway-command`
> 远端状态：**已全部推送**，`origin/main = HEAD = 35cc51d`，工作树干净

---

## 一、一句话交接

`docs/plans/product-replica-plan.md` 的**全部内容已执行完毕**（UI 100% 复现成品图 + 海图系统战区化 + 珊瑚海战区切换），
186 个提交、352 测试全绿、已推送 GitHub。**工程门的活结束了，接下来是玩法门**——核心待办是
「让 LLM-NPC 从问答助手变成真实的参谋班子」，方向论证见本文档第七节。

---

## 二、交付清单（按阶段）

### UI 复现段（基准 = `docs/assets/Gemini_Generated_Image_u1fak0u1fak0u1fa.png` 成品图）

| 批次 | 内容 | 关键产物 |
|------|------|---------|
| P0 | 基准切换登记 + 区域比对流水线 | `docs/assets/compare_regions.py` |
| D | 45nm 近景取景 / 纸面压黄 / 深色厚画框 / NE hatch+放射细线 | `static/js/chartRenderer.js` |
| E | 深色 chrome（底栏/右栏/标签）+ 命令卡常驻 + 按钮三态 + 布局合规 60px/320px + 齿轮 | `static/css/style.css` |
| G | 圆圈舰队标记（计数牌退役）+ 飞机剪影 + 敌标红虚线圈+ENEMY 勘误 + SECRET 章上地图 + 黄铜圆规 + 尺铅笔移位 + 东岛细节 | chartRenderer/mapRenderer |
| H | 基准态 fixture + 像素比对验收 | `static/dev/design-fixture.html` |
| Loop×5 | 对照→分级→设计师评审→实施→L5.5 验收硬门 | `docs/reports/product-compare/loops/loop-1..5.md` |
| V | 全分支审查 + 修复波次 + 文档收口 | `docs/reports/doc-conflict-audit.md` |

### 海图系统（Spec = `docs/design/CHART_SYSTEM.md`）

| Phase | 内容 | 关键产物 |
|-------|------|---------|
| M | 战区包化：`theaters/midway/` + 校验器 + `GET /theater` + ChartEngine 数据驱动化 + **投影唯一化（两参考系局限关闭）** | `tools/validate_theater.py`、`src/theater/context.py`、`static/js/theaterLoader.js` |
| N | 航线系统：Route 模型/API + 三类渲染 + **航海参谋 NPC**（提案→批注→修订→批准闭环）+ 沿航路点航行 + 命令卡联动 + 端到端验收 | `src/routes.py`、`src/agents/navigator.py` |
| O | 珊瑚海：战区包（agent 五步生成）+ 战役选择开局层 + 切换与玩法验收 + 收敛轮 | `theaters/coral-sea/`、`docs/reports/product-compare/phase-o-verify.md` |

### 验收证据索引

| 想看什么 | 去哪 |
|---------|------|
| 最终效果截图 | `docs/reports/product-compare/loops/loop-5-fixture-1440.png`（中途岛）、`oc-loop2-game-coralsea.png`（珊瑚海） |
| 设计师评分曲线 | loop-1..5.md：DESIGN **6.6→7.2→7.3→7.8→8.3→8.3**（平台化=收敛） |
| 像素比对数据 | `docs/reports/product-compare/phase-h-verify.md`（区域差 40.5≤45，基线 98.7） |
| 珊瑚海设计师评价 | `docs/reports/product-compare/loops/oc-loop1-designer-review.md`（7.3/10 首评） |
| 玩法闭环实证 | `phase-o-verify.md`、`docs/reports/fidelity-loop/route-loop-verify.md` |
| 全量台账（含所有裁定） | `docs/reports/product-compare/sdd-ledger-final.md` |
| 文档冲突与处置 | `docs/reports/doc-conflict-audit.md` |

---

## 三、当前代码地图（新增/重大改动）

```
src/
├── theater/context.py        # TheaterContext + load_theater（fail-fast 校验）
├── routes.py                 # Route/Waypoint/PendingRoute 模型 + fleet_short_name 战区映射
└── agents/
    ├── navigator.py          # ★ 航海参谋 NPC（提案/修订，工具走 GameState 墙）
    └── base.py               # NPCAgent 基类（messages 短期记忆 + build_system_prompt）

theaters/
├── midway/    {theater.json, geography.geojson, scenario.json, README.md}
└── coral-sea/ {同上}          # agent 生成，含地理修复轮

static/
├── js/theaterLoader.js       # fetch /theater → setTheater
├── js/chartRenderer.js       # ★ 数据驱动绘制（makeProjector 唯一投影）
├── js/mapRenderer.js         # 实体层（舰队/飞机/敌标/三类航线）
├── dev/design-fixture.html   # 像素比对专用状态页（不进游戏流程）
└── assets/textures/          # AI 生成纹理（paper_tex 等）

tools/
├── validate_theater.py       # 战区包硬/软校验
└── gen_midway_pack.py        # 中途岛包生成（与渲染公式同源）
```

**新增后端端点**：`GET /theater`、`GET /theaters`、`POST /game/new`、`GET/POST /routes`、`POST /routes/{id}/approve|cancel|comment`、`GET /pending-routes`、`POST /pending-routes/{id}/approve|reject`、`POST /navigator/propose`

---

## 四、必须知道的坑（下一位维护者省时间）

1. **缓存号纪律**：改任何 `static/js/*.js`、`static/css/*.css`、`static/index.html` **必须**递增 `?v=`（当前 **1780998018**），并同步 `tests/test_ui_assets.py` 的 pin **和** `svgLoader.js` 里带 `?v=` 的资产条目——否则会被一致性测试拦下，或浏览器缓存旧文件造成"改了没生效"的假象（这是踩过的坑）。
2. **无头 Chrome 截图用 `--timeout=12000`，不要用 `--virtual-time-budget`**——rAF 动画循环会把后者挂死。见 `docs/reports/product-compare/loops/loop-*` 的截图命令。
3. **uvicorn 自愈**：`/tmp/uvicorn_keepalive.sh`（本会话创建的，重启后需重建）；playwright 内嵌浏览器截图通道不稳定，一律用无头 Chrome。
4. **fixture 页 `static/dev/design-fixture.html` 是测试工件**，顶部有「FIXTURE — 非游戏画面」标识条，不要混入正式流程。
5. **`src/initial_state.py` 已 scenario 化**（`build_initial_state(scenario_path)`），midway 走历史开局分支保持逐字段不变——改它前先看 `test_build_initial_state_midway_default_unchanged`。
6. **战区解耦原则**：游戏逻辑不得硬编码战区常量，必须经 `TheaterContext` 读配置（navigator 曾因硬编码 midway 路径被评审打回，已修）。

---

## 五、已登记但未做的遗留（按级别）

**D-C 级（可选打磨）**
- CSE 标签与 30px 航向线同带有细线穿插；ENT 圈位贴画布左缘时左侧标签出画
- 环礁形态偏圆润（真实地理立场导致的既定偏差）
- PENDING 金色扇区在新 scenario 布兵后部分出画
- 罗盘压 176°30'W 标注（已让位，残余轻微）
- 珊瑚海：比例尺仍用 midway 的 0-10-25-50nm 刻度（尺度感失真 6.6×）；右侧页签仍静态 `TF16 CAPT/HOR CAPT` 未战区化

**A 级（影响体验完整性）**
- **A5 敌标 / A8 军令纸 / A10 情报卡 缺真实数据下的实拍对照**——需要玩一局触发
- 珊瑚海同位双舰 CSE 标签叠字（<36px 时应错行）
- 底栏敌情缺 BB 段（数据端 `known_enemy` 无战列舰计数字段）

**验证缺口**
- `POST /navigator/propose` 的**真实 LLM 链路**未被测试驱动（测试全用 fake client）
- 中途岛 fixture 的 ENT 西置构图未复现成品图（有意偏差，为保标题可读）

---

## 六、可执行命令速查

```bash
source .venv/bin/activate
uvicorn server:app --reload            # 起服务（http://localhost:8000）
pytest tests/                          # 352 passed 0 failed
pytest tests/test_ui_assets.py -v      # 前端静态守卫
node tests/ui/route_display.test.mjs   # JS 显示一致性（Canvas 录制器）
python tools/validate_theater.py theaters/coral-sea/   # 战区包校验
python docs/assets/compare_regions.py <设计图> <截图> <输出目录>  # 像素比对
curl -X POST localhost:8000/game/new -H "Content-Type: application/json" -d '{"theater_id":"coral-sea"}'  # 切战区
```

---

## 七、★ 下一步核心：玩法方向（已与用户讨论，结论如下）

### 用户的定性（原话要点）

> 「核心乐趣是**像真实历史一样与真正的参谋交互**，最核心是 LLM-NPC 的设定。」

这推翻了"指挥海战"作为第一乐趣的假设——**主角是参谋班子，不是海图**。海图是舞台，交互对象是赋予意义的那一层。

### 现状差距（已核代码，非印象）

| 维度 | 现状 | 缺口 |
|------|------|------|
| 记忆 | 仅 `self.messages` 会话内短期记忆 | 无跨会话立场/关系记忆 |
| 主动 | `chat()` 仅在玩家说话时触发 | 参谋不会主动上门 |
| 性格 | autonomy/risk/initiative/competence 只是提示词里的数字 | 未转化为行为机制（competence 不影响判断质量） |
| 摩擦 | 有求必应（像 API） | 不会质疑问题、不会拒绝、不会说"我不知道" |
| 互动 | 每个 NPC 独立 session，跨 NPC 必须经玩家 | 有隔离但无"转述"动作，班子戏无从生长 |
| 输出性质 | 倾向给自信答案 | 未强制区分【事实/参谋判断/情报来源】 |

**结论：当前是"五个有性格设定的问答助手"，还不是"一个班子"。**

### 三条设计原则（讨论中最重要，优先级高于具体机制）

1. **事实确定，判断可飘**——`GameState` 是神谕，但基于事实的**推断可以错**。参谋错要有梯度、可归因。否则只是查询接口。
2. **失败可归因**——输掉后必须能在复盘看出"我输在信了 Browning 的乐观估计"。做不到这点，LLM 的不确定性就只是噪音，不是戏剧。
3. **UI 强制区分【事实 / 参谋判断 / 情报来源】**——LLM 的表达力会**掩盖信息缺失**，说得越流畅玩家越容易忘记他其实什么都不知道。必须让"这是他的判断"视觉上不可混。**这是全项目最大的陷阱。**

### 五机制 + 推荐顺序

| 方向 | 机制 | 说明 |
|------|------|------|
| **A 参谋关系层** | ①立场账本 ②主动上门 ③摩擦与拒绝 ④competence 机制化 ⑤转述 | 关系的地基 |
| **C 认知链** | 失真情报 → 参谋误判 → 玩家仲裁 → 可归因复盘 | 把"交互"变成"有胜负后果的决策"的关键 |
| **B 班子冲突层** | 转述 + 互评 + 分歧戏剧化 | 长出来的戏剧，锦上添花 |

**推荐 A → C → B**：A 是地基（无记忆→无关系→无冲突素材）；C 才是让"像人的参谋"不只是精美对话玩具的关键；B 是戏剧富集。

**两个待用户拍板的问题（尚无答案）**
1. **参谋该不该"赢"玩家**——即参谋判断有时比玩家对，采纳他才是最优解？倾向"应该会"（否则没有值得尊重的人可依赖），但会削弱"玩家是唯一枢纽"的掌控感。口味问题，需用户定。
2. **乌龟玩法惩罚**——是否给日军加"主动搜索压力"事件（史实种子已留：利根四号机弹射失误 25 分钟、鹦鹉螺号暴露）。若无达摩克利斯之剑，"情报用时间买"的压力齿轮不转。

### 另一个重要的设计缺口（讨论中提出）

**推理工具缺失**：多份失真报告理论上可夹叉定位（两份方位差 → 三角定位），这是硬核乐趣金矿，但当前 UI 无报告对账工具，玩家只能在脑内拼。做与不做需决策。

---

## 八、给下一位的开工建议（顺序）

1. 先跑 `pytest tests/ -q`（应 352 passed）与 `uvicorn server:app`，浏览器打开确认中途岛/珊瑚海都能进——**确认基线可信再动手**。
2. 想动玩法 → 以 `docs/plans/gameplay-system-roadmap.md` 为长期路线图；S2 感知与情报、**S3 参谋认知与判断（Phase S3.0–S3.7，珊瑚海 5/7 与 5/8 纵切全通）均已执行完成**（规格 `docs/design/S3_COGNITION_SYSTEM.md`，代码 `src/cognition/`）；下一步按路线图是 **S4 参谋班子与关系系统**（前端契约桩已就位：`static/js/s4Adapter.js`，落地后只需接真实事件源）。
3. 想补 UI → S8 五工作台重构已执行完成（Phase UI.0–UI.7，规格 `docs/design/S8_INTERFACE.md`：CHART/COMMS/INTEL/STAFF/LOG + Commander Desk + NotificationCenter + ISSUE ORDER）；收尾项见 `docs/plans/s8-ui-ux-system-plan.md` 执行记录。
4. S3.8 收尾项：真实 LLM 接入后跑人物行为评估（Browning 风格/谨慎情报官/航空指挥官三类）并冻结五维权重（当前权重全部标注 v0，集中于 `src/cognition/formula.py` 与 `src/cognition/evidence_fit.py`）。
4. 任何阶段改动前，读 `docs/reports/product-compare/sdd-ledger-final.md`——**所有历史裁定都在那**，避免重蹈。

---

## 九、会话方法论备忘（这套流程有效，建议沿用）

本工程采用 **subagent-driven-development** 纪律，跑通了完整闭环：

- **六步循环**：红测 → 实现 → 转绿 → 目检 → 派评审 → 提交
- **两层把关**：客观门（pytest/node 断言/校验器）+ 目检（无头 Chrome/设计师 agent），**客观门非充分条件**（曾有"图"字碎片骗过全部客观判据）
- **设计师验收硬门（L5.5）**：设计师 agent 逐条 ACCEPT/REJECT，REJECT 未清零不得关轮——**真实行使过 3 次**（Loop1-F8 晕影零效果、Loop3-F3R 方向词错挂、O.2 地理超差），每次都逼出真实修复
- **裁定留档**：所有代决策记入台账（`sdd-ledger-final.md`），带"错了会怎样"
- **修复环**：轮 1-3 原实现者、4-5 换更强模型、5 轮后控制器裁定
- **工时保护**：自下而上核算 + 预算保护条款（提前收敛则加深轮次），防"过早收工"

**最有效的一条经验**：*每轮以新实拍为基准重新对照*——单轮修复后必然有实现盲区，Loop 的价值不在重复，而在用新证据逼出旧盲区（Loop 1 的竖向接缝、Loop 3 的坐标系反向都是这样抓到的）。

---

**文档地址**：`docs/reports/HANDOFF.md`（本文件，已提交入库）
