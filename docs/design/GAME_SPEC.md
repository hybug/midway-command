# 中途岛指挥官 · 游戏规则文档

> 本文档是所有游戏机制的唯一真相来源。开发、测试、设计均以此为准。

---

## 一、游戏概要

**背景**：1942年6月4日，中途岛战役。玩家扮演 TF16 指挥官 Spruance。
**核心玩法**：通过自然语言与参谋团对话，下达侦察/航行/攻击命令。
**核心体验**：信息不对称 × 参谋性格偏差 × 时间压力。

---

## 二、时间/AP系统

### 2.1 概述

时间/AP系统控制游戏节奏。负责：游戏时钟推进、动作点（AP）消耗与重置、tick 管线调度、游戏结束判定。

**职责边界**：
- 本系统负责：时钟推进、AP 管理、tick 管线调度、游戏结束触发
- 本系统**不**负责：具体业务逻辑（侦察、战斗等由各自系统处理）

**依赖关系**：
- 输入来自：前端（玩家点击"推进时间"）、NPC系统（消耗AP）
- 输出给到：所有系统（tick信号）、前端（AP状态、游戏结束通知）
- 调用时机：玩家主动推进时间时触发整个管线

### 2.2 数据模型

#### 2.2.1 GameClock

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| game_time | `datetime` | required | 1942-06-04 04:00 UTC | 当前游戏时间 |
| tick_minutes | `int` | const = 15 | 15 | 每tick推进分钟数 |

#### 2.2.2 TurnType 枚举

| 枚举 | 值 | AP | 触发条件 | 状态 |
|------|-----|-----|---------|------|
| NORMAL | "normal" | 3 | 默认 | ✅ 已实现 |
| CRITICAL | "critical" | 5 | 接近敌军/战斗准备 | ⬜ 待实现 |
| EMERGENCY | "emergency" | 2 | 被攻击/紧急情况 | ⬜ 待实现 |

#### 2.2.3 GameState 中的时间/AP 字段

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| clock | `GameClock` | required | 游戏时钟 |
| turn_type | `TurnType` | default NORMAL | 当前回合类型 |
| action_points | `int` | ≥ 0 | 当前剩余AP |
| max_action_points | `int` | ≥ 0 | 当前回合最大AP |

#### 2.2.4 TickStep 管线步骤

| 字段 | 类型 | 说明 |
|------|------|------|
| name | `str` | 步骤名称（日志用） |
| handler | `Callable[[GameState, int], list[str]]` | 处理函数，返回通知列表 |
| order | `int` | 执行顺序（越小越先执行） |
| enabled | `bool` | 是否启用（可用于临时禁用步骤） |

### 2.3 状态机

#### 游戏生命周期

| 状态 | 值 | 含义 | 持续条件 |
|------|-----|------|---------|
| PLAYING | "playing" | 游戏中 | game_time < 08:00 |
| GAME_OVER | "game_over" | 游戏结束 | game_time ≥ 08:00 或触发结束事件 |

#### 状态转换

| 编号 | 当前 | 触发 | 目标 | 动作 |
|------|------|------|------|------|
| TIME-SM-001 | PLAYING | game_time ≥ 08:00 | GAME_OVER | 触发结局判定 |
| TIME-SM-002 | PLAYING | 所有航母被击沉 | GAME_OVER | 触发结局判定 |

### 2.4 规则

| 编号 | 规则 | 条件 | 行为 | 边界/异常 | 测试关联 |
|------|------|------|------|----------|---------|
| TIME-001 | 时钟推进 | 玩家点击推进 | game_time += 15min | — | test_time::test_advance_clock |
| TIME-002 | AP消耗 | NPC对话/下达命令 | action_points -= 1 | AP=0时返回False，不消耗 | test_ap::test_consume_ap |
| TIME-003 | AP重置 | 推进时间 | action_points = max_action_points | — | test_ap::test_reset_ap |
| TIME-004 | AP不可为负 | 消耗时 | action_points ≥ 0 | — | test_ap::test_no_negative |
| TIME-005 | 回合类型-NORMAL | 默认 | max_ap = 3 | — | test_ap::test_normal_turn |
| TIME-006 | 回合类型-CRITICAL | 接近敌军（待实现） | max_ap = 5 | — | test_ap::test_critical_turn |
| TIME-007 | 回合类型-EMERGENCY | 被攻击（待实现） | max_ap = 2 | — | test_ap::test_emergency_turn |
| TIME-008 | 管线执行顺序 | tick触发 | 按order从小到大依次执行 | 某步骤抛异常：记录日志，跳过，继续执行后续步骤 | test_pipeline::test_order |
| TIME-009 | 管线步骤注册 | 启动时 | 按order排序后执行 | 重复注册同名步骤：覆盖旧的 | test_pipeline::test_register |
| TIME-010 | 游戏结束-时间 | game_time ≥ 08:00 | state.game_phase = GAME_OVER | — | test_time::test_game_over_time |
| TIME-011 | 游戏结束-全灭 | 所有航母被击沉 | state.game_phase = GAME_OVER | — | test_time::test_game_over_destroyed |
| TIME-012 | 游戏结束后不可推进 | game_phase = GAME_OVER | tick()返回空，不执行管线 | — | test_time::test_no_tick_after_over |

### 2.5 管线设计（Tick Pipeline）

#### 管线架构

```
tick(minutes=15)
  → Pipeline.execute(state, minutes)
    → Step(order=10): advance_clock(state, minutes)
    → Step(order=20): update_positions(state, minutes)
    → Step(order=30): update_spatial_index(state)
    → Step(order=40): process_scouting(state)
    → Step(order=50): process_reports(state)
    → Step(order=60): fire_events(state)
    → Step(order=70): check_game_over(state)
    → Step(order=80): reset_ap(state)
  → return notifications
```

#### 管线步骤注册表

| order | name | handler | 当前状态 | 依赖 |
|-------|------|---------|---------|------|
| 10 | advance_clock | state.clock.game_time += timedelta | ✅ | 无 |
| 20 | update_positions | update_all_positions(state, minutes) | ✅ | order=10 |
| 30 | update_spatial_index | update_spatial_index(state) | ✅ | order=20 |
| 40 | process_scouting | check_scout_results(state) | ✅ | order=30 |
| 50 | process_reports | check_pending_reports(state) | ✅ | order=40 |
| 60 | fire_events | scheduler.fire_due_events(state) | ✅ | 无 |
| 65 | process_deck_ops | 甲板加油/挂弹进度 | ⬜ 待实现 | order=60 |
| 66 | process_weather | 天气检查（每4tick） | ⬜ 待实现 | order=60 |
| 67 | process_enemy_ai | Kido Butai 决策 | ⬜ 待实现 | order=30 |
| 68 | process_midway_defense | 中途岛防空/反击 | ⬜ 待实现 | order=60 |
| 70 | check_game_over | 判定游戏是否结束 | ⬜ 待实现 | order=60 |
| 80 | reset_ap | 重置AP为max | ✅ | order=70 |

#### 扩展机制

```python
# 注册新步骤
pipeline.register(TickStep(
    name="process_weather",
    handler=process_weather,
    order=66,
    enabled=True
))

# 临时禁用步骤
pipeline.disable("process_enemy_ai")

# 替换步骤（同名覆盖）
pipeline.register(TickStep(name="advance_clock", handler=new_handler, order=10))
```

### 2.6 接口

| 函数 | 调用方 | 签名 | 副作用 |
|------|--------|------|--------|
| `consume_ap` | server.py (chat/action) | `(state, action) → bool` | 减少action_points |
| `has_ap` | server.py | `(state) → bool` | 无 |
| `reset_ap` | pipeline step 80 | `(state) → None` | 重置action_points |
| `init_turn` | 游戏初始化 | `(state, turn_type) → None` | 设置turn_type和AP |
| `Pipeline.execute` | server.py (/advance) | `(state, minutes) → list[str]` | 执行所有管线步骤 |
| `Pipeline.register` | 系统初始化 | `(step) → None` | 注册管线步骤 |
| `get_ap_status` | 前端 | `(state) → dict` | 无 |

#### REST 端点

| 端点 | 方法 | 请求 | 响应 |
|------|------|------|------|
| POST /advance | POST | `{"minutes": 15}` | `{"notifications": [...], "ap": {...}, "game_over": bool}` |

### 2.7 边界条件与异常

| 编号 | 场景 | 预期行为 |
|------|------|---------|
| TIME-EDGE-001 | AP=0时尝试操作 | 返回False，不执行操作 |
| TIME-EDGE-002 | 游戏结束后推进时间 | 返回空通知列表，不执行管线 |
| TIME-EDGE-003 | 管线步骤抛异常 | 记录日志，跳过该步骤，继续执行后续 |
| TIME-EDGE-004 | game_time刚好=08:00 | 执行完本tick后触发游戏结束 |
| TIME-EDGE-005 | game_time超过08:00（如07:45+15=08:00） | 正常执行tick，然后触发游戏结束 |

### 2.8 测试用例

#### 测试覆盖矩阵

| 规则编号 | 测试函数 | 测试类型 | 优先级 |
|---------|---------|---------|--------|
| TIME-001 | test_advance_clock | 单元 | P0 |
| TIME-001 | test_advance_clock_multiple_ticks | 单元 | P0 |
| TIME-002 | test_consume_ap_success | 单元 | P0 |
| TIME-002 | test_consume_ap_multiple | 单元 | P0 |
| TIME-003 | test_reset_ap | 单元 | P0 |
| TIME-004 | test_ap_no_negative | 边界 | P0 |
| TIME-005 | test_normal_turn_ap | 单元 | P0 |
| TIME-008 | test_pipeline_order | 单元 | P0 |
| TIME-008 | test_pipeline_step_exception_continues | 异常 | P1 |
| TIME-009 | test_pipeline_register_override | 单元 | P1 |
| TIME-010 | test_game_over_at_0800 | 集成 | P0 |
| TIME-011 | test_game_over_all_sunk | 集成 | P0 |
| TIME-012 | test_no_tick_after_game_over | 边界 | P0 |

#### 关键测试用例详述

**TC-TIME-008: 管线顺序**
- 注册3个步骤(order=30,10,20)，执行后验证handler调用顺序为10→20→30

**TC-TIME-008b: 步骤异常不影响后续**
- 步骤2抛异常，验证步骤3仍然执行

**TC-TIME-010: 时间到08:00**
- game_time=07:45，推进15min → game_time=08:00 → game_phase=GAME_OVER → 返回结局通知

**TC-TIME-012: 结束后不可推进**
- game_phase=GAME_OVER，调用tick() → 返回空列表，game_time不变

---

## 三、地理/坐标系统

### 3.1 概述

地理/坐标系统是所有空间计算的基础。负责：地理坐标（经纬度）↔ 六边形网格坐标（q,r）转换、实体间距离/方位计算、扇面区域生成、空间索引维护。

**职责边界**：
- 本系统负责：坐标转换、距离/方位计算、空间索引、扇面生成
- 本系统**不**负责：实体移动（实体系统）、侦察检测逻辑（侦察系统）、海图渲染（海图参谋系统）

**依赖关系**：
- 输入来自：实体系统（经纬度）、侦察系统（搜索扇面参数）
- 输出给到：侦察系统（距离/方位用于检定）、海图参谋系统（坐标用于渲染）、事件系统（空间索引每tick更新）
- 调用时机：每tick更新空间索引；侦察检定/扇面生成时按需调用

### 3.2 数据模型

#### 3.2.1 全局常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `REF_LAT` | 28.2 | 中途岛纬度 |
| `REF_LON` | -177.4 | 中途岛经度 |
| `CELL_SIZE_NM` | 10 | 每格10海里 |
| `GRID_RADIUS` | 40 | 40格半径 = 400nm覆盖范围 |

#### 3.2.2 Position 模型

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| lat | `float` | required, [-90, 90] | — | 纬度，正=北 |
| lon | `float` | required, [-180, 180] | — | 经度，负=西 |
| bearing | `Optional[int]` | [0, 359] | None | 相对方位（相对位置元数据） |
| distance_nm | `Optional[int]` | ≥ 0 | None | 相对距离nm（相对位置元数据） |
| reference | `Optional[str]` | — | None | 参考点名称 |

> ⚠️ 已知问题：state.py 和 entities.py 各有一个 Position 类，字段相同但不互通。规格以 state.py 为准。

#### 3.2.3 Hex 坐标

| 字段 | 类型 | 说明 |
|------|------|------|
| q | `int` | 轴向坐标，正=东 |
| r | `int` | 轴向坐标，正=北 |

#### 3.2.4 SpatialIndex 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| entity_positions | `dict[str, (q,r)]` | 实体ID → hex位置 |
| hex_entities | `dict[(q,r), set[str]]` | hex格 → 实体ID集合 |

#### 3.2.5 初始位置

| 单位 | 位置 | hex坐标 | 航向 | 航速 |
|------|------|---------|------|------|
| TF16（Enterprise） | 31.5°N 176.0°W | ≈(8, 20) | 240° | 25kn |
| TF16（Hornet） | 31.5°N 176.0°W | ≈(8, 20) | 240° | 25kn |
| Kido Butai | 31.0°N 180.0°W | ≈(-17, 17) | 110° | 20kn |
| 中途岛 | 28.2°N 177.4°W | (0, 0) | — | — |

#### 3.2.6 关键距离

