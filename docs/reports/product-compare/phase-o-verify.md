# Phase O.3 验收报告：珊瑚海战区切换与玩法回路（端到端实证）

日期：2026-09-11 · 依据：`task-O.3-brief.md` · 手法先例：N.6 route-loop（curl 驱动）+ M 批 fixture + O.1 CDP 截图
截图：`o3-game-coralsea.png`（游戏页 1440×900，CDP 真实点击开局层）· `o3-fixture-coralsea-closeup.png`（fixture 近景参照，临时改动已还原）

## 结论速览

| 节 | 判定 |
|---|---|
| 一 战区切换（`/game/new` coral-sea → `/state`） | **PASS**（4 处实证断点修复后） |
| 二 海图渲染（游戏页底图 + fixture 近景参照） | **PASS** |
| 三 玩法回路（航线 → 批准 → advance×2 → 沿线移动） | **PASS** |

全量 `pytest tests/` → **346 passed, 0 failed**（基线 341 + 珊瑚海开局回归 1 + 舰队名前缀绑定 1 + 地理层 Node 套件包装 1 + 静态守卫 1，`test_game_new` 断言追加若干）。

---

## 一、战区切换（PASS）

### 实证断点（systematic-debugging，4 处，均已最小修复）

1. **`/game/new` 只切图不换局**：`build_initial_state()` 硬编码 midway 包——切珊瑚海后时钟仍 1942-06-04、舰队仍 TF16 企业/大黄蜂、敌舰队仍 Kido Butai（基线 curl 实证，验收全红）。
   **修**：`build_initial_state(scenario_path)` 参数化（缺省/midway 走既有历史开局逐字段不变，其余包通用剧本化构建：clock_start→时钟、布兵→双舰队、enemy_fleet→MO 实体+actual_enemy；known_enemy 初始为空——可视性分层不破）；`server.py` 传 `pack_dir/"scenario.json"`。
2. **`/state` 只序列化 `task_forces[0]`**：珊瑚海双盟军舰队只见 YOR。
   **修**：全舰队序列化；顺带下发 `theater` 摘要（id/name/timezone_offset，无坐标军情）供顶栏时区显示。
3. **剧本舰队名前缀绑定缺失**：scenario 名「Task Force 17 (TG 17.5)」与 owner 短名还原「Task Force 17」精确匹配失败 → 航线航行静默跳过（实证：`[ROUTE] 舰队 'TF17' 不存在，跳过`）。
   **修**：`src/entities.py` 舰队绑定精确/前缀双匹配（`_fleet_matches`，`update_positions` 与 `advance_route_fleet` 同口径，防双重移动）。
4. **前端底图不随战役切换**（O.1 登记遗留）：startCampaign 不重拉 `/theater`。
   **修**：见节二。

### 切换证据（curl）

```
POST /game/new {"theater_id":"coral-sea"} → ok:true, theater_id:coral-sea
GET /state：
  clock.game_time = 1942-05-06T21:00:00+00:00   —— 时区语义：Z+10 当地 = 1942-05-07T07:00（五月七日黎明，= scenario.date）
  theater = {id: coral-sea, name: 珊瑚海, timezone_offset: 10}
  task_forces = [Task Force 17 (TG 17.5) / USS Yorktown (CV-5) @ (-15.5, 155.6) course 315 speed 27,
                 Task Force 11 (TG 17.8) / USS Lexington (CV-2) @ (-15.7, 155.4) course 315 speed 27]
                   —— 位置=scenario.json 布兵值
  known_enemy = []   —— 敌情经侦察产生（可视性分层：actual_enemy 含 MO 机动部队，不下发玩家态；
                        state.enemy_fleet = MO 机动部队/日本/翔鹤+瑞鹤 @ (-12.0, 157.0) course 210 speed 20，pytest 断言）
GET /theater：id coral-sea，view_nm = 800（视野半径），center (-15.2, 155.5)，geography 31 features
重入切换：POST /game/new midway → 时钟回 1942-06-04T04:00、TF16（回归测试断言 + 活服实证）
```

判定：**PASS**——时钟/时区、双舰队=scenario 值、敌情=日军（MO，god-view）、图幅 800nm 全部符合。

## 二、海图渲染（PASS）

### 修复（前端接线，最小面）

- **GeoJSON 地理层**（本次主缺口：`/theater` 下发的 `geography` 前端从未消费，全库无多边形渲染——midway 近景环礁为程序化绘制）：chartRenderer 新增 `drawGeography`——land/islet 米黄填充+墨色海岸线、reef 淡青虚线、depth_contour 等深虚线、label 标注（text/size 全走数据）；按 `T().atoll` 门控（无程序化环礁参数的多岛包才走地理层，midway 近景逐像素不回归）；TheaterLoader 把 `payload.geography` 附加在战区对象上；**startCampaign 重拉战区包**（`TheaterLoader.load` → `ChartRenderer.setTheater` → 重投影，O.1 遗留收口）。
- 配套：mapRenderer 全舰队上图 + 字标映射（YOR/LEX）、uiController 底栏单航母/南北半球感知（13.7°S 157.7°E）、顶栏日期/Z+时区随战区（07 MAY 1942 · Z+10）、时钟 Zulu（UTC）化（O.1 §五.3 疣收口）、大取景细网格 <24px 跳过；缓存号全链 1780998016→**1780998017**。

