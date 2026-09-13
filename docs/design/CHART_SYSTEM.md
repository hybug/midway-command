# 海图系统设计（Theater Chart System）

> 状态：**已实施**（2026-09-12，实施计划见 docs/plans/product-replica-plan.md Phase M/N/O——战区包化/投影唯一化/航线系统+航海参谋/珊瑚海战区包全部落地；时区纪法为 ZD+12 二战海军口径，非 ISO 偏移） · 上游：`docs/plans/product-replica-plan.md`（成品图复现工程） · 关联：`docs/design/GAME_SPEC.md`、`docs/design/TECH_ARCH.md`

## 一、目标与设计原则

**目标**：把当前「写死中途岛」的海图渲染（chartRenderer.js 硬编码 CHART_CENTER/RING_NM/环礁/岛名）重构为**数据驱动的战区海图系统**——换战区（如珊瑚海）只需换一份「战区包」数据，海图即呈现真实地理（岛屿/经纬度/礁盘/距离结构），且游戏全部逻辑（航行/航线/侦察/打击/敌情）在任意战区下无差别工作。

**设计原则**：
1. **数据与渲染分离**：地理是数据（Theater Pack），风格是规则（Chart Style），渲染是引擎（ChartEngine）——三者互不依赖，各自可换。
2. **逻辑与地图解耦**：游戏逻辑只认识「经纬度 + 距离 + 方位」这一通用地理语言，永不 import 任何具体战区常量。
3. **1942 美学即约束**：战区数据必须是「1942 年海图能画出来的东西」——低多边形海岸线、简化礁盘、手写标注。这天然降低了地理数据精度要求（Natural Earth 1:10m 级足够），反而让 agent 生成数据变得可行。
4. **可校验优先于可渲染**：任何战区包先过校验器再进渲染，坏数据不允许上屏。

## 二、现状与差距

| 现状 | 差距 |
|------|------|
| chartRenderer.js 硬编码：CHART_CENTER{28.2,-177.4}、CHART_VIEW_NM=45、RING_NM、atollOutline 程序化环礁、SAND/EASTERN ISLAND 坐标与标注 | 需要「战区包 → 渲染参数」的数据通道 |
| initial_state.py 写死 TF16/TF17 坐标、侦察扇区 30°-90° 等 | 兵力初始部署/侦察扇区模板需随战区走 |
| 游戏逻辑（movement/spatial/scouting/mission）已是纯经纬度 ✓ | 唯一例外：个别默认值与基地坐标散落，需收口到战区配置 |
| 换图 = 改代码重新发版 | 目标：换图 = 放一份战区包 + 热加载 |
| 敌情/航线/航线标注已有雏形（known_enemy、scout 航线、CSE 线） | 缺：玩家手绘航线、多段航路点、航迹层、多级缩放 |

## 三、核心抽象：Theater Pack（战区包）

```
theaters/
└── coral-sea/                    # 战区 ID（kebab-case，唯一）
    ├── theater.json              # 战区元数据 + 渲染配置 + 玩法配置（核心，见下）
    ├── geography.geojson         # 地理图层（GeoJSON FeatureCollection）
    ├── assets/                   # 战区专属位图/矢量素材（可选，如大岛纹理）
    ├── scenario.json               # 战区剧本：初始兵力部署/NPC 名册/胜利条件/历史事件种子
    └── README.md                 # 数据来源、许可证、生成方式（agent 填写）
```

### theater.json Schema（v1）