| 路径 | 距离 | hex格数 | 战术意义 |
|------|------|---------|---------|
| TF16 → 中途岛 | ~211nm | ~21 | 在SBD作战半径内 |
| Kido Butai → 中途岛 | ~216nm | ~22 | — |
| TF16 → Kido Butai | ~207nm | ~21 | 超出SBD作战半径(167nm) |

### 3.3 状态机

地理系统无状态机——它是纯计算模块，无状态转换。

### 3.4 规则

| 编号 | 规则 | 条件 | 行为 | 边界/异常 | 测试关联 |
|------|------|------|------|----------|---------|
| GEO-001 | 地理→hex | 输入 lat, lon | 转为 (q,r) hex坐标，四舍五入到最近格 | lat超出[-90,90]或lon超出[-180,180]：抛ValueError | test_coordinate::test_world_to_hex |
| GEO-002 | hex→地理 | 输入 (q,r) | 转为 (lat,lon) 格中心点 | 任意 (q,r) 均有效，不抛异常 | test_coordinate::test_hex_to_world |
| GEO-003 | 坐标往返精度 | world→hex→world | 误差 < 0.01°（≈0.6nm） | — | test_coordinate::test_roundtrip |
| GEO-004 | hex距离 | 输入两个 (q,r) | 返回 hex 格数（cube distance） | — | test_coordinate::test_hex_distance |
| GEO-005 | hex距离→海里 | 输入两个 (q,r) | 返回 nautical miles = hex_dist × 10 | — | test_coordinate::test_hex_distance_nm |
| GEO-006 | hex方位 | 输入两个 (q,r) | 返回方位角 [0,360)，0=N, 90=E | 同一点返回0 | test_coordinate::test_hex_bearing |
| GEO-007 | 扇面生成 | center, bearing_min, bearing_max, radius | 返回扇面内所有 (q,r) 列表 | bearing_min > bearing_max 时按跨360°处理 | test_coordinate::test_hex_sector |
| GEO-008 | 扇面跨360° | bearing_min=350, bearing_max=10 | 包含 350°~360° 和 0°~10° 的格 | — | test_coordinate::test_sector_wrap_360 |
| GEO-009 | 方位在扇面内 | bearing, min, max | 返回 bool，处理跨360° | — | test_coordinate::test_bearing_in_sector |
| GEO-010 | hex邻居 | 输入 (q,r) | 返回6个邻居坐标 | — | test_coordinate::test_hex_neighbors |
| GEO-011 | hex在范围内 | (q,r), center, radius | 返回 bool | — | test_coordinate::test_hex_in_range |
| GEO-012 | 空间索引-更新 | entity_id, lat, lon | 从旧格移除，加入新格 | 旧格为空时自动清理 | test_spatial::test_update_entity |
| GEO-013 | 空间索引-移除 | entity_id | 从索引中完全移除 | 不存在的ID不抛异常 | test_spatial::test_remove_entity |
| GEO-014 | 空间索引-范围查询 | center, range_hex | 返回范围内所有实体 {id: (q,r)} | — | test_spatial::test_entities_in_range |
| GEO-015 | 空间索引-距离查询 | entity_a, entity_b | 返回 hex 距离，NM 距离 | 任一实体不存在返回 None | test_spatial::test_distance_between |
| GEO-016 | 空间索引-每tick重建 | GameState | clear() 后遍历所有实体重建 | 访问 _hidden_actual_enemy（已知设计问题） | test_spatial::test_update_spatial_index |
| GEO-017 | 空间索引-同格查询 | entity_id | 返回同格其他实体集合 | 实体不存在返回空集 | test_spatial::test_entities_in_same_hex |
| GEO-018 | 空间索引-邻居查询 | entity_id, range_hex | 返回范围内实体（不含自身） | 实体不存在返回空dict | test_spatial::test_entities_nearby |

### 3.5 算法与公式

#### 3.5.1 world_to_hex 坐标转换

**用途**：地理坐标 → hex坐标
**输入**：lat ∈ [-90,90], lon ∈ [-180,180]
**输出**：(q, r) ∈ ℤ × ℤ

**公式**：
```
dlat = lat - 28.2
dlon = lon - (-177.4)
nm_north = dlat × 60                    # 1°纬度 ≈ 60nm
nm_east = dlon × 60 × cos(28.2°)       # 1°经度 ≈ 52.9nm @ 28.2°N
q = round(nm_east / 10)
r = round(nm_north / 10)
```

**精度**：平面近似，400nm范围内误差 < 0.6nm

#### 3.5.2 hex_distance 距离计算

**用途**：两个hex格之间的距离
**输入**：(q1,r1), (q2,r2)
**输出**：距离（格数）∈ ℕ

**公式**：
```
s1 = -q1 - r1       # cube coordinate
s2 = -q2 - r2
distance = max(|q1-q2|, |r1-r2|, |s1-s2|)
```

#### 3.5.3 hex_bearing 方位计算

**用途**：从hex A 到 hex B 的方位角
**输入**：(q1,r1), (q2,r2)
**输出**：方位 ∈ [0, 360)，0=N, 90=E

**公式**：
```
1. hex→world 得到两组 (lat,lon)
2. y = sin(dlon) × cos(lat2)
3. x = cos(lat1)×sin(lat2) - sin(lat1)×cos(lat2)×cos(dlon)
4. bearing = (atan2(y,x) × 180/π + 360) % 360
```

#### 3.5.4 _round_hex 四舍五入

**用途**：浮点hex坐标四舍五入到最近整数格
**算法**：cube coordinate rounding
```
1. s = -q - r
2. rq, rr, rs = round(q), round(r), round(s)
3. 修正：取差值最大的轴，用 -其他两轴之和 重算
4. 确保 rq + rr + rs = 0
```

#### 3.5.5 移动距离计算

**用途**：每tick实体移动
**公式**：
```
移动距离(nm) = 速度(kn) × 时间(min) / 60
例：25kn × 15min / 60 = 6.25nm/tick
```

### 3.6 接口

| 函数 | 调用方 | 调用时机 | 签名 | 副作用 |
|------|--------|---------|------|--------|
| `world_to_hex` | spatial, scouting, 前端 | 坐标转换时 | `(lat: float, lon: float) → (int, int)` | 无（纯函数） |
| `hex_to_world` | scouting, rendering | 需要经纬度时 | `(q: int, r: int) → (float, float)` | 无（纯函数） |
| `hex_distance` | spatial, scouting | 距离计算时 | `(q1,r1,q2,r2) → int` | 无（纯函数） |
| `hex_sector` | scouting, rendering | 生成搜索扇面时 | `(center, bearing_min, bearing_max, radius) → list[(q,r)]` | 无（纯函数） |
| `SpatialIndex.update_entity` | events.py | 每tick | `(entity_id, lat, lon) → None` | 修改索引 |
| `update_spatial_index` | events.py | 每tick | `(state) → None` | 重建整个索引 |

### 3.7 边界条件与异常

| 编号 | 场景 | 预期行为 | 降级策略 |
|------|------|---------|---------|
| GEO-EDGE-001 | lat/lon 超出范围 | 抛 ValueError | — |
| GEO-EDGE-002 | 经度跨 180°/-180° 边界 | 自动包裹到 [-180, 180] | — |
| GEO-EDGE-003 | 实体移出 GRID_RADIUS 范围 | hex坐标仍有效，但不在地图可视范围 | 前端不渲染超出范围的实体 |
| GEO-EDGE-004 | 扇面跨 360° 边界 | bearing_in_sector 正确处理 wrap-around | — |
| GEO-EDGE-005 | 同一点计算方位 | 返回 0° | — |
| GEO-EDGE-006 | 空间索引中实体不存在 | 返回 None / 空集合，不抛异常 | — |
| GEO-EDGE-007 | _hidden_actual_enemy 访问 | 已知设计问题，当前直接访问私有属性 | 后续重构为公开接口 |

### 3.8 测试用例

#### 测试覆盖矩阵

| 规则编号 | 测试函数 | 测试类型 | 优先级 |
|---------|---------|---------|--------|
| GEO-001 | test_world_to_hex_basic | 单元 | P0 |
| GEO-001 | test_world_to_hex_ref_point | 单元 | P0 |
| GEO-001 | test_world_to_hex_invalid | 异常 | P1 |
| GEO-002 | test_hex_to_world | 单元 | P0 |
| GEO-003 | test_roundtrip_accuracy | 单元 | P0 |
| GEO-004 | test_hex_distance | 单元 | P0 |
| GEO-004 | test_hex_distance_same_cell | 边界 | P0 |
| GEO-005 | test_hex_distance_nm | 单元 | P0 |
| GEO-006 | test_hex_bearing_cardinal | 单元 | P0 |
| GEO-006 | test_hex_bearing_same_point | 边界 | P1 |
| GEO-007 | test_hex_sector_basic | 单元 | P0 |
| GEO-008 | test_sector_wrap_360 | 边界 | P0 |
| GEO-009 | test_bearing_in_sector | 单元 | P0 |
| GEO-009 | test_bearing_in_sector_wrap | 边界 | P0 |
| GEO-010 | test_hex_neighbors | 单元 | P1 |
| GEO-011 | test_hex_in_range | 单元 | P1 |
| GEO-012 | test_spatial_update | 单元 | P0 |
| GEO-013 | test_spatial_remove | 单元 | P0 |
| GEO-014 | test_spatial_range_query | 单元 | P0 |
| GEO-015 | test_spatial_distance | 单元 | P0 |
| GEO-015 | test_spatial_distance_not_found | 异常 | P1 |
| GEO-016 | test_spatial_full_rebuild | 集成 | P0 |
| GEO-017 | test_spatial_same_hex | 单元 | P1 |
| GEO-018 | test_spatial_nearby | 单元 | P1 |

#### 关键测试用例详述

**TC-GEO-001a: 中途岛参考点**
- 输入：lat=28.2, lon=-177.4
- 预期：(q=0, r=0)

**TC-GEO-001b: TF16 初始位置**
- 输入：lat=31.5, lon=-176.0
- 预期：q≈8, r≈20（允许±1误差）

**TC-GEO-003: 往返精度**
- 对 100 个随机坐标：world→hex→world
- 预期：所有 |lat差| < 0.01° 且 |lon差| < 0.01°

**TC-GEO-008: 扇面跨360°**
- 输入：center=(0,0), bearing_min=350, bearing_max=10, radius=5
- 预期：包含方位 355° 和 5° 的格

**TC-GEO-016: 空间索引完整重建**
- 输入：GameState 含 2 TF + 1 敌军 + 1 侦察机
- 预期：索引中 4 个实体，位置正确

---

## 四、状态系统

### 4.1 概述

状态系统是游戏数据的唯一真相来源（Single Source of Truth）。所有游戏数据都存储在 GameState 中，所有系统通过读写 GameState 进行交互。

**职责边界**：
- 本系统负责：定义所有数据模型、维护数据一致性、提供序列化/反序列化
- 本系统**不**负责：业务逻辑（由各领域系统处理）、数据持久化（由 server.py 处理）

**架构原则**：
- GameState 是扁平的 Pydantic v2 model，不做拆分（原型阶段保持简单）
- Position 类统一使用 state.py 版本，删除 entities.py 的重复定义
- _hidden_actual_enemy 改为公开属性 actual_enemy，NPC 访问控制由 NPC 系统的过滤函数负责
- AirGroup 保留，用于组织打击任务（编组 = 临时飞行编队）

### 4.2 数据模型

#### 4.2.1 GameState（顶层容器）

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| clock | `GameClock` | required | — | 游戏时钟 |
| game_phase | `GamePhase` | required | PLAYING | 游戏阶段（新增） |
| turn_type | `TurnType` | default | NORMAL | 回合类型 |
| action_points | `int` | ≥ 0 | 3 | 当前剩余AP |
| max_action_points | `int` | ≥ 0 | 3 | 当前回合最大AP |
| task_forces | `list[TaskForce]` | default | [] | 己方舰队 |
| known_enemy | `list[EnemyKnown]` | default | [] | 已知敌情（经玩家确认） |
| actual_enemy | `list[dict]` | default | [] | 真实敌情（原 _hidden_actual_enemy） |
| enemy_fleet | `Optional[EntityTaskForce]` | default | None | 敌军舰队实体（原 _enemy_fleet） |
| active_scouts | `list[ScoutMission]` | default | [] | 活跃侦察任务 |
| pending_reports | `list[PendingReport]` | default | [] | 待到达的侦察报告 |
| aircraft_losses | `list[AircraftLoss]` | default | [] | 飞机损失记录 |
| incoming_messages | `list[str]` | default | [] | 待显示消息 |
| pending_suggestions | `list[PendingSuggestion]` | default | [] | 待确认方案 |

#### 4.2.2 GamePhase 枚举（新增）

| 枚举 | 值 | 含义 |
|------|-----|------|
| PLAYING | "playing" | 游戏中 |
| GAME_OVER | "game_over" | 游戏结束 |

#### 4.2.3 Position（统一定义）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| lat | `float` | [-90, 90] | 纬度 |
| lon | `float` | [-180, 180] | 经度 |
| bearing | `Optional[int]` | [0, 359] | 相对方位（元数据） |
| distance_nm | `Optional[int]` | ≥ 0 | 相对距离（元数据） |
| reference | `Optional[str]` | — | 参考点名称 |

方法：`to_tuple() → (lat, lon)`

> ⚠️ 删除 entities.py 的 Position，统一使用此定义。