### 截图自查

- **o3-game-coralsea.png**（游戏页，CDP 点击开局层「开始战役」真实切换）：底图渲染珊瑚海战区包——新几内亚东段、所罗门群岛链（布干维尔→瓜岛）、路易西亚德礁群、新喀里多尼亚、islet/reef 多边形 + NEW GUINEA / SOLOMON ISLANDS / GUADALCANAL / LOUISIADE ARCHIPELAGO / CORAL SEA / NEW CALEDONIA 标注 + 1°/5° 经纬网 + 100/200/300nm 距离环；双舰队标记（YOR 43°/LEX）上图；顶栏 07 MAY 1942 · Z+10 / TASK FORCE 17。页面取证：`theater: coral-sea/800nm, geography: true`。
- **o3-fixture-coralsea-closeup.png**（近景参照）：design-fixture 临时注入珊瑚海包近景（view_nm 45→80、center 移所罗门群岛重心 -9.7/160.3）——ChartEngine 对珊瑚海地理的渲染能力实证：瓜岛/佛罗里达群岛多边形海岸线、GUADALCANAL 标注、网格/比例尺全走数据。**临时改动已 git 还原**（design-state.js 不在变更清单）。

判定：**PASS**——底图=珊瑚海包（多边形/标注/样式全走数据），800nm 全景与 80nm 近景双尺度取证。

## 三、玩法回路（PASS）

### 回路证据（curl，活服）

```
POST /routes {kind: planned, owner: TF17, waypoints: [(-14.2,157.2), (-12.5,158.8), (-10.5,159.8)]}
  → route edbbee9b…, draft, progress 0        （图拉吉方向侦察航线，3 航路点）
POST /routes/edbbee9b…/approve → status: active
位置前：YOR (-15.5, 155.6)
POST /advance {minutes:180} ×2 → 200, 200
位置后：YOR (-13.70, 157.67)，TF course 43°    —— 位移方位 = 航线首段（NE，向图拉吉）；
                                                  81nm/tick×2 过 W1 吸附切段
GET /routes → status active, progress 1/3     —— 推进指针停在下一航路点
GET /state → clock 21:00Z→03:00Z（+6h），LEX 按 scenario 航向 315° 自航 162nm → (-13.79, 153.43)
截图（o3-game-coralsea.png）：YOR 标记 CSE 43° + 虚线航线与航路点圈上图，页面 routes 取证 [{o:TF17,s:active,p:1}]
```

截图同帧取证：底栏 航向 43°/航速 27/位置 13.7°S 157.7°E/甲板 约 74/74·0/敌情 暂无（初始无敌情，可视性分层）。

判定：**PASS**——建线→批准→推进→沿线移动→progress 推进全链实证。

---

## 变更与测试清单

**后端修复**（实证 bug 在 src 游戏逻辑层，全局约束「除非实证 bug 在彼」口径）：
`src/initial_state.py`（scenario 参数化+通用构建）、`server.py`（/game/new 传包路径、/state 全舰队+theater 摘要）、`src/entities.py`（舰队名前缀绑定）。
回归：`tests/test_game_new.py`（珊瑚海开局/切回+midway 缺省不回归）、`tests/test_entities.py`（前缀绑定）。

**前端修复**（mapRenderer/uiController/server 路由层白名单面 + theaterLoader/chartRenderer 渲染链）：
`static/js/chartRenderer.js`（drawGeography+atoll 守卫）、`theaterLoader.js`（geography 附加）、`main.js`（startCampaign 重拉）、`mapRenderer.js`（全舰队/callsign/细网格守卫）、`uiController.js`（底栏守卫/Zulu 时钟/顶栏战区）、`index.html`+`svgLoader.js`（缓存号 1780998017）。
守卫：`tests/test_ui_assets.py`（渲染链静态分析+缓存号递增）、`tests/ui/geo_render.test.mjs`+`tests/test_geo_render_js.py`（Node 桩：地理层消费真实 geojson/双舰队投影位/midway 不回归）。

**验收产物**：本报告 + 两张截图。

## 遗留（deferred，不阻塞验收）

- `route_hint`（日军绕所罗门西进轴等历史进场轴）本层不画——留待航线系统口径统一。
- navigator 提案舰队名映射（`FLEET_SHORT.get(tf.name, tf.name)` 回退全名）与 NPC 名册显示名热替换（O.1 遗留）未动——不在本次白名单。
- 敌情初始为空系设计（侦察产生敌情）；珊瑚海 NPC 工具面（bases/陆基航程）随包自动生效，未逐一玩法化验证。