```jsonc
{
  "id": "coral-sea",
  "name": "珊瑚海",
  "name_en": "Coral Sea",
  "date": "1942-05-04",                     // 战役日期（时钟初始）
  "timezone_offset": 10,                     // 当地时区（Z+10）
  "view": {                                  // 取景（对齐成品图近景规范）
    "center": { "lat": -15.2, "lon": 152.5 },
    "view_nm": 220,                          // 视野直径（海图短边覆盖的海里数）
    "rotation": 0                            // 预留：海图旋转角
  },
  "graticule": { "minor_step": 0.25, "major_step": 1.0, "label_format": "dms" },
  "range_rings": {                           // 距离环（原点/半径可配）
    "origin": { "lat": -15.2, "lon": 152.5 },
    "rings_nm": [100, 200, 300],             // 珊瑚海尺度大，环距按战区定
    "labels": true
  },
  "bases": [                                 // 基地/机场（游戏逻辑读：起飞/降落/陆基航程）
    { "id": "noumea", "name": "努美阿", "lat": -22.27, "lon": 166.44, "type": "port" },
    { "id": "tulagi", "name": "图拉吉", "lat": -9.1, "lon": 160.15, "type": "airfield", "capacity": 24 }
  ],
  "sectors": [                               // 侦察扇区模板（scouting.generate_*_route 的参数来源）
    { "id": "nw-quad", "name": "西北扇区", "origin_ref": "noumea", "bearing_min": 270, "bearing_max": 360 }
  ],
  "units": "nm",                             // 距离单位（预留 km）
  "style_overrides": {                       // 战区级风格覆盖（可选，缺省用全局 chart style）
    "sea_tint": "rgba(184,212,200,0.25)",
    "land_fill": "#d4c4a0"
  },
  "scenario": "scenario.json"                // 指向战区剧本（换图=换玩法，见 §5.2）
}
```

### geography.geojson 约定

FeatureCollection，每个 Feature 带 `class` 属性驱动渲染样式：

| class | 几何 | 渲染 |
|-------|------|------|
| `land` | Polygon/MultiPolygon | 陆地填充（land_fill）+ 墨线描边 |
| `islet` | Polygon（小岛/沙洲） | 同 land，最小面积过滤 |
| `reef` | Polygon/LineString | 礁盘虚线描边（reef 色，不填充或半透蓝绿） |
| `lagoon` | Polygon | 泻湖填充（lagoon 色） |
| `depth_contour` | LineString | 等深线细线（alpha 0.08） |
| `label` | Point + props{text, size, role} | 地图标注（岛名/坐标/海域名，role 定字体层级） |
| `route_hint` | LineString | 预置航线参考（历史航线，虚线淡线） |

示例：

```jsonc
{
  "type": "FeatureCollection",
  "features": [
    { "type": "Feature", "properties": { "class": "land", "name": "Guadalcanal" },
      "geometry": { "type": "Polygon", "coordinates": [[[160.0,-9.4],[160.9,-9.6],[160.8,-10.3],[159.9,-10.2],[160.0,-9.4]]] } },
    { "type": "Feature", "properties": { "class": "label", "text": "CORAL SEA", "role": "sea" },
      "geometry": { "type": "Point", "coordinates": [152.5, -14.0] } }
  ]
}
```

> **精度立场**：1942 海图风格 = 简化海岸线。数据精度到 0.1°（~6nm）即可，多边形 8–30 个顶点。这意味着 agent 用地理知识手写 GeoJSON 与从 Natural Earth 简化，产物质量同级——数据获取不再依赖高精源。

## 四、渲染管线：ChartEngine（图层化重构）

chartRenderer.js 拆分三层，替换现有「Midway 硬编码绘制」：

```
ChartStyle（风格规则，既有 CHART_STYLE 扩展）   ← token + style_overrides
TheaterLoader（加载+校验战区包）                ← fetch theaters/<id>/，schema 校验
ChartEngine.draw(ctx, w, h, theater, camera)    ← 图层顺序绘制，无任何战区常量
  ├─ L0 paper        纸底（纹理平铺，既有）
  ├─ L1 graticule    经纬网（步进/标注来自 graticule 配置）
  ├─ L2 terrain      GeoJSON 图层（land/reef/lagoon/depth_contour，投影后 Path2D）
  ├─ L3 annotations  标注（label features + 中心标注）
  ├─ L4 tactical     距离环/侦察扇区底图（range_rings + sectors 配置）
  ├─ L5 entities     实体层（既有：舰队/飞机/敌标/航线——mapRenderer 职责，不变）
  └─ L6 overlay      章/暗角/划痕/台灯（既有氛围层）
```

关键接口（签名级设计）：