#### 4.2.4 Carrier

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| name | `str` | required | 舰名 |
| position | `Position` | required | 当前位置 |
| course | `int` | [0, 359] | 航向 |
| speed | `int` | [0, 35] | 航速(kn) |
| air_groups | `list[AirGroup]` | default | 飞行编组列表 |
| aircraft | `list[Aircraft]` | default | 具体飞机列表 |
| cap_strength | `int` | ≥ 0 | CAP巡逻强度 |
| damage_level | `int` | [0, 3] | 损伤等级 |

#### 4.2.5 其他模型

| 模型 | 字段数 | 说明 |
|------|--------|------|
| TaskForce | 4 | name, carriers[], course, speed |
| EnemyKnown | 5 | position, description, confidence, source, reported_at |
| ScoutMission | 18 | 含阶段、燃油、返航、损失追踪 |
| PendingReport | 10 | 含真实数据+失真数据 |
| AircraftLoss | 4 | scout_id, aircraft_number, reason, time |
| Aircraft | 11 | 含型号、状态、燃油、弹药、任务 |
| AirGroup | 7 | 飞行编组，用于组织打击任务 |
| MissionPlan | 12 | 出击规划（拦截点、油量、警告） |
| ScoutMission | 11 | 侦察任务（航线、阶段、检测结果） |
| PendingSuggestion | 4 | npc, action_type, details, proposed_at |
| GameClock | 2 | game_time, tick_minutes |

#### 4.2.6 枚举定义汇总

| 枚举 | 值 | 用途 |
|------|-----|------|
| GamePhase | PLAYING, GAME_OVER | 游戏生命周期 |
| TurnType | NORMAL, CRITICAL, EMERGENCY | 回合类型 |
| AircraftType | SBD, TBD, VF | 飞机型号 |
| AircraftStatus | READY, LOADING, IN_FLIGHT, RETURNING, LANDING, MAINTENANCE | 飞机状态 |
| AirGroupType | FIGHTER, DIVE_BOMBER, TORPEDO | 编组类型 |
| AirGroupStatus | READY, PLANNING, LAUNCHING, AIRBORNE, ATTACKING, RETURNING, REFUELING, REARMING, LOST | 编组状态 |
| SearchPattern | SECTOR, EXPANDING_SQUARE, PARALLEL | 搜索模式（扇形/扩展方形/平行） |
| ScoutPhase | PREPARING, OUTBOUND, SEARCHING, RETURNING, LANDED, LOST | 侦察阶段 |

### 4.3 状态机

状态系统本身无状态机——它是数据容器。状态机定义在各领域系统中（如时间系统的 GamePhase、侦察系统的 ScoutPhase）。

### 4.4 规则

| 编号 | 规则 | 条件 | 行为 | 边界/异常 | 测试关联 |
|------|------|------|------|----------|---------|
| STATE-001 | GameState 唯一性 | 全局 | 所有系统共享同一个 GameState 实例 | — | test_state::test_singleton |
| STATE-002 | Position 统一 | 全局 | 所有位置使用 state.py 的 Position 类 | entities.py 的 Position 已删除 | test_state::test_position_unified |
| STATE-003 | Position.to_tuple | 需要元组 | 返回 (lat, lon) | — | test_state::test_position_to_tuple |
| STATE-004 | actual_enemy 公开 | 全局 | 原 _hidden_actual_enemy 改为公开属性 actual_enemy | — | test_state::test_actual_enemy_accessible |
| STATE-005 | NPC 访问过滤 | NPC 查询 | NPC 系统通过过滤函数只看到 known_enemy，不看 actual_enemy | — | test_npc::test_npc_cannot_see_actual |
| STATE-006 | AirGroup 保留 | 全局 | air_groups 用于组织打击任务，aircraft 为具体飞机列表 | — | — |
| STATE-007 | 序列化完整 | API 响应 | GameState.model_dump() 包含所有公开字段 | actual_enemy 包含在序列化中 | test_state::test_serialization |
| STATE-008 | Pydantic 约束 | 赋值时 | 所有 Field 约束（ge, le, range）生效 | 违反约束抛 ValidationError | test_state::test_field_constraints |
| STATE-009 | 默认值正确 | 初始化 | GameState(clock=...) 中可选字段有合理默认值 | — | test_state::test_defaults |

### 4.5 算法与公式

状态系统无算法——它是纯数据容器，计算由各领域系统负责。

### 4.6 接口

| 操作 | 调用方 | 说明 |
|------|--------|------|
| GameState 初始化 | initial_state.py | 创建初始状态（04:00, TF16, KB 等） |
| model_dump() | server.py | 序列化为 dict（API 响应） |
| model_validate() | server.py | 从 dict 反序列化（加载存档） |
| 字段赋值 | 所有系统 | 直接修改 GameState 字段 |

### 4.7 边界条件与异常

| 编号 | 场景 | 预期行为 |
|------|------|---------|
| STATE-EDGE-001 | 违反 Pydantic 约束（如 speed=-1） | 抛 ValidationError |
| STATE-EDGE-002 | task_forces 为空 | 合法状态（游戏初始化前） |
| STATE-EDGE-003 | actual_enemy 为空但 known_enemy 不为空 | 不应发生，但不强制校验（原型阶段） |
| STATE-EDGE-004 | Position 经度跨 180° | 存储原始值，由地理系统处理包裹 |

### 4.8 测试用例

| 规则编号 | 测试函数 | 测试类型 | 优先级 |
|---------|---------|---------|--------|
| STATE-001 | test_gamestate_creation | 单元 | P0 |
| STATE-002 | test_position_unified | 单元 | P0 |
| STATE-003 | test_position_to_tuple | 单元 | P0 |
| STATE-004 | test_actual_enemy_accessible | 单元 | P0 |
| STATE-007 | test_serialization_roundtrip | 单元 | P0 |
| STATE-008 | test_field_constraints | 单元 | P0 |
| STATE-009 | test_defaults | 单元 | P1 |
| — | test_initial_state_valid | 集成 | P0 |

---

## 五、航空参谋系统（飞机系统）

### 5.1 概述

飞机系统模拟"航空参谋"（Air Officer）的角色。负责：飞机库存管理、编组（AirGroup）组织、起飞/着舰调度、燃油计算、战损追踪。

**职责边界**：
- 本系统负责：飞机状态管理、编组生命周期、燃油消耗、起飞/着舰、战损统计
- 本系统**不**负责：空间移动计算（由 movement.py 处理）、攻击检定（由骰子系统处理）、侦察搜索逻辑（由侦察系统处理）

**依赖关系**：
- 输入来自：玩家命令（"派出打击队"）、侦察系统（SBD 分配侦察）、事件系统（tick 驱动燃油消耗）
- 输出给到：空间系统（飞行中飞机位置）、骰子系统（攻击/着舰检定参数）、状态系统（飞机/编组数据）
- 调用时机：玩家下达出动命令时创建编组；每 tick 更新燃油和位置

**关键设计决策**：
- 飞机始终属于航母（Carrier.aircrafts），飞行中通过编组（AirGroup）追踪位置和状态
- 编组（AirGroup）保留，用于组织打击任务（历史真实：企业号打击队 = SBD中队 + TBD中队 + VF护航）
- CAP（战斗空中巡逻）为低优先级功能，本版不做

### 5.2 数据模型

#### 5.2.1 AircraftType 枚举

| 枚举 | 值 | 全称 | 用途 | 速度 |
|------|-----|------|------|------|
| SBD | "sbd" | SBD Dauntless | 俯冲轰炸 + 侦察 | 150kt 巡航 / 120kt 搜索 |
| TBD | "tbd" | TBD Devastator | 鱼雷攻击 | 120kt |
| VF | "vf" | F4F Wildcat | 战斗机护航 | 180kt |

#### 5.2.2 AircraftStatus 枚举

| 枚举 | 值 | 含义 | 所在位置 |
|------|-----|------|---------|
| READY | "ready" | 待命，可出动 | 航母机库 |
| LOADING | "loading" | 加油/挂弹中 | 航母甲板 |
| IN_FLIGHT | "in_flight" | 飞行中 | 空中（由 AirGroup 追踪） |
| RETURNING | "returning" | 返航中 | 空中 |
| LANDING | "landing" | 着舰中 | 甲板 |
| MAINTENANCE | "maintenance" | 维修/不可用 | 机库 |
| LOST | "lost" | 损失 | — |

#### 5.2.3 AirGroupStatus 枚举

| 枚举 | 值 | 含义 |
|------|-----|------|
| READY | "ready" | 编组待命 |
| PLANNING | "planning" | 参谋规划航线中，等待玩家确认 |
| LAUNCHING | "launching" | 起飞准备中（1 轮） |
| AIRBORNE | "airborne" | 已升空 |
| ATTACKING | "attacking" | 执行攻击 |
| RETURNING | "returning" | 返航 |
| REFUELING | "refueling" | 加油中 |
| REARMING | "rearming" | 重新挂弹 |
| LOST | "lost" | 编组损失 |

#### 5.2.4 Aircraft 数据模型

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | `str` | required | — | 飞机唯一标识 |
| aircraft_type | `AircraftType` | required | — | 飞机型号 |
| aircraft_status | `AircraftStatus` | required | READY | 当前状态 |
| aircraft_qty | `int` | ≥ 0 | — | 当前架数 |
| aircraft_max_qty | `int` | ≥ 0 | — | 最大架数 |
| fuel_pct | `float` | [0, 100] | 100.0 | 燃油百分比 |
| hp | `int` | ≥ 0 | 见规则 | 生命值 |
| max_hp | `int` | ≥ 0 | 见规则 | 最大生命值 |
| group_id | `Optional[str]` | — | None | 所属编组ID |
| mission | `Optional[str]` | — | None | 当前任务类型 |
| losses | `int` | ≥ 0 | 0 | 已损失架数 |

#### 5.2.5 MissionPlan 数据模型（出击规划）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | `str` | required | 规划唯一标识 |
| target_position | `Position` | required | 敌舰报告位置（含失真） |
| target_course | `int` | [0, 359] | 敌舰报告航向 |
| target_speed | `int` | ≥ 0 | 敌舰报告航速 |
| intercept_point | `Position` | required | 计算出的拦截点 |
| intercept_heading | `int` | [0, 359] | 飞机应飞航向 |
| intercept_distance_nm | `float` | ≥ 0 | 到拦截点距离 |
| flight_time_min | `float` | ≥ 0 | 预计飞行时间 |
| fuel_margin_pct | `float` | [-∞, 100] | 油量余裕（负=不可行） |
| warnings | `list[str]` | default [] | 警告列表 |
| feasible | `bool` | required | 是否可行 |
| npc_briefing_data | `dict` | required | 传给 NPC 的计算结果 |

#### 5.2.6 AirGroup 数据模型

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | `str` | required | — | 编组唯一标识 |
| carrier_name | `str` | required | — | 所属航母名称 |
| aircraft_ids | `list[str]` | default | [] | 编组内飞机ID列表 |
| status | `AirGroupStatus` | required | READY | 编组状态 |
| plan_id | `Optional[str]` | — | None | 关联的出击规划ID |
| mission_type | `Optional[str]` | — | None | 任务类型（strike/scout） |
| launched_at | `Optional[datetime]` | — | None | 起飞时间 |
| target_position | `Optional[Position]` | — | None | 目标位置（拦截点） |
| intercept_heading | `Optional[int]` | — | None | 飞机航向 |

#### 5.2.6 燃油消耗率

| 机型 | 巡航油耗 | 搜索油耗 | 满油航程 |
|------|---------|---------|---------|
| SBD | 0.6%/nm | 0.125%/min | 167nm |
| TBD | 0.6%/nm | 0.125%/min | 167nm |
| VF | 0.8%/nm | 0.15%/min | 125nm |

#### 5.2.7 初始配置

| 航母 | VF | SBD | TBD | 总计 |
|------|-----|------|------|------|
| Enterprise | 27 VF-6 | 38 SBD（含 McClusky） | 15 TBD（含 Waldron） | 80 |
| Hornet | 27 VF-8 | 38 SBD | 15 TBD | 80 |

机库容量：每艘航母 300 机位。

### 5.3 状态机

#### 5.3.1 Aircraft 生命周期

```
READY → LOADING → IN_FLIGHT → RETURNING → LANDING → READY
                                    ↘ LOST（燃油耗尽/被击落）
LOADING → IN_FLIGHT（起飞完成）
IN_FLIGHT → ATTACKING → IN_FLIGHT（攻击后继续飞行）
```

#### 5.3.2 AirGroup 生命周期

```
READY → PLANNING → LAUNCHING → AIRBORNE → ATTACKING → RETURNING → REFUELING → REARMING → READY
               ↘ READY（玩家拒绝）                              ↘ LOST（全机损失）
                                              AIRBORNE → RETURNING（玩家召回/燃油不足）
```

#### 5.3.3 状态转换表

| 编号 | 当前 | 触发 | 目标 | 动作 |
|------|------|------|------|------|
| AIR-SM-001 | READY | 玩家下达打击命令 | PLANNING | 系统计算拦截点和油量，参谋提出方案 |
| AIR-SM-001b | PLANNING | 玩家确认方案 | LAUNCHING | 创建 AirGroup，加入飞机 |
| AIR-SM-001c | PLANNING | 玩家拒绝方案 | READY | 取消规划，飞机保持待命 |
| AIR-SM-002 | LAUNCHING | 1 轮后 | AIRBORNE | 飞机状态→IN_FLIGHT，记录起飞时间 |
| AIR-SM-003 | AIRBORNE | 玩家召回 / 燃油≤15% | RETURNING | 开始返航 |
| AIR-SM-004 | AIRBORNE | 到达目标 | ATTACKING | 执行攻击检定 |
| AIR-SM-005 | ATTACKING | 攻击完成 | RETURNING | 开始返航 |
| AIR-SM-006 | RETURNING | 到达航母 | LANDING | 着舰检定（骰子系统五级） |
| AIR-SM-007 | LANDING | 大成功(95+) | READY | 飞机立即回到 READY |
| AIR-SM-007b | LANDING | 成功(70-94) | REFUELING | 飞机状态→LOADING |
| AIR-SM-007c | LANDING | 部分成功(40-69) | LANDING | 甲板占用 1 轮，然后→REFUELING |
| AIR-SM-008 | LANDING | 失败(10-39) | LANDING | 甲板占用 1 轮，二次检定 |
| AIR-SM-009 | LANDING | 大失败(≤9) / 二次失败 | LOST | 飞机坠海 |
| AIR-SM-010 | AIRBORNE | 燃油=0 | LOST | 飞机坠毁，编组可能全损 |
| AIR-SM-011 | REFUELING | 加油完成 | REARMING | — |
| AIR-SM-012 | REARMING | 挂弹完成 | READY | 飞机可再次出动 |

### 5.4 规则

| 编号 | 规则 | 条件 | 行为 | 边界/异常 | 测试关联 |
|------|------|------|------|----------|---------|
| AIR-001 | 飞机归属 | 全局 | 飞机始终属于航母（Carrier.aircrafts） | 飞行中通过 AirGroup 追踪，归属不变 | test_aircraft::test_ownership |
| AIR-002 | 编组创建 | 玩家下达出击命令 | 创建 AirGroup，将指定飞机加入 | 飞机状态必须为 READY | test_airgroup::test_create |
| AIR-003 | 编组取消 | 飞机全部损失 | AirGroup.status = LOST | — | test_airgroup::test_lost |
| AIR-004 | 起飞准备 | AirGroup.status=LAUNCHING | 1 轮后自动变为 AIRBORNE | 每轮只允许 1 个编组起飞 | test_airgroup::test_launch |
| AIR-005 | 燃油消耗-巡航 | 飞机 IN_FLIGHT | fuel_pct -= 油耗率 × 距离(nm) | VF 消耗更快（0.8%/nm） | test_aircraft::test_fuel_cruise |
| AIR-006 | 燃油消耗-盘旋 | 飞机 SEARCHING | fuel_pct -= 油耗率 × 时间(min) | — | test_aircraft::test_fuel_search |
| AIR-007 | 燃油耗尽 | fuel_pct ≤ 0 | 飞机状态→LOST | 记入 aircraft_losses | test_aircraft::test_fuel_empty |
| AIR-008 | 返航触发-自动 | fuel_pct ≤ 15% | AirGroup.status→RETURNING | — | test_aircraft::test_auto_return |
| AIR-009 | 返航触发-指令 | 玩家召回 | AirGroup.status→RETURNING | — | test_aircraft::test_manual_return |
| AIR-010 | 着舰检定 | 到达航母 | 沿用骰子系统五级结果（§7） | 修正值：NPC能力+夜间+燃油 | test_aircraft::test_landing_check |
| AIR-010a | 着舰-大成功 | 骰值 ≥ 95 | 飞机立即回到 READY | — | test_aircraft::test_landing_critical |
| AIR-010b | 着舰-成功 | 骰值 70-94 | 飞机回到 READY | — | test_aircraft::test_landing_success |
| AIR-010c | 着舰-部分成功 | 骰值 40-69 | 甲板占用 1 轮 | — | test_aircraft::test_landing_partial |
| AIR-011 | 着舰-失败 | 骰值 10-39 | 甲板占用 1 轮后重试 | 二次失败→飞机 LOST | test_aircraft::test_landing_fail |
| AIR-011b | 着舰-大失败 | 骰值 ≤ 9 | 飞机直接坠海，LOST | — | test_aircraft::test_landing_critical_fail |
| AIR-012 | 机库容量 | 航母飞机总数 | 不超过 300 架 | — | test_aircraft::test_hangar_capacity |
| AIR-013 | HP-SBD/TBD | 飞机被攻击 | max_hp = 3 | hp≤0 → LOST | test_aircraft::test_hp_sbd |
| AIR-014 | HP-VF | 飞机被攻击 | max_hp = 3 | hp≤0 → LOST | test_aircraft::test_hp_vf |
| AIR-015 | 损失追踪 | 飞机 LOST | 记录到 aircraft_losses | 含原因和时间 | test_aircraft::test_loss_tracking |
| AIR-016 | 着舰触发-自动 | AirGroup 燃油最低飞机 ≤ 5% | 自动触发着舰流程 | — | test_aircraft::test_auto_landing |
| AIR-017 | 拦截点计算 | 玩家下达打击命令 | 系统基于（失真的）侦察报告计算拦截点 | 飞机速度≤敌舰速度：无解 | test_mission::test_intercept_calc |
| AIR-018 | 油量预算 | 拦截点已计算 | 计算往返油量+搜索余量 | margin<0%：不可行 | test_mission::test_fuel_budget |
| AIR-019 | 出击规划流程 | 收到侦察报告后 | 参谋提出方案（航线、油量、风险），玩家确认/拒绝 | 参谋方案包含所有计算结果 | test_mission::test_planning_flow |
| AIR-020 | NPC 参谋报告 | 方案生成时 | 系统提供计算数据，NPC 生成自然语言简报 | 数据含拦截点、油量、夜间着舰风险 | test_mission::test_npc_briefing |
| AIR-021 | 方案拒绝 | 玩家拒绝方案 | 不起飞，等待新命令 | — | test_mission::test_plan_reject |
| AIR-022 | 方案确认 | 玩家确认方案 | 创建编组，进入 LAUNCHING | — | test_mission::test_plan_confirm |
| AIR-023 | 夜间着舰惩罚 | 返航时间 > 日落 | 着舰检定修正值 -30 | 参谋应提前警告 | test_aircraft::test_night_landing |
| AIR-024 | 夜间着舰灯光 | 夜间着舰时 | 需开启灯光引导 | 暴露风险增加（NPC应提示） | test_aircraft::test_night_landing_light |

### 5.5 算法与公式

#### 5.5.1 燃油消耗-巡航

**用途**：飞行中每 tick 消耗燃油
**公式**：
```
消耗率: SBD/TBD = 0.6%/nm, VF = 0.8%/nm
飞行距离(nm) = 速度(kn) × 时间(min) / 60
fuel_pct -= 消耗率 × 飞行距离
```

**示例**：
```
SBD, 150kt, 1tick(15min): 距离 = 150×15/60 = 37.5nm
消耗 = 0.6% × 37.5 = 22.5%
满油可飞: 100 / 0.6 = 166.7nm ≈ 4.4 tick
```

#### 5.5.2 燃油消耗-盘旋搜索

**用途**：侦察机盘旋搜索时消耗
**公式**：
```
消耗率: SBD/TBD = 0.125%/min, VF = 0.15%/min
fuel_pct -= 消耗率 × 时间(min)
```

**示例**：
```
SBD, 盘旋60min: 消耗 = 0.125% × 60 = 7.5%
```

#### 5.5.3 拦截点计算

**用途**：计算飞机应飞往的拦截点（敌舰会在那里）
**输入**：
- `P_enemy`：敌舰报告位置（lat, lon）— 含失真
- `C_enemy`：敌舰航向（°）
- `S_enemy`：敌舰航速（kn）
- `S_aircraft`：飞机速度（kn）
- `P_launch`：起飞位置（lat, lon）

**算法**：
```
1. 将 P_enemy, P_launch 转为 (x, y) 平面坐标（nm）
2. 敌舰速度矢量: V_enemy = (S_enemy × sin(C_enemy), S_enemy × cos(C_enemy))
3. 相对位置: D = P_enemy - P_launch
4. 解方程: |D + V_enemy × t| = S_aircraft × t
   展开: |D|² + 2(D · V_enemy)t + |V_enemy|²t² = S_aircraft²t²
   整理: (S_aircraft² - S_enemy²)t² - 2(D · V_enemy)t - |D|² = 0
   取正根: t = (2(D·V_enemy) + √(4(D·V_enemy)² + 4(S²-S_e²)|D|²)) / (2(S²-S_e²))
5. 拦截点: P_intercept = P_enemy + V_enemy × t
6. 飞机航向: θ = atan2(P_intercept.x - P_launch.x, P_intercept.y - P_launch.y)
```

**边界情况**：
- 飞机速度 ≤ 敌舰速度：无解（追不上），参谋应警告
- 距离过远（>满油航程）：无可行航线，参谋应拒绝规划
- 计算结果基于失真数据，实际拦截点可能偏差

#### 5.5.4 油量预算

**用途**：计算打击任务的油量是否充足
**输入**：
- `D_intercept`：到拦截点的距离（nm）
- `D_return`：拦截点到航母的距离（nm）
- `fuel_rate`：巡航油耗率（%/nm）
- `search_time`：预计盘旋搜索时间（min）
- `search_rate`：盘旋油耗率（%/min）

**公式**：
```
fuel_outbound = fuel_rate × D_intercept
fuel_return = fuel_rate × D_return
fuel_search = search_rate × search_time
fuel_reserve = 10%（安全余量）

fuel_total = fuel_outbound + fuel_return + fuel_search + fuel_reserve
margin = 100% - fuel_total

if margin < 0%:
    不可行，油量不足
elif margin < 10%:
    低油量警告（参谋应提示）
elif margin < 20%:
    注意油量（参谋应提及）
```

**参谋报告内容**（系统提供数据，NPC 生成自然语言）：

| 数据项 | 来源 | NPC 如何使用 |
|--------|------|-------------|
| 拦截点坐标 | 算法 5.5.3 | "目标预计在 XX 方位 XX 海里处" |
| 飞行时间 | 拦截距离 / 飞机速度 | "预计飞行 XX 分钟" |
| 油量余裕 | margin | "油量充足" / "油量紧张，建议减少搜索时间" / "油量不足，无法返航" |
| 夜间着舰风险 | 返航时间 > 日落 | "返航时天色已暗，着舰风险增加，建议开启灯光引导" |
| 敌军威胁评估 | 距离 + 敌军已知信息 | "目标区域可能有敌方战斗机巡逻" |
| 天气影响 | 天气系统 | "当前天气条件影响飞行" |

#### 5.5.5 着舰检定

**用途**：飞机返回航母时检定能否成功着舰
**机制**：沿用骰子系统（§7）三层分离

```
原始骰 = d100
NPC层  = Murray.competence(7) × 2 = +14
情境层 = 夜间(-30) + 燃油紧张(-10) + 天气(待定)（封顶 ±20）
总修正 = NPC层 + 情境层（封顶 ±30）

最终值 = 原始骰 + 总修正 → 五级结果
大成功/大失败 = 看原始骰
```

**五级结果映射**：

| 骰值 | 结果 | 着舰效果 |
|------|------|---------|
| 95+ | 大成功 | 完美着舰，飞机立即回到 READY |
| 70-94 | 成功 | 正常着舰 |
| 40-69 | 部分成功 | 粗暴着舰，甲板占用 1 轮 |
| 10-39 | 失败 | 着舰失败，甲板占用 1 轮后重试 |
| 9- | 大失败 | 坠海，飞机 LOST |

**重试机制**：
- 首次失败（10-39）：甲板占用 1 轮，再次检定
- 二次检定仍失败：飞机 LOST

#### 5.5.6 HP 初始值

| 机型 | HP | 说明 |
|------|-----|------|
| SBD | 3 | 俯冲轰炸机，装甲较好 |
| TBD | 2 | 鱼雷机，脆弱 |
| VF | 3 | 战斗机，装甲较好 |

#### 5.5.7 NPC 参谋简报数据结构

系统在出击规划时生成 `npc_briefing_data`，传给 LNPC 生成自然语言简报：

```python
npc_briefing_data = {
    # 目标信息（基于失真数据）
    "target": {
        "bearing": 240,           # 方位（°）
        "distance_nm": 200,       # 距离（nm）
        "course": 110,            # 航向
        "speed_kn": 20,           # 航速
        "description": "疑似航母编队",  # 来自侦察报告
        "confidence": "medium",   # 置信度
    },
    # 拦截方案
    "intercept": {
        "heading": 235,           # 飞机应飞航向
        "distance_nm": 185,       # 到拦截点距离
        "flight_time_min": 74,    # 飞行时间（分钟）
        "arrival_time": "07:14",  # 预计到达时间
    },
    # 油量评估
    "fuel": {
        "margin_pct": 22.5,       # 油量余裕
        "status": "adequate",     # sufficient/adequate/tight/critical/impossible
        "warning": None,          # 油量警告文本（或 None）
    },
    # 风险警告
    "warnings": [
        {"type": "night_landing", "text": "返航时天色已暗，着舰风险增加"},
        {"type": "fuel", "text": "油量紧张，建议减少搜索时间"},
        {"type": "enemy_cap", "text": "目标区域可能有敌方战斗机巡逻"},
    ],
    # 参谋建议
    "recommendation": "建议出击，但需缩短搜索时间以确保返航油量",
}
```

**NPC 使用方式**：
- LLM（Browning）接收此数据 + 角色设定 + 当前态势
- 生成自然语言简报，包含：目标描述、航线建议、油量评估、风险警告、最终建议
- 玩家确认/拒绝后，系统执行对应操作