```javascript
// TheaterLoader.js
async function loadTheater(id) -> Theater        // fetch + JSON.parse + validate，失败即抛
function validateTheater(pack) -> { ok, errors } // 见 §六校验器

// 投影（唯一坐标系出入口，全程等距圆柱 + cos(lat) 纬度修正——既有 latLonToChartPx 泛化）
function makeProjector(view, width, height) -> project(lat, lon) -> {x, y}
function project.invert(x, y) -> {lat, lon}      // 反投影：鼠标拾取/航线输入要用

// Camera（Phase-2 扩展多级缩放的预留口）
camera = { center, view_nm, rotation }           // v1 固定 = theater.view
```

**mapRenderer 的实体投影**改为消费 `makeProjector` 的同一投影实例（顺带消灭「底图与实体两参考系」这一已知局限——投影唯一化是本设计的副产品收益）。

**Midway 战区包**：现 chartRenderer 的程序化环礁/双岛/跑道逻辑改写为生成器脚本 `tools/gen_midway_pack.py`——产出 `theaters/midway/`，渲染结果与现状视觉等价（回归验收=与当前截图 MD5 级对照，容差为抗锯齿）。**保证重构不破坏已收敛的成品图复现。**

## 五、游戏逻辑接口（条件 2：支撑航行/航线/玩法）

游戏逻辑一律通过 `TheaterContext` 读配置，禁止直连 Midway 常量：

```python
# src/theater/context.py（新）
class TheaterContext:
    id: str; view: View; bases: list[Base]; sectors: list[Sector]
    def distance_nm(a: LatLon, b: LatLon) -> float        # 委托 scouting.calculate_distance_nm
    def bearing(a: LatLon, b: LatLon) -> float
    def base(ref: str) -> Base                             # 机场/港口（起飞、陆基航程、补给）
    def sector_template(sector_id: str) -> Sector          # 侦察扇区模板 → generate_sector_route 参数
    def is_land(lat, lon) -> bool                          # 点位是否陆地（近岸搁浅/绕飞预留）
```

**玩法支撑矩阵**：

| 玩法 | 现状 | 海图系统提供 |
|------|------|--------------|
| 舰队航行 | course/speed 每 tick 位移 ✓ | 不变；新增**航路点航线**（见下） |
| 侦察航线 | 三种 generate_*_route（扇区原点硬编码=舰队位） | 扇区模板来自 theater.sectors；原点可选基地/舰队 |
| 打击解算 | calculate_intercept ✓ | 不变（纯经纬度数学） |
| **航线标注（玩家手绘）** | 无 | 见 §5.1 |
| **航迹层** | 无 | 每 tick 记录 FleetTrack（船尾虚线，历史回放） |
| **陆基航空兵** | 无 | bases[type=airfield] + capacity → 陆基侦察/CAP 半径圈 |
| **敌情** | known_enemy（delayed/distorted）✓ | 不变；标注渲染层复用 |
| **昼夜** | 时钟 ✓ | Phase-2：光照 LUT（纸面色温随时间） |

### 5.1 航线系统细化（标注 = 玩法）

三类航线，同一数据结构不同样式：

```python
Route = {
  "id": str, "kind": "planned|mission|track",   # 手绘铅笔线 / 任务航线(侦察/打击) / 历史航迹
  "owner": str,                                  # 舰队/机群/玩家
  "waypoints": [ {lat, lon, eta?, note?} ],      # 航路点
  "status": "draft|active|done|cancelled"
}
# API
create_planned_route(waypoints)      # 玩家：图上点选 → 铅笔线（多段）
activate_route(route_id, fleet_id)   # 舰队沿航路点航行（替代单点 course——course=末段方位自动推导）
append_mission_route(mission)        # 侦察/打击任务自动生成（现有 generate_*_route 产物挂接）
```

样式（对齐 1942 海图语言）：手绘线=Caveat 铅笔灰线；任务线=红/蓝虚线+箭头；航迹=浅墨点线。**这正是成品图里 ENT→环礁双虚线箭头矢量的系统化表达**。

### 5.2 航海参谋航线玩法（已拍板：核心玩法闭环）

**决策回路**：指挥官给出战略意图（自然语言）→ **航海参谋 NPC**（新 LLM 角色）生成结构化航线方案 → 命令卡呈现方案摘要 + **海图同步渲染草案线**（铅笔虚线）→ 指挥官批注修改意见 → 参谋修订（可多轮）→ **批准** → 航线转正式任务线，舰队沿航路点航行，海图自动更新。