### 5.6 接口

| 函数 | 调用方 | 签名 | 副作用 |
|------|--------|------|--------|
| `plan_mission` | server.py (打击命令) | `(state, enemy_report) → MissionPlan` | 计算拦截点、油量、生成警告 |
| `confirm_mission` | server.py (玩家确认) | `(state, plan_id) → AirGroup` | 创建编组，状态→LAUNCHING |
| `reject_mission` | server.py (玩家拒绝) | `(state, plan_id) → None` | 取消规划 |
| `launch_air_group` | pipeline (tick) | `(state, group_id) → None` | 状态 LAUNCHING→AIRBORNE |
| `update_fuel` | pipeline (tick) | `(state, minutes) → list[str]` | 消耗燃油，触发自动返航 |
| `process_landing` | pipeline (tick) | `(state) → list[str]` | 处理着舰检定 |
| `recall_air_group` | server.py (召回命令) | `(state, group_id) → None` | 状态→RETURNING |
| `get_aircraft_status` | 前端 | `(state, carrier_name) → dict` | 无（只读） |
| `get_air_group_status` | 前端 | `(state, group_id) → dict` | 无（只读） |
| `get_mission_plan` | NPC LLM | `(state, plan_id) → dict` | 返回规划数据供 NPC 生成简报 |

#### REST 端点

| 端点 | 方法 | 请求 | 响应 |
|------|------|------|------|
| POST /plan-strike | POST | `{"enemy_report_id": "..."}` | `{"plan_id": "...", "npc_briefing_data": {...}}` |
| POST /confirm-strike | POST | `{"plan_id": "..."}` | `{"group_id": "...", "status": "launching"}` |
| POST /reject-strike | POST | `{"plan_id": "..."}` | `{"status": "cancelled"}` |
| POST /recall | POST | `{"group_id": "..."}` | `{"status": "returning"}` |

### 5.7 边界条件与异常

| 编号 | 场景 | 预期行为 |
|------|------|---------|
| AIR-EDGE-001 | 飞机状态非 READY 时尝试出击 | 拒绝，返回错误信息 |
| AIR-EDGE-002 | 机库满（300架）时出击 | 拒绝，返回"机库已满" |
| AIR-EDGE-003 | 燃油恰好=0 | 飞机 LOST，不执行返航 |
| AIR-EDGE-004 | 编组所有飞机都 LOST | 编组状态→LOST |
| AIR-EDGE-005 | 着舰时航母已被击沉 | 飞机 LOST（无处降落） |
| AIR-EDGE-006 | 同时多个编组尝试起飞 | 每轮只允许 1 个，其余排队等待 |
| AIR-EDGE-007 | 玩家召回已返航的编组 | 忽略，返回"编组已在返航" |
| AIR-EDGE-008 | 飞机速度≤敌舰速度 | 拦截点计算无解，参谋报告"追不上" |
| AIR-EDGE-009 | 油量不足（margin<0） | 参谋报告"油量不足，无法返航"，方案标记不可行 |
| AIR-EDGE-010 | 夜间着舰 | 参谋警告"返航时天色已暗"，着舰检定惩罚 |
| AIR-EDGE-011 | 敌舰位置失真导致拦截失败 | 飞机到达后未发现敌舰，可盘旋搜索或返航 |
| AIR-EDGE-012 | 玩家拒绝方案 | 编组回到 READY，等待新命令 |

### 5.8 测试用例

#### 测试覆盖矩阵

| 规则编号 | 测试函数 | 测试类型 | 优先级 |
|---------|---------|---------|--------|
| AIR-001 | test_aircraft_ownership | 单元 | P0 |
| AIR-002 | test_create_air_group | 单元 | P0 |
| AIR-003 | test_air_group_all_lost | 单元 | P0 |
| AIR-004 | test_launch_cycle | 集成 | P0 |
| AIR-004 | test_launch_queue_multiple | 边界 | P1 |
| AIR-005 | test_fuel_cruise_sbd | 单元 | P0 |
| AIR-005 | test_fuel_cruise_tbd | 单元 | P0 |
| AIR-005 | test_fuel_cruise_vf | 单元 | P0 |
| AIR-005 | test_fuel_cruise_mixed_group | 集成 | P0 |
| AIR-006 | test_fuel_search | 单元 | P0 |
| AIR-007 | test_fuel_empty_crash | 边界 | P0 |
| AIR-007 | test_fuel_negative_clamp | 边界 | P1 |
| AIR-008 | test_auto_return_at_15pct | 单元 | P0 |
| AIR-008 | test_auto_return_threshold_15_1 | 边界 | P0 |
| AIR-008 | test_auto_return_threshold_14_9 | 边界 | P0 |
| AIR-009 | test_manual_return | 单元 | P0 |
| AIR-010 | test_landing_check_basic | 单元 | P0 |
| AIR-010a | test_landing_critical_success | 单元 | P0 |
| AIR-010b | test_landing_success | 单元 | P0 |
| AIR-010c | test_landing_partial_success | 单元 | P0 |
| AIR-011 | test_landing_fail_retry | 边界 | P0 |
| AIR-011b | test_landing_critical_fail | 边界 | P0 |
| AIR-011 | test_landing_fail_full_flow | 集成 | P0 |
| AIR-010 | test_landing_night_penalty | 边界 | P0 |
| AIR-010 | test_landing_fuel_penalty | 边界 | P1 |
| AIR-012 | test_hangar_capacity | 边界 | P1 |
| AIR-013 | test_hp_damage_sbd | 单元 | P0 |
| AIR-013 | test_hp_damage_tbd | 单元 | P0 |
| AIR-014 | test_hp_damage_vf | 单元 | P0 |
| AIR-014 | test_hp_lethal_hit | 边界 | P0 |
| AIR-015 | test_loss_tracking | 单元 | P0 |
| AIR-015 | test_loss_reasons | 单元 | P1 |
| AIR-016 | test_auto_landing | 单元 | P0 |
| AIR-017 | test_intercept_calc_basic | 单元 | P0 |
| AIR-017 | test_intercept_calc_no_solution | 边界 | P0 |
| AIR-017 | test_intercept_calc_distorted | 边界 | P0 |
| AIR-018 | test_fuel_budget_sufficient | 单元 | P0 |
| AIR-018 | test_fuel_budget_insufficient | 边界 | P0 |
| AIR-018 | test_fuel_budget_tight | 边界 | P1 |
| AIR-019 | test_planning_flow | 集成 | P0 |
| AIR-019 | test_full_lifecycle | 集成 | P0 |
| AIR-020 | test_npc_briefing_data | 单元 | P0 |
| AIR-021 | test_plan_reject | 单元 | P0 |
| AIR-022 | test_plan_confirm | 单元 | P0 |
| AIR-EDGE-005 | test_carrier_sunk_airborne | 边界 | P1 |
| AIR-EDGE-010 | test_night_landing_penalty | 边界 | P1 |

#### 关键测试用例详述

**TC-AIR-004: 起飞完整周期**
- 创建编组(LAUNCHING) → tick 1 → AIRBORNE → 验证飞机状态=IN_FLIGHT

**TC-AIR-005: SBD 燃油消耗**
- SBD 满油, 150kt, 飞行 1tick(15min) → fuel_pct ≈ 77.5%（消耗 22.5%）

**TC-AIR-007: 燃油耗尽**
- fuel_pct=0 → 飞机状态=LOST → 记入 aircraft_losses

**TC-AIR-010: 着舰检定基本**
- 骰值 80 + NPC修正(+17) = 97 → 大成功
- 验证：使用骰子系统 d100 + 修正值，结果映射到五级

**TC-AIR-010a: 着舰大成功**
- 骰值 ≥ 95 → 飞机直接回到 READY（无需加油挂弹）

**TC-AIR-010b: 着舰成功**
- 骰值 70-94 → 飞机进入 REFUELING → REARMING → READY

**TC-AIR-010c: 着舰部分成功**
- 骰值 40-69 → 甲板占用 1 轮 → 然后进入 REFUELING

**TC-AIR-011: 着舰失败重试**
- 骰值 10-39 → 甲板占用 1 轮 → 二次检定 → 成功则着舰

**TC-AIR-011b: 着舰大失败**
- 骰值 ≤ 9 → 飞机直接坠海，LOST，无需重试

**TC-AIR-010-夜间: 夜间着舰惩罚**
- 返航时间 > 日落 → 修正值 -30
- 骰值 50 + NPC(+17) + 夜间(-30) = 37 → 失败

**TC-AIR-010-燃油: 燃油紧张惩罚**
- fuel_pct < 10% → 修正值 -10
- 骰值 60 + NPC(+17) + 燃油(-10) = 67 → 部分成功

**TC-AIR-016: 自动着舰**
- 编组中最低燃油飞机 ≤ 5% → 自动触发着舰流程

**TC-AIR-017a: 拦截点基本计算**
- 敌舰位置 (31.0°N, 180.0°W)，航向 110°，航速 20kn
- 飞机从 (31.5°N, 176.0°W) 出发，速度 150kt
- 预期：拦截点在敌舰前方，飞行时间约 80min

**TC-AIR-017b: 拦截无解**
- 敌舰航速 25kn，飞机速度 180kt 但距离过远
- 预期：返回无解，参谋报告"无法拦截"

**TC-AIR-018a: 油量充足**
- SBD 满油，拦截距离 100nm
- 预期：margin ≈ 40%，状态 "sufficient"

**TC-AIR-018b: 油量不足**
- SBD 满油，拦截距离 180nm（超过满油航程 167nm）
- 预期：margin < 0%，feasible = False

**TC-AIR-020: NPC 简报数据完整性**
- 调用 plan_mission() → 检查 npc_briefing_data 包含所有必需字段
- 预期：包含 target、intercept、fuel、warnings、recommendation

**TC-AIR-003: 编组全损**
- 编组 3 架飞机全部燃油耗尽 → 全部 LOST
- 预期：AirGroup.status = LOST

**TC-AIR-005c: TBD 燃油消耗**
- TBD 满油，120kt，飞行 1tick(15min)
- 预期：消耗 = 0.6% × (120×15/60) = 18%，fuel_pct ≈ 82%

**TC-AIR-005d: 混合机型编组燃油**
- 编组含 SBD+TBD+VF，各飞 1tick
- 预期：VF 消耗最多（0.8%/nm），SBD/TBD 消耗相同（0.6%/nm）

**TC-AIR-007b: 燃油负值钳制**
- fuel_pct = 2%，消耗 5% → fuel_pct = 0（不为负），飞机 LOST

**TC-AIR-008a: 自动返航阈值上界**
- fuel_pct = 15.1% → 不触发自动返航

**TC-AIR-008b: 自动返航阈值下界**
- fuel_pct = 14.9% → 触发自动返航

**TC-AIR-011c: 着舰失败完整流程**
- 第一次失败 → 甲板占用 1 轮 → 第二次失败 → 飞机 LOST → 记入损失
- 验证：状态转换、甲板占用、损失记录

**TC-AIR-013a: SBD 被攻击**
- SBD hp=3，受到 2 点伤害 → hp=1，存活
- 再受 2 点伤害 → hp≤0，状态=LOST

**TC-AIR-013b: TBD 被攻击**
- TBD hp=2，受到 3 点伤害 → hp≤0，状态=LOST

**TC-AIR-014b: 致命一击**
- VF hp=3，受到 5 点伤害 → hp≤0，状态=LOST（不为负）

**TC-AIR-015b: 不同损失原因**
- 燃油耗尽 → reason="fuel_exhausted"
- 着舰失败 → reason="landing_failed"
- 被击落 → reason="shot_down"
- 验证：AircraftLoss.reason 正确记录

**TC-AIR-017c: 失真数据拦截**
- 侦察报告方位偏移 5°，距离偏移 10%
- 预期：拦截点计算仍返回可行方案，但与真实位置有偏差

**TC-AIR-019b: 完整生命周期**
- READY → plan_mission → PLANNING → confirm → LAUNCHING → tick → AIRBORNE → attack → RETURNING → LANDING → success → READY
- 验证：每步状态正确、燃油消耗正确、损失记录正确

**TC-AIR-EDGE-005: 航母被击沉时空中飞机**
- 编组 AIRBORNE，航母被击沉
- 预期：飞机状态→LOST，编组→LOST

**TC-AIR-EDGE-010: 夜间着舰惩罚**
- 返航时间 > 日落（19:00）
- 预期：着舰检定修正值 -30（骰子系统统一）

---

## 六、侦察系统

### 6.1 概述

侦察系统负责：搜索模式定义、航线生成、空间相遇检测、侦察检定、侦察报告生成。侦察机本质上是执行侦察任务的 AirGroup（§5），本系统定义其特殊逻辑。

**职责边界**：
- 本系统负责：搜索模式、航线生成、空间相遇、侦察检定、报告生成
- 本系统**不**负责：飞机状态管理（由航空参谋系统处理）、空间计算（由地理系统处理）、骰子机制（由骰子系统处理）

**依赖关系**：
- 输入来自：玩家命令（"派侦察机搜索东北方"）、航空参谋系统（飞机、燃油）、地理系统（hex 距离/方位）
- 输出给到：状态系统（侦察报告）、海图系统（侦察航线显示）
- 调用时机：玩家下达侦察命令时规划航线；每 tick 检测空间相遇

**关键设计**：
- 侦察 = 空间相遇 + 骰子检定（两层）
- 搜索模式决定侦察机飞过哪些 hex 格子
- 掷骰子决定发现质量（五级结果）
- 侦察机是 AirGroup 的一种（mission_type = "scout"）

### 6.2 数据模型

#### 6.2.1 SearchPattern 枚举

| 枚举 | 值 | 含义 |
|------|-----|------|
| SECTOR | "sector" | 扇形搜索 |
| EXPANDING_SQUARE | "expanding_square" | 扩展方形 |
| PARALLEL | "parallel" | 平行搜索 |

#### 6.2.2 ScoutPhase 枚举

侦察机生命周期状态（合并到 AirGroup，此处定义逻辑阶段）：

| 枚举 | 值 | 含义 |
|------|-----|------|
| PREPARING | "preparing" | 准备中 |
| OUTBOUND | "outbound" | 出航中（飞向搜索区域） |
| SEARCHING | "searching" | 搜索中（沿航线飞行并检测） |
| RETURNING | "returning" | 返航中 |
| LANDED | "landed" | 已降落 |
| LOST | "lost" | 损失 |

#### 6.2.3 ScoutMission 数据模型

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | `str` | required | 任务唯一标识 |
| air_group_id | `str` | required | 关联的 AirGroup |
| search_pattern | `SearchPattern` | required | 搜索模式 |
| route | `list[(q,r)]` | required | 航线（hex 坐标列表） |
| route_index | `int` | ≥ 0 | 当前航线位置索引 |
| phase | `ScoutPhase` | required | 当前阶段 |
| fuel_budget | `float` | [0, 100] | 预估油量消耗 |
| fuel_margin | `float` | [-∞, 100] | 油量余裕 |
| warnings | `list[str]` | default [] | 警告列表 |
| detections | `list[dict]` | default [] | 已发现目标列表 |

#### 6.2.4 搜索模式参数

| 模式 | 参数 | 值域 | 说明 |
|------|------|------|------|
| 扇形 | center_bearing | [0, 359] | 中心方位 |
| 扇形 | sector_width | [30, 90] | 扇面宽度（°） |
| 扇形 | radius_nm | [50, 300] | 搜索半径（nm） |
| 扩展方形 | max_radius_nm | [50, 300] | 最大半径 |
| 平行 | bearing | [0, 359] | 主方向 |
| 平行 | width_nm | [50, 300] | 宽度 |
| 平行 | spacing_nm | [10, 30] | 间距 |

### 6.3 状态机

```
READY → PLANNING → LAUNCHING → AIRBORNE(OUTBOUND) → AIRBORNE(SEARCHING) → AIRBORNE(RETURNING) → LANDING → READY
               ↘ READY（玩家拒绝）                                                       ↘ LOST
```

| 编号 | 当前 | 触发 | 目标 | 动作 |
|------|------|------|------|------|
| SC-SM-001 | READY | 玩家下达侦察命令 | PLANNING | Browning 规划航线和油量 |
| SC-SM-002 | PLANNING | 玩家确认方案 | LAUNCHING | 创建 AirGroup（mission_type=scout） |
| SC-SM-003 | PLANNING | 玩家拒绝方案 | READY | 取消规划 |
| SC-SM-004 | LAUNCHING | 1 tick 后 | OUTBOUND | 飞机起飞，沿航线飞行 |
| SC-SM-005 | OUTBOUND | 到达搜索区域 | SEARCHING | 开始搜索检测 |
| SC-SM-006 | SEARCHING | 航线完成 / 燃油≤15% | RETURNING | 开始返航 |
| SC-SM-007 | RETURNING | 到达航母 | LANDING | 着舰检定 |
| SC-SM-008 | LANDING | 着舰成功 | READY | 飞机回到待命 |
| SC-SM-009 | LANDING | 着舰失败 | LOST | 飞机损失 |
| SC-SM-010 | AIRBORNE | 燃油=0 | LOST | 飞机坠毁 |
| SC-SM-011 | AIRBORNE | 反向检定大失败 | LOST | 被敌方击落 |

### 6.4 规则

| 编号 | 规则 | 条件 | 行为 | 边界/异常 | 测试关联 |
|------|------|------|------|----------|---------|
| SC-001 | 扇形搜索 | 已知敌方大致方位 | 生成三角锥形航线 | 跨360°边界时正确包裹 | test_scout::test_sector_route |
| SC-002 | 扩展方形 | 完全未知 | 生成螺旋方形航线 | — | test_scout::test_expanding_square |
| SC-003 | 平行搜索 | 怀疑某方向 | 生成锯齿形航线 | — | test_scout::test_parallel_track |
| SC-004 | 航线长度 | 航线生成后 | 计算总长度（nm） | — | test_scout::test_route_length |
| SC-005 | 空间相遇 | 侦察机 hex == 敌舰 hex 或相邻 | 触发骰子检定 | — | test_scout::test_detect_same_hex |
| SC-006 | 侦察检定 | 空间相遇成立 | d100 + NPC层 + 情境层 → 五级结果 | 大成功/大失败看原始骰 | test_scout::test_detect_dice |
| SC-007 | 反向检定 | 侦察检定完成 | 敌方掷骰子能否发现侦察机 | 大失败→侦察机被击落 | test_scout::test_detect_reverse |
| SC-008 | 搜索完成 | 航线最后一个 hex | 自动切换到 RETURNING | — | test_scout::test_search_complete |
| SC-009 | 自动返航 | 燃油 ≤ 15% | 切换到 RETURNING | — | test_scout::test_auto_return |
| SC-010 | 侦察报告 | 检定成功 | 生成侦察报告（含位置、类型、数量） | 报告延迟到达 | test_scout::test_report |
| SC-011 | 油量预算 | 规划时 | 计算往返油量 + 搜索余量 | margin < 0%：不可行 | test_scout::test_fuel_budget |
| SC-012 | 模式选择 | 玩家命令 | 根据情报状态推荐搜索模式 | — | test_scout::test_pattern_selection |
| SC-013 | 着舰检定 | RETURNING→LANDING | 沿用骰子系统五级结果 | 夜间修正 -30 | test_scout::test_landing |
| SC-014 | 飞机损失 | 燃油耗尽/被击落/着舰失败 | 记入 aircraft_losses | — | test_scout::test_loss |
| SC-015 | 侦察报告延迟 | 报告生成后 | 基础20min + 距离因子 + 随机抖动 | — | test_scout::test_report_delay |

### 6.5 算法与公式

#### 6.5.1 扇形搜索航线生成

**输入**：fleet_pos(舰队位置), center_bearing(中心方位), sector_width(扇面宽度), radius(半径)
**输出**：list[(q,r)] 航线 hex 列表

```
1. bearing_min = center_bearing - sector_width/2
2. bearing_max = center_bearing + sector_width/2
3. 出航段：从 fleet_pos 沿 center_bearing 飞到半径
   - 每 10nm 一个 hex，共 radius/10 个 hex
4. 弧线段：在半径处沿弧线扫荡
   - 从 bearing_min 到 bearing_max，每 10° 一个点
   - 每个点计算 hex 坐标
5. 返航段：从弧线末端沿最短路径返回 fleet_pos
```

#### 6.5.2 扩展方形航线生成

**输入**：fleet_pos(舰队位置), max_radius(最大半径)
**输出**：list[(q,r)] 航线 hex 列表

```
1. 从 fleet_pos 开始
2. 方向序列：北→东→南→西→北→东→...（每层重复）
3. 步长：每层增加 1 格（1,1,2,2,3,3,...）
4. 直到达到 max_radius
```

#### 6.5.3 平行搜索航线生成

**输入**：fleet_pos(舰队位置), bearing(主方向), width(宽度), spacing(间距)
**输出**：list[(q,r)] 航线 hex 列表

```
1. 计算平行线数量 = width / spacing
2. 每条线沿 bearing 方向，长度 = width
3. 相邻线间距 = spacing
4. 交替方向（来回扫荡）
```

#### 6.5.4 空间相遇检测

**输入**：scout_hex(侦察机当前 hex), enemy_positions(敌舰位置列表)
**输出**：list[enemy_id] 相遇的敌舰列表

```
对每个敌舰：
  enemy_hex = world_to_hex(enemy.lat, enemy.lon)
  if hex_distance(scout_hex, enemy_hex) <= 1:
    加入相遇列表
```

#### 6.5.5 侦察检定

**输入**：detection_list(相遇敌舰列表), npc_competence(侦察NPC能力)
**输出**：list[detection_result] 检定结果列表

```
对每次相遇：
  原始骰 = d100
  NPC层 = npc_competence × 2（封顶 +20）
  情境层 = 距离修正 + 搜索模式修正（封顶 ±20）
  总修正 = NPC层 + 情境层（封顶 ±30）
  最终值 = 原始骰 + 总修正（钳制 1-100）

  结果 = 五级结果映射（最终值）
  if 原始骰 >= 95: 结果 = 大成功
  if 原始骰 <= 9: 结果 = 大失败

  反向检定：
  敌方骰 = d100 + 敌方能力修正
  if 敌方骰 >= 95: 侦察机被击落
```

#### 6.5.6 五级侦察结果

| 骰值 | 结果 | 侦察效果 |
|------|------|---------|
| 95+ | 大成功 | 清晰识别舰型、数量、航向、航速 |
| 70-94 | 成功 | 识别大致类型和数量 |
| 40-69 | 部分成功 | 看到有船，不确定类型 |
| 10-39 | 失败 | 漏报（没看到） |
| 9- | 大失败 | 被击落或严重误报 |

#### 6.5.7 报告延迟

```
基础延迟 = 20 分钟
距离因子 = (距离_nm / 200) × 25 分钟
随机抖动 = random(-5, +10) 分钟
总延迟 = 基础延迟 + 距离因子 + 随机抖动
范围：20-55 分钟
```

### 6.6 接口

| 函数 | 调用方 | 签名 | 副作用 |
|------|--------|------|--------|
| `generate_route` | server.py (侦察命令) | `(pattern, params) → list[(q,r)]` | 生成航线 hex 列表 |
| `calculate_fuel_budget` | server.py | `(route, aircraft_type) → dict` | 计算油量消耗和余裕 |
| `plan_scout_mission` | server.py | `(state, pattern, params) → ScoutMission` | Browning 规划侦察任务 |
| `confirm_scout` | server.py | `(state, mission_id) → AirGroup` | 确认并创建 AirGroup |
| `reject_scout` | server.py | `(state, mission_id) → None` | 取消规划 |
| `process_scouting` | pipeline (tick) | `(state) → list[str]` | 处理侦察机移动和检测 |
| `check_detection` | pipeline (tick) | `(scout_hex, state) → list[dict]` | 空间相遇检测 |
| `roll_scout_check` | pipeline (tick) | `(detection) → dict` | 侦察骰子检定 |
| `roll_reverse_check` | pipeline (tick) | `(detection) → dict` | 反向检定 |

#### REST 端点

| 端点 | 方法 | 请求 | 响应 |
|------|------|------|------|
| POST /plan-scout | POST | `{"pattern": "sector", "bearing": 45, "width": 60, "radius": 200}` | `{"mission_id": "...", "route": [...], "fuel_margin": 22.5}` |
| POST /confirm-scout | POST | `{"mission_id": "..."}` | `{"group_id": "...", "status": "launching"}` |

### 6.7 边界条件与异常

| 编号 | 场景 | 预期行为 |
|------|------|---------|
| SC-EDGE-001 | 航线超出 GRID_RADIUS | 截断航线，参谋警告"超出搜索范围" |
| SC-EDGE-002 | 油量不足（margin < 0） | 参谋拒绝规划，报告"油量不足，无法返航" |
| SC-EDGE-003 | 扇形跨360°边界 | bearing_in_sector 正确处理 wrap-around |
| SC-EDGE-004 | 搜索区域内无敌舰 | 搜索完成，返回"未发现敌踪" |
| SC-EDGE-005 | 侦察机燃油中途耗尽 | 侦察机 LOST，记入损失 |
| SC-EDGE-006 | 反向检定大失败 | 侦察机被击落，LOST |
| SC-EDGE-007 | 夜间着舰 | 着舰检定修正值 -30 |
| SC-EDGE-008 | 航母被击沉时侦察机在途 | 侦察机 LOST |
| SC-EDGE-009 | 同一 hex 内多个敌舰 | 一次检定发现所有敌舰 |

### 6.8 测试用例

#### 测试覆盖矩阵

| 规则编号 | 测试函数 | 测试类型 | 优先级 |
|---------|---------|---------|--------|
| SC-001 | test_sector_route_basic | 单元 | P0 |
| SC-001 | test_sector_route_wrap_360 | 边界 | P0 |
| SC-002 | test_expanding_square_route | 单元 | P0 |
| SC-003 | test_parallel_track_route | 单元 | P1 |
| SC-004 | test_route_length | 单元 | P0 |
| SC-005 | test_detect_same_hex | 单元 | P0 |
| SC-005 | test_detect_adjacent_hex | 单元 | P0 |
| SC-005 | test_detect_no_enemy | 单元 | P0 |
| SC-006 | test_detect_dice_quality | 单元 | P0 |
| SC-007 | test_detect_reverse | 单元 | P1 |
| SC-007 | test_detect_scout_shot_down | 边界 | P1 |
| SC-007 | test_detect_multiple_enemies | 边界 | P1 |
| SC-008 | test_search_complete | 集成 | P0 |
| SC-009 | test_auto_return | 单元 | P0 |
| SC-010 | test_report_generation | 单元 | P0 |
| SC-011 | test_fuel_budget_sufficient | 单元 | P0 |
| SC-011 | test_fuel_budget_insufficient | 边界 | P0 |
| SC-011 | test_fuel_search_time | 单元 | P1 |
| SC-012 | test_pattern_selection | 单元 | P1 |
| SC-013 | test_scout_landing | 单元 | P0 |
| SC-014 | test_scout_loss | 单元 | P0 |
| SC-015 | test_report_delay | 单元 | P0 |
| SC-001 | test_scout_launch | 集成 | P0 |
| SC-001 | test_scout_move_along_route | 集成 | P0 |
| SC-011 | test_scout_fuel_empty_mid_route | 边界 | P0 |
| SC-005 | test_scout_no_enemies_found | 边界 | P0 |
| SC-EDGE-001 | test_scout_enemy_at_edge | 边界 | P1 |
| SC-EDGE-007 | test_scout_night_penalty | 边界 | P1 |
| SC-EDGE-008 | test_scout_carrier_sunk | 边界 | P1 |