```python
# 新 NPC：src/agents/navigator.py（航海参谋）
# 工具集（npc_config 注册）：query_own_fleet / query_theater(theater_id) /
#   query_distance_bearing(a, b) / query_bases() / propose_route(route) —— 全部走 GameState 墙
NavigatorNPC.propose_route -> PendingRoute(          # 复用 PendingSuggestion 审批架构
    route=Route(kind="planned", waypoints=[...], speeds=[...]),
    rationale="抢占东南风位，黎明前封锁珍珠港航道…",   # 史实/战术理由（命令卡展示用）
    status="proposed")                                # → 玩家批准后 route.status=active
```

- **海图渲染联动**：`proposed` 状态画**铅笔草案线**（Caveat 灰虚线+航路点小圈）；`active` 转**任务线**（红/蓝虚线+箭头）；舰队航迹叠加浅墨点线。三类线即成品图 ENT→环礁双虚线矢量的系统化。
- **命令卡联动**：PendingRoute 复用军令纸组件（A8/E6 常驻卡），正文=rationale+航路点表（航向/距离/ETA），按钮=批准实施/驳回/提修改意见（意见走聊天回路给参谋）。
- **与现有架构的复用关系**：审批流=PendingSuggestion 同构；参谋工具全部经 GameState 墙（不碰真实坐标外泄问题）；NPC 名册在 scenario.json 中按战区配置（珊瑚海=TF17 Fletcher 参谋团，中途岛=Spruance 参谋团）。

## 六、Agent 换图工作流（条件 1：珊瑚海场景）

```
玩家指令（自然语言）："切换到珊瑚海战区，1942 年 5 月 4 日"
        │
        ▼
Agent（theater-designer agent，新角色）
 1. RESEARCH   web 检索/调用地理知识：珊瑚海范围（147°-156°E, 10°-22°S）、
               关键地理（所罗门群岛/新几内亚东端/路易西亚德群岛/图拉吉/莫尔兹比港）、
               战役史实（1942-05-04~08 珊瑚海海战：TF17 Fletcher vs MO 机动部队）
 2. GENERATE   产出战区包：theater.json（取景/环距/基地/扇区）+
               geography.geojson（低多边形海岸线，0.1° 精度立场）+
               initial_state（双方兵力按史实：约克城/列克星敦 vs 翔鹤/瑞鹤）
 3. VALIDATE   validate_theater.py（§七）：schema/几何闭合/经度范围/必备图层/比例合理
 4. PREVIEW    dev 预览页渲染战区包 → 截图 → 设计师 agent 审查（海岸线形态/标注/构图）
 5. COMMIT     theaters/coral-sea/ 入库 + 报告登记数据来源与许可证
        │
        ▼
游戏热加载（server 端点 POST /theater/{id} → TheaterContext 切换 + 前端 loadTheater）
```

**战区包更新标准（agent 产出必须满足的验收规范）**：
1. **地理精度**：海岸线 0.1°（~6nm）级、单要素 8–30 顶点；关键地理（大岛/基地/礁群）与真实坐标偏差 ≤ 0.3°；
2. **完整性**：theater.json 全字段 + ≥1 个 land + ≥2 个 base + ≥1 个 sector + scenario.json 全字段；
3. **史实附注**：README 必须记录数据来源（检索引文/AI 生成声明）与许可证（Natural Earth=PD / AI 生成无第三方）；
4. **视觉验收**：设计师 agent 对照真实珊瑚海地图审海岸线形态/取景构图（审校分离纪律）；
5. **玩法自洽**：scenario 双方兵力按史实可对弈（机动路线/侦察扇区/基地覆盖成回路）。

**Agent 可行性关键点**：
- 数据低精度立场（§三）使 agent 手写 GeoJSON 可行，不依赖 GIS 管线；
- 「审校分离」：生成 agent ≠ 审查 agent（设计师 agent 对海岸线形态/构图做视觉验收，与保真度工程同纪律）；
- **许可证纪律**：外部数据（Natural Earth=PD / OSM=ODbL）来源与许可证必须写入战区包 README；agent 纯知识生成则标注「AI 生成」。