#### 关键测试用例详述

**TC-SC-001a: 扇形搜索基本**
- 方位 045°，扇面 60°，半径 200nm
- 预期：航线包含出航段 + 弧线段 + 返航段，总长度 ≈ 600nm

**TC-SC-001b: 扇形跨360°**
- 方位 350°，扇面 40°（覆盖 330°-10°）
- 预期：航线正确包含 350° 和 5° 方向的 hex

**TC-SC-002: 扩展方形**
- 最大半径 100nm
- 预期：航线为螺旋方形，覆盖约 20-40 格

**TC-SC-005a: 空间相遇-同格**
- 侦察机在 (10, 20)，敌舰也在 (10, 20)
- 预期：相遇成立，触发检定

**TC-SC-005b: 空间相遇-相邻格**
- 侦察机在 (10, 20)，敌舰在 (11, 20)
- 预期：相遇成立（相邻格子）

**TC-SC-006: 侦察检定质量**
- 原始骰 80 + NPC(+18) = 98 → 大成功
- 预期：清晰识别舰型、数量

**TC-SC-007: 反向检定**
- 敌方骰 96 → 大成功
- 预期：侦察机被击落

**TC-SC-011a: 油量充足**
- 航线长度 100nm，SBD 满油
- 预期：margin ≈ 40%，可行

**TC-SC-011b: 油量不足**
- 航线长度 200nm，SBD 满油
- 预期：margin < 0%，不可行

**TC-SC-015: 报告延迟**
- 距离 200nm
- 预期：延迟 = 20 + 25 + 随机 = 40-55 分钟

---

## 七、骰子系统

### 7.1 核心机制

> **统一原则**：本游戏中任何需要判定的场合（侦察、攻击、着舰、NPC 行为、天气等），必须复用本骰子系统。各系统不得自创判定机制。

**三层分离架构**：

```
原始骰 = d100 (1-100)              ← 随机性层
NPC层  = competence × 2（封顶 +20） ← 执行者能力层
情境层 = Σ 情境修正（封顶 ±20）     ← 外部条件层

总修正 = NPC层 + 情境层（封顶 ±30）
最终值 = 原始骰 + 总修正（钳制到 1-100）
```

**关键区分**：
- **五级结果**：看**最终值**（修正后）→ 决定成败程度
- **大成功/大失败**：看**原始骰**（修正前）→ 保持随机惊喜

### 7.2 五级结果

| 最终值 | 结果 | 含义 |
|--------|------|------|
| 95+ | 大成功 | 超出预期，历史转折 |
| 70-94 | 成功 | 达成目标 |
| 40-69 | 部分成功 | 达成但有代价 |
| 10-39 | 失败 | 未达成 |
| 9- | 大失败 | 灾难性后果 |

**大成功/大失败附加判定**：
- 原始骰 ≥ 95 → 即使最终值未达 95，也算大成功
- 原始骰 ≤ 9 → 即使最终值 > 9，也算大失败
- 这保证了即使 NPC 能力很高，仍有 5% 概率出意外

### 7.3 NPC 参数修正

所有 NPC 参数统一为 0-10 整数，乘数统一为 ×2：

| 参数 | 值域 | 乘数 | 修正范围 | 用途 |
|------|------|------|---------|------|
| competence | 0-10 | ×2 | 0~+20 | 执行检定时使用（侦察、攻击、着舰等） |
| autonomy | 0-10 | ×2 | 0~+20 | NPC 自主决策时使用 |
| risk_tolerance | 0-10 | ×2 | 0~+20 | NPC 风险评估时使用 |
| initiative | 0-10 | ×2 | 0~+20 | NPC 主动行为时使用 |

**使用规则**：
- 执行类检定（侦察/攻击/着舰）：只用 **competence**
- NPC 自主决策（是否主动出击/是否冒险）：用 **autonomy + initiative + risk_tolerance**
- 单次检定只取一个参数，不叠加多个 NPC 参数

### 7.4 情境修正

| 条件 | 修正 | 适用场景 |
|------|------|---------|
| 距离 < 100nm | +10 | 侦察 |
| 距离 > 150nm | -10 | 侦察 |
| 扇形搜索 | +5 | 侦察 |
| 平行搜索 | -5 | 侦察 |
| 方格搜索 | 0 | 侦察 |
| 夜间 | -30 | 着舰 |
| 燃油紧张（<10%） | -10 | 着舰 |
| 天气恶劣 | -10 | 通用（待实现） |

**情境修正封顶**：单次检定的情境修正合计不超过 ±20

### 7.5 优势/劣势骰

- 优势：掷 2 个 d100，取较高值
- 劣势：掷 2 个 d100，取较低值
- 不叠加：同时有优势和劣势时互相抵消

### 7.6 封顶规则

| 层 | 封顶 | 说明 |
|-----|------|------|
| NPC层 | +20 | competence 最大 10×2 |
| 情境层 | ±20 | 所有情境修正合计 |
| 总修正 | ±30 | NPC层 + 情境层 |
| 最终值 | 1-100 | 钳制到有效范围 |

### 7.7 应用场景

| 场景 | 函数 | NPC参数 | 情境修正 |
|------|------|---------|---------|
| 侦察检定 | `roll_scout_check()` | competence | 距离 + 搜索模式 |
| 攻击检定 | `roll_attack_check()` | competence | 目标状态 + 距离 |
| 着舰检定 | `roll_landing_check()` | competence | 夜间 + 燃油 + 天气 |
| 天气检定 | `roll_weather_check()` | — | 季节（待实现） |
| NPC 自主决策 | `roll_npc_decision()` | autonomy + initiative | 态势（待实现） |

---

## 八、NPC 系统

### 8.1 概述

NPC 系统管理游戏中的参谋角色。每个 NPC 有独立的人格参数、信息权限和行为模式。NPC 由 LLM 驱动，系统提供游戏数据，LLM 生成自然语言回应。

**职责边界**：
- 本系统负责：NPC 数据定义、信息过滤、行为触发、LLM 数据准备
- 本系统**不**负责：游戏逻辑执行（由各业务系统处理）、骰子检定（由骰子系统处理）

**依赖关系**：
- 输入来自：GameState（全局态势）、各系统事件（触发 NPC 发言）
- 输出给到：前端（NPC 对话）、玩家（决策建议）
- 调用时机：玩家主动对话时；事件触发时；tick 驱动时（主动报告）

### 8.2 数据模型

#### 8.2.1 NPC 参数表

所有参数统一为 0-10 整数（骰子系统 §7.3）：

| NPC | 职位 | 自主度 | 风险容忍 | 主动性 | 能力 | 信息权限 |
|-----|------|--------|---------|--------|------|---------|
| Browning | 参谋长 | 8 | 8 | 9 | 9 | 全局态势 |
| Murray | 企业号舰长 | 5 | 4 | 5 | 7 | 本舰 |
| Mitscher | 大黄蜂舰长 | 5 | 4 | 5 | 7 | 本舰 |
| 通信官 | 通信官 | 1 | 1 | 2 | 6 | 电报 |
| 情报官 | 情报参谋 | 3 | 3 | 4 | 7 | 情报 |

#### 8.2.2 信息权限定义

| 权限等级 | 可见内容 | 持有者 |
|---------|---------|--------|
| 全局态势 | 所有己方位置、所有侦察报告、敌方已知信息、AP/时钟 | Browning |
| 本舰 | 本舰状态、本舰飞机、本舰位置 | Murray, Mitscher |
| 电报 | 通信内容、侦察报告原文 | 通信官 |
| 情报 | 侦察报告、已知敌情、情报分析 | 情报官 |

### 8.3 状态机

NPC 系统本身无状态机——NPC 是被动角色，由事件触发发言。

### 8.4 规则

| 编号 | 规则 | 条件 | 行为 | 边界/异常 | 测试关联 |
|------|------|------|------|----------|---------|
| NPC-001 | 信息过滤 | NPC 查询 | 系统根据信息权限过滤 GameState | NPC 不应看到超出权限的信息 | test_npc::test_info_filter |
| NPC-002 | Browning 主动建议 | 侦察报告到达 | Browning 分析报告并建议行动 | — | test_npc::test_browning_advice |
| NPC-003 | Murray/Mitscher 被动报告 | 本舰事件 | 舰长报告本舰状态变化 | 不主动建议战术 | test_npc::test_captain_report |
| NPC-004 | 通信官转发 | 电报到达 | 通信官转发原始电报 | 不做判断 | test_npc::test_comms_forward |
| NPC-005 | 情报官分析 | 侦察报告到达 | 情报官分析报告可信度 | — | test_npc::test_intel_analysis |
| NPC-006 | LLM 数据准备 | NPC 发言时 | 系统过滤 GameState + 角色设定 → 传给 LLM | — | test_npc::test_llm_data |
| NPC-007 | NPC 不访问 actual_enemy | 全局 | NPC 通过信息过滤只能看到 known_enemy | — | test_npc::test_no_actual_enemy |

### 8.5 算法与公式

#### 8.5.1 信息过滤

**用途**：根据 NPC 信息权限过滤 GameState
**输入**：state(GameState), npc_name(str)
**输出**：filtered_state(dict)

```
权限表:
  Browning → 全局态势（除 actual_enemy）
  Murray → 只看 Enterprise 相关
  Mitscher → 只看 Hornet 相关
  通信官 → 只看 incoming_messages
  情报官 → 只看 known_enemy + pending_reports

过滤逻辑:
  1. 从 state 中提取该 NPC 权限范围内的字段
  2. actual_enemy 永远不传给任何 NPC
  3. 返回过滤后的 dict
```

#### 8.5.2 LLM 数据包

NPC 发言时，系统传给 LLM 的数据包结构：

```python
llm_data = {
    "role": "Browning",           # NPC 角色名
    "personality": {              # 人格参数
        "autonomy": 8,
        "risk_tolerance": 8,
        "initiative": 9,
        "competence": 9,
    },
    "info_scope": "global",       # 信息权限等级
    "filtered_state": {...},      # 过滤后的游戏状态
    "context": "侦察报告到达",     # 当前触发事件
    "recent_events": [...],       # 最近发生的事件
}
```

### 8.6 接口

| 函数 | 调用方 | 签名 | 副作用 |
|------|--------|------|--------|
| `filter_state_for_npc` | LLM 系统 | `(state, npc_name) → dict` | 无（纯函数） |
| `get_npc_params` | 骰子系统 | `(npc_name) → dict` | 无（纯函数） |
| `trigger_npc_speech` | 事件系统 | `(state, npc_name, context) → str` | 调用 LLM 生成发言 |
| `get_npc_list` | 前端 | `() → list[dict]` | 无（只读） |

### 8.7 边界条件与异常

| 编号 | 场景 | 预期行为 |
|------|------|---------|
| NPC-EDGE-001 | NPC 尝试访问 actual_enemy | 信息过滤函数拒绝，返回空 |
| NPC-EDGE-002 | LLM 返回异常内容 | 系统兜底：返回默认报告文本 |
| NPC-EDGE-003 | NPC 不在线（如 Murray 阵亡） | 跳过该 NPC，不触发发言 |

### 8.8 测试用例

| 规则编号 | 测试函数 | 测试类型 | 优先级 |
|---------|---------|---------|--------|
| NPC-001 | test_info_filter_browning | 单元 | P0 |
| NPC-001 | test_info_filter_murray | 单元 | P0 |
| NPC-001 | test_info_filter_comms | 单元 | P0 |
| NPC-007 | test_no_actual_enemy | 单元 | P0 |
| NPC-002 | test_browning_advice | 集成 | P1 |
| NPC-003 | test_captain_report | 集成 | P1 |
| NPC-006 | test_llm_data_package | 单元 | P0 |
| NPC-EDGE-001 | test_filter_blocks_actual_enemy | 边界 | P0 |

---

## 九、海图参谋系统（地图系统）

### 9.1 概述

海图参谋系统模拟"海图参谋"（Chart Officer）的角色——维护战术海图、标注敌情、绘制航线、提供空间态势感知。所有海图相关功能设计都补充到本章节。

**职责边界**：
- 本系统负责：海图渲染、视觉元素管理、动效设计、玩家海图交互、"圈出确认"机制
- 本系统**不**负责：空间计算（由地理系统处理）、游戏逻辑（由各业务系统处理）

**依赖关系**：
- 输入来自：GameState（舰队位置、敌情）、侦察系统（侦察报告）、航空参谋系统（编组状态）
- 输出给到：前端 Canvas（渲染）、玩家（态势感知）
- 调用时机：每 tick 更新渲染；事件触发时更新标注

**设计原则**：
- **沉浸感**：海图应有二战纸质海图的质感，不是现代数字界面
- **动效驱动**：每个视觉元素都有动态行为，不是静态图标
- **一一对应**：每个视觉元素背后都有明确的数值逻辑来源

### 9.2 数据模型

#### 9.2.1 视觉元素清单

| 视觉元素 | 数据源 | 动效 | 交互 |
|---------|--------|------|------|
| 己方舰队图标 | TaskForce.position/course/speed | 沿航向平滑移动（lerp） | 点击查看详情 |
| 敌军标记（待确认） | PendingReport | 虚线圈脉冲闪烁，手绘感线条 | 点击确认→变实线 |
| 敌军标记（已确认） | EnemyKnown | 实线圈，置信度越高越亮 | 点击查看详情 |
| 侦察航线（规划中） | ScoutMission.route（未确认） | 虚线从起点逐渐"画"到终点 | 点击确认/取消 |
| 侦察航线（执行中） | ScoutMission.route（已确认） | 实线，飞机图标沿线移动 | — |
| 搜索扇面 | ScoutMission 搜索区域 | 从中心向外扩展，边缘淡出 | — |
| 打击航线 | AirGroup.intercept_heading | 虚线箭头从舰队指向目标 | — |
| 飞机编队 | AirGroup（AIRBORNE） | 小三角沿航线移动，尾迹线 | 点击查看详情 |
| 中途岛 | 固定位置 | 静态图标 | — |
| 比例尺 | 固定 | 静态，铜版画风格 | — |
| 罗盘 | 固定 | 静态，八角星 + N/S/E/W | — |
| 距离环 | 舰队位置为圆心 | 静态虚线圆 | — |

#### 9.2.2 视觉风格定义

| 元素 | 风格 |
|------|------|
| 底色 | 泛黄纸质海图纹理 |
| 网格 | 淡蓝色六边形（铅笔画感） |
| 己方标记 | 墨水蓝 |
| 敌方标记 | 红墨水 |
| 辅助线 | 铅笔灰 |
| 字体 | 打字机风格（等宽、略有墨迹不均匀） |
| 待确认标记 | 橙色虚线 + 脉冲动画 |
| 已确认标记 | 绿色实线 |

### 9.3 状态机

海图系统本身无状态机——它是渲染层，状态由 GameState 驱动。

### 9.4 规则

| 编号 | 规则 | 条件 | 行为 | 边界/异常 | 测试关联 |
|------|------|------|------|----------|---------|
| CHART-001 | 己方舰队显示 | 始终 | 在正确位置显示舰队图标 | — | test_chart::test_fleet_display |
| CHART-002 | 敌军待确认标记 | 侦察报告到达 | 在报告位置显示虚线圈（橙色脉冲） | — | test_chart::test_pending_contact |
| CHART-003 | 圈出确认 | 玩家点击待确认标记 | 虚线圈变实线（绿色），更新到 known_enemy | — | test_chart::test_confirm_contact |
| CHART-004 | 侦察航线显示 | 规划中/执行中 | 虚线/实线显示航线 | — | test_chart::test_scout_route |
| CHART-005 | 飞机编队移动 | AirGroup AIRBORNE | 小三角沿航线平滑移动 | — | test_chart::test_aircraft_movement |
| CHART-006 | 搜索扇面扩展 | 侦察机搜索中 | 扇面从中心向外扩展 | — | test_chart::test_search_sector |
| CHART-007 | 打击航线显示 | 打击编组 LAUNCHING/AIRBORNE | 虚线箭头从舰队指向目标 | — | test_chart::test_strike_route |
| CHART-008 | 舰队平滑移动 | 每 tick | 舰队图标用 lerp 平滑过渡 | — | test_chart::test_fleet_smooth |
| CHART-009 | 手绘感线条 | 敌军标记 | 线条用 Perlin noise 扰动 | — | test_chart::test_hand_drawn |
| CHART-010 | 确认动画 | 圈出确认 | 0.5-1秒画圈动画 | — | test_chart::test_confirm_animation |
| CHART-011 | 报告到达动画 | 侦察报告到达 | 0.3秒标记出现动画 | — | test_chart::test_report_animation |
| CHART-012 | 搜索扇面淡出 | 搜索完成 | 扇面变为半透明 | — | test_chart::test_sector_fade |
| CHART-013 | 距离环显示 | 始终 | 以舰队为圆心的虚线圆 | — | test_chart::test_range_rings |
| CHART-014 | 比例尺/罗盘 | 始终 | 铜版画风格静态元素 | — | test_chart::test_compass_scale |
| CHART-015 | 地图边界 | 实体移出 GRID_RADIUS | 不渲染超出范围的实体 | — | test_chart::test_out_of_bounds |

### 9.5 算法与公式

#### 9.5.1 视觉位置计算

**用途**：将游戏坐标转换为 Canvas 像素坐标
**公式**：
```
canvas_x = center_x + hex_q × cell_size_px
canvas_y = center_y - hex_r × cell_size_px × 0.866  # hex 间距
```

#### 9.5.2 平滑移动（lerp）

**用途**：舰队/飞机图标平滑过渡，不是跳格子
**公式**：
```
每帧插值：
current_pos = lerp(current_pos, target_pos, 0.1)
lerp(a, b, t) = a + (b - a) × t
```
**帧率**：60fps，每帧更新

#### 9.5.3 手绘感线条

**用途**：敌军标记的虚线圈有手绘感
**算法**：
```
1. 生成标准圆形路径
2. 对每个路径点，用 Perlin noise 扰动 (x, y)
   x' = x + noise(x, y, seed) × jitter_amount
   y' = y + noise(x, y, seed+1) × jitter_amount
3. jitter_amount = 2-3 像素（轻微抖动）
```

#### 9.5.4 搜索扇面扩展

**用途**：搜索扇面从中心向外逐渐扩展
**算法**：
```
当前覆盖半径 = 搜索进度 × 最大半径
搜索进度 = route_index / route_length
扇面渲染 = clip(圆形区域, 扇形范围)
边缘透明度 = 1.0 - (距离 / 当前覆盖半径) × 0.5
```

#### 9.5.5 画圈确认动画

**用途**：玩家确认敌军标记时的动画
**算法**：
```
动画时长 = 0.7 秒
动画进度 = elapsed / duration
当前角度 = animation_progress × 360°
绘制弧线：从起始角度到当前角度
完成后：切换为实线圈
```

### 9.6 接口

| 函数 | 调用方 | 签名 | 副作用 |
|------|--------|------|--------|
| `render_frame` | 游戏循环 | `(state, ctx) → None` | 渲染一帧海图 |
| `update_animations` | 游戏循环 | `(delta_time) → None` | 更新所有动画状态 |
| `confirm_contact` | 玩家点击 | `(report_id) → None` | 虚线圈→实线，更新 known_enemy |
| `add_pending_marker` | 侦察系统 | `(report) → None` | 添加待确认标记 |
| `update_fleet_position` | 每 tick | `(state) → None` | 更新舰队图标位置 |
| `update_aircraft_positions` | 每 tick | `(state) → None` | 更新飞机图标位置 |
| `draw_search_sector` | 侦察系统 | `(mission) → None` | 绘制搜索扇面 |
| `get_canvas_coords` | 内部 | `(lat, lon) → (x, y)` | 坐标转换 |

### 9.7 边界条件与异常

| 编号 | 场景 | 预期行为 |
|------|------|---------|
| CHART-EDGE-001 | 实体移出 GRID_RADIUS | 不渲染，或在边缘显示箭头指示方向 |
| CHART-EDGE-002 | 窗口大小变化 | 重新计算 cell_size_px，保持比例 |
| CHART-EDGE-003 | 多个待确认标记重叠 | 按时间排序，最新在最上层 |
| CHART-EDGE-004 | 动画未完成时新数据到达 | 中断当前动画，立即更新到新状态 |
| CHART-EDGE-005 | 飞机编队消失（LOST） | 图标播放坠毁动画后消失 |

### 9.8 测试用例

#### 测试覆盖矩阵

| 规则编号 | 测试函数 | 测试类型 | 优先级 |
|---------|---------|---------|--------|
| CHART-001 | test_fleet_display_position | 单元 | P0 |
| CHART-001 | test_fleet_display_heading | 单元 | P0 |
| CHART-002 | test_pending_contact_appear | 单元 | P0 |
| CHART-002 | test_pending_contact_pulse | 动效 | P1 |
| CHART-003 | test_confirm_contact_animation | 动效 | P0 |
| CHART-003 | test_confirm_contact_data_update | 单元 | P0 |
| CHART-004 | test_scout_route_planning | 单元 | P0 |
| CHART-004 | test_scout_route_executing | 单元 | P0 |
| CHART-005 | test_aircraft_movement_smooth | 动效 | P0 |
| CHART-005 | test_aircraft_movement_complete | 集成 | P0 |
| CHART-006 | test_search_sector_expand | 动效 | P0 |
| CHART-006 | test_search_sector_fade | 动效 | P1 |
| CHART-007 | test_strike_route_display | 单元 | P0 |
| CHART-008 | test_fleet_smooth_lerp | 动效 | P0 |
| CHART-009 | test_hand_drawn_jitter | 动效 | P1 |
| CHART-010 | test_confirm_animation_duration | 动效 | P1 |
| CHART-011 | test_report_animation_duration | 动效 | P1 |
| CHART-013 | test_range_rings_display | 单元 | P1 |
| CHART-015 | test_out_of_bounds_clip | 边界 | P0 |
| CHART-EDGE-004 | test_animation_interrupt | 边界 | P1 |
| CHART-EDGE-005 | test_aircraft_crash_animation | 动效 | P1 |

#### 关键测试用例详述

**TC-CHART-001: 己方舰队显示**
- TF16 在 lat=31.5, lon=-176.0，航向 240°
- 预期：Canvas 上正确位置显示舰队图标，箭头指向 240°

**TC-CHART-002: 待确认标记出现**
- 侦察报告到达，敌军位置 lat=31.0, lon=-180.0
- 预期：对应 hex 位置出现橙色虚线圈，脉冲闪烁

**TC-CHART-003: 圈出确认**
- 玩家点击待确认标记
- 预期：0.7秒画圈动画 → 虚线变实线 → known_enemy 更新

**TC-CHART-005: 飞机编队移动**
- 编队从 (8,20) 飞往 (5,15)
- 预期：小三角图标每帧 lerp 移动，60fps 平滑过渡

**TC-CHART-006: 搜索扇面扩展**
- 侦察机搜索进度 50%
- 预期：扇面覆盖半径 = 最大半径 × 50%，边缘淡出

**TC-CHART-008: 舰队平滑移动**
- 舰队从 hex(8,20) 移动到 hex(8,21)
- 预期：图标不是跳格子，而是 1 秒内平滑过渡

**TC-CHART-015: 地图边界**
- 实体移出 GRID_RADIUS(40格)
- 预期：不渲染该实体

---

## 十、事件系统

### 10.1 已实现事件
| 时间 | 事件 | 效果 |
|------|------|------|
| 06:00 | 中途岛遭袭 | 通知玩家 |

### 10.2 待实现事件（设计文档）
- 侦察报告到达（已实现）
- 攻击成功 → 日军反击
- 飞机返航着舰
- 天气变化
- 多结局触发

---

## 十一、胜利条件（待实现）

| 结局 | 条件 | 叙事 |
|------|------|------|
| 超越历史 | 沉 ≥ 4 日舰，美损 ≤ 1 | "你做到了 Spruance 都不敢想的事" |
| 中途岛奇迹 | 沉 3-4 日舰，美损 ≈ 历史 | "历史按你想的方式发生了" |
| 惨胜 | 沉 ≥ 2 日舰，美损 ≥ 2 | "赢了，但代价惨重" |
| 惨败 | 沉 ≤ 2 日舰 | "如果这一天没赢，太平洋战争会怎样？" |
| Browning 独走 | Browning 自主决策导致胜利 | "这场胜利属于 Browning，还是属于你？" |

---

## 十二、已知问题

| 编号 | 问题 | 严重性 |
|------|------|--------|
| BUG-1 | `recon_plan.py` 用 `datetime.now()` 而非游戏时间 | 中 |
| BUG-2 | `mapRenderer.js` `_drawPendingRecon` 中 `midAngle` 未定义 | 高 |
| BUG-3 | NPC 标签前后端不匹配 | 低 |
| BUG-5 | `launch_scout` 不在工具 schema 中 | 低 |
| BUG-6 | 单线程状态无并发保护 | 低（原型阶段） |

---

## 十三、开发路线图

### Phase 1：核心循环 ✅
- [x] AP 系统
- [x] 侦察循环（含骰子检定）
- [x] 信息延迟 + 失真

### Phase 2：丰富体验
- [x] 多 NPC
- [ ] 双刃骰（优势骰代价）
- [ ] 连锁事件

### Phase 3：完整游戏
- [ ] 战斗演算（攻击/命中/损伤）
- [ ] 多结局
- [ ] 历史脚注

### Bug 修复
- [ ] 修复 BUG-1（recon_plan 时间）
- [ ] 修复 BUG-2（mapRenderer midAngle）
- [ ] 修复 BUG-3（NPC 标签）

### UI 完善
- [ ] 待确认任务海图显示（已实现基础版）
- [ ] SVG 图标集成（已实现基础版）
- [ ] 多侦察任务同时显示
- [ ] 通信面板优化