## 七、校验器（validate_theater.py）

硬校验（FAIL 拒载）：schema 合法 / 视野中心在经纬度范围 / GeoJSON 几何闭合 / land 多边形面积 ≥ 下限 / bases 至少 1 个且坐标在视野内×2 / RING 原点在视野内 / 时区合法。
软校验（WARN 进报告）：海岸线顶点数异常（>500 疑未简化）/ 岛名缺失 / 与真实地理抽样比对（agent 对 3 个已知城市坐标自检，误差 >0.5° 报警）。

## 八、扩展能力提案（条件 3：讨论项）

### 核心层（建议纳入本系统 v1 范围）
| # | 能力 | 理由 |
|---|------|------|
| C1 | **多级缩放**（战役 600nm → 近景 45nm → 接敌 10nm） | 成品图本身就有近景语言；滚轮缩放 + camera 预留口已设计 |
| C2 | **航线系统三类线**（planned/mission/track） | 玩法核心（§5.1），也是「航线标注」需求的完整形态 |
| C3 | **投影唯一化** | 消灭两参考系已知局限；鼠标拾取（点选航线/敌情确认）的前提 |
| C4 | **陆基航空兵圈** | 珊瑚海战役的史实核心就是陆基机（其实中途岛岛基航空兵同理）——战斗力语义 |

### 增强层（v2，逐个立项）
| # | 能力 | 说明 |
|---|------|------|
| E1 | **天气/海况层** | 风向风速影响侦察骰与航速；战区包可带气候带默认值 |
| E2 | **昼夜光照 LUT** | 时钟驱动纸面色温（夜战/晨昏发现史实） |
| E3 | **岛屿遮蔽侦察** | line-of-sight 被大岛阻挡——需要 terrain 查询，系统已留 is_land 接口 |
| E4 | **测量工具** | 两脚规量距（历史沉浸+教学） |
| E5 | **AAR 导出** | 海图导出 PNG + 航迹回放（战后复盘） |

### 远期（讨论后定）
| # | 能力 | 说明 |
|---|------|------|
| R1 | **多战区战役包** | 中途岛→珊瑚海→东所罗门 连续战役；单位/损伤跨战区继承 |
| R2 | **真实历史海图底图** | 公有领域扫描件做 L0 底图（LLC/旧海图档案）——质感天花板 |
| R3 | **agent 动态事件** | agent 读战区史实库生成历史事件（鹦鹉螺号暴露、运输团转向） |

## 九、决议记录（2026-09-12 拍板）

| # | 议题 | 决议 |
|---|------|------|
| 1 | 换图粒度 | **正式玩法**——UI 复现完成后整个玩法切换到珊瑚海海战；开局提供战役选择（theater 加载即初始化 scenario） |
| 2 | 航线输入 | **航海参谋 NPC 提案 → 指挥官修订 → 批准上图**的决策闭环（§5.2），这是游戏核心玩法 |
| 3 | 陆地语义 | v1 仅视觉+基地锚点（遮蔽/搁浅留增强层 E3） |
| 4 | 数据来源 | v1 限定「agent 知识生成 + Natural Earth PD」白名单；OSM 暫缓 |
| 5 | 多级缩放 | 先不做；每战区固定取景（theater.view），camera 口预留 |
| 6 | 权威源 | **后端单一下发**：theaters/ 归后端，`GET /theater` 运行时下发战区包，前端零内置战区 |

---

## 附：与既有工程的关系

- 本设计**不推翻**成品图复现工程——Midway 战区包化后，已收敛的视觉（Loop×5 的 44/50）由 gen_midway_pack 生成器等价保持，作为重构的回归基准。
- 实施切分（决议后定稿，待出实施计划）：**Phase 1** = Theater Pack + ChartEngine + 中途岛包化（重构，视觉零变化回归）→ **Phase 2** = 航线系统 + 航海参谋 NPC（§5.2 核心玩法闭环，复用审批架构）→ **Phase 3** = 战役选择（正式玩法）+ agent 生成珊瑚海战区包（过 §六 五步验收）→ **Phase 4** = 增强层按拍板逐个立项（缩放暂缓）。
