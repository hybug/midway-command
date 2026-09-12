# 实施计划：§2-§9 全系统实现

> **[历史存档 2026-09-12]** 本文档已执行完毕，仅作历史参考（规格以 docs/design/GAME_SPEC.md 为准，仓库实况优先）。

## 概览

基于 GAME_SPEC.md 规格文档，实现从 §2 时间/AP系统 到 §9 海图参谋系统 的全部功能。

**当前状态**：124 个测试全部通过。已有基础实现（ap.py, dice.py, spatial.py, entities.py, events.py, scouting.py, state.py）。

**目标**：将现有实现与规格文档对齐，补充缺失功能，确保所有规则都有测试覆盖。

---

## 实施顺序（按依赖关系）

### Phase 1: 基础层（§4 状态系统 + §3 地理系统 + §7 骰子系统）
这些是其他系统的基础设施，必须先完成。

### Phase 2: 核心逻辑（§2 时间/AP系统 + §5 航空参谋系统）
游戏核心循环和飞机管理。

### Phase 3: 业务系统（§6 侦察系统 + §8 NPC系统）
侦察和NPC交互。

### Phase 4: 展示层（§9 海图参谋系统）
前端渲染，最后实现。

---

## 详细计划

### Phase 1A: §4 状态系统 (state.py)

**需要修改的文件**：
- `src/state.py` — 添加 GamePhase enum, MissionPlan model, 更新 AirGroup/AirGroupStatus
- `tests/test_state.py` — 添加 STATE-001~009 测试

**具体任务**：
1. 添加 `GamePhase` 枚举 (PLAYING, GAME_OVER)
2. 在 GameState 中添加 `game_phase` 字段
3. 更新 `AirGroupStatus` 枚举（添加 PLANNING, ATTACKING, REFUELING, REARMING, LOST）
4. 更新 `AirGroup` 数据模型（添加 plan_id, intercept_heading 等字段）
5. 添加 `MissionPlan` 数据模型
6. 将 `_hidden_actual_enemy` 改为公开属性 `actual_enemy`
7. 统一 Position 类（删除 entities.py 的 Position，使用 state.py 的）
8. 添加 Position.to_tuple() 方法
9. 编写测试：test_gamestate_creation, test_position_unified, test_position_to_tuple, test_actual_enemy_accessible, test_serialization_roundtrip, test_field_constraints, test_defaults, test_initial_state_valid

**验证命令**：`python -m pytest tests/test_state.py -v`

---

### Phase 1B: §3 地理系统 (render/coordinate.py + spatial.py)

**需要修改的文件**：
- `src/render/coordinate.py` — 验证/补充 world_to_hex, hex_to_world, hex_distance, hex_bearing, hex_sector, bearing_in_sector
- `src/spatial.py` — 验证/补充 SpatialIndex 所有方法
- `tests/test_coordinate.py` — 新建，GEO-001~011 测试
- `tests/test_spatial.py` — 新建，GEO-012~018 测试

**具体任务**：
1. 验证 coordinate.py 中所有函数正确实现
2. 验证 spatial.py 中 SpatialIndex 所有方法正确实现
3. 编写 24 个测试用例（见规格 §3.8）

**验证命令**：`python -m pytest tests/test_coordinate.py tests/test_spatial.py -v`

---

### Phase 1C: §7 骰子系统 (dice.py)

**需要修改的文件**：
- `src/dice.py` — 更新为三层分离架构（NPC层封顶+20, 情境层封顶±20, 总修正封顶±30）；大成功/大失败看原始骰
- `tests/test_dice.py` — 更新测试以匹配新架构

**具体任务**：
1. 更新 roll_check() 实现三层分离
2. 更新 roll_with_npc() 使用 competence×2（封顶+20）
3. 更新 roll_scout_check(), roll_attack_check(), roll_landing_check() 使用新架构
4. 添加大成功/大失败附加判定（原始骰≥95或≤9）
5. 更新所有测试

**验证命令**：`python -m pytest tests/test_dice.py -v`

---

### Phase 2A: §2 时间/AP系统 (ap.py + pipeline)

**需要修改的文件**：
- `src/ap.py` — 验证现有实现
- `src/pipeline.py` — 新建，实现 TickStep + Pipeline
- `src/events.py` — 重构为使用 Pipeline
- `tests/test_ap.py` — 验证/补充测试
- `tests/test_pipeline.py` — 新建，TIME-008~009 测试

**具体任务**：
1. 验证 ap.py 实现（TIME-001~007 已覆盖）
2. 新建 pipeline.py，实现 TickStep dataclass 和 Pipeline class
3. 重构 events.py 的 EventScheduler.tick() 为 Pipeline.execute()
4. 添加 check_game_over 步骤（TIME-010~012）
5. 编写管线测试：test_pipeline_order, test_pipeline_step_exception_continues, test_pipeline_register_override
6. 编写游戏结束测试：test_game_over_at_0800, test_game_over_all_sunk, test_no_tick_after_game_over

**验证命令**：`python -m pytest tests/test_ap.py tests/test_pipeline.py -v`

---

### Phase 2B: §5 航空参谋系统 (aircraft.py + mission.py)

**需要修改的文件**：
- `src/aircraft.py` — 新建，实现飞机管理（create_air_group, launch, update_fuel, process_landing）
- `src/mission.py` — 新建，实现出击规划（plan_mission, confirm_mission, reject_mission, intercept calculation, fuel budget）
- `src/entities.py` — 精简为移动引擎（删除重复的 Position/Carrier/TaskForce）
- `src/state.py` — 更新 Aircraft/AirGroup 模型
- `tests/test_aircraft.py` — 新建，AIR-001~016 测试
- `tests/test_mission.py` — 新建，AIR-017~024 测试

**具体任务**：
1. 新建 aircraft.py：
   - create_air_group() — 创建编组
   - launch_air_group() — LAUNCHING→AIRBORNE
   - update_fuel() — 每tick消耗燃油
   - process_landing() — 着舰检定（五级结果）
   - recall_air_group() — 召回
   - get_aircraft_status() / get_air_group_status()
2. 新建 mission.py：
   - plan_mission() — 计算拦截点、油量
   - confirm_mission() / reject_mission()
   - calculate_intercept() — 拦截点计算
   - calculate_fuel_budget() — 油量预算
   - generate_npc_briefing_data() — NPC数据包
3. 精简 entities.py（删除 Position, Carrier, TaskForce 重复定义）
4. 编写 42 个测试用例（见规格 §5.8）

**验证命令**：`python -m pytest tests/test_aircraft.py tests/test_mission.py -v`

---

### Phase 3A: §6 侦察系统 (scouting.py)

**需要修改的文件**：
- `src/scouting.py` — 大幅重写，添加航线生成、空间相遇、骰子检定
- `tests/test_scouting.py` — 重写，SC-001~015 测试

**具体任务**：
1. 实现搜索模式航线生成：
   - generate_sector_route() — 扇形搜索
   - generate_expanding_square_route() — 扩展方形
   - generate_parallel_route() — 平行搜索
2. 实现空间相遇检测：
   - check_detection() — 侦察机hex vs 敌舰hex
3. 实现侦察检定（骰子系统三层）：
   - roll_scout_check() — 五级结果
   - roll_reverse_check() — 反向检定
4. 实现侦察报告：
   - generate_report() — 生成报告
   - calculate_report_delay() — 报告延迟
5. 实现侦察生命周期：
   - plan_scout_mission() — Browning规划
   - confirm_scout() / reject_scout()
   - process_scouting() — 每tick处理
6. 编写 30 个测试用例（见规格 §6.8）

**验证命令**：`python -m pytest tests/test_scouting.py -v`

---

### Phase 3B: §8 NPC系统 (npc.py)

**需要修改的文件**：
- `src/npc.py` — 新建，实现信息过滤、LLM数据准备
- `src/npc_config.py` — 更新参数（统一为0-10整数）
- `tests/test_npc.py` — 更新，NPC-001~007 测试

**具体任务**：
1. 新建 npc.py：
   - filter_state_for_npc() — 信息过滤
   - get_npc_params() — 获取NPC参数
   - prepare_llm_data() — 准备LLM数据包
2. 更新 npc_config.py：
   - 所有参数统一为0-10整数
   - 添加信息权限定义
3. 编写 8 个测试用例（见规格 §8.8）

**验证命令**：`python -m pytest tests/test_npc.py -v`

---

### Phase 4: §9 海图参谋系统 (前端)

**需要修改的文件**：
- `src/render/chart.py` — 新建，海图渲染逻辑
- `static/js/chart.js` — 新建，Canvas渲染
- `tests/test_chart.py` — 新建，CHART-001~015 测试

**具体任务**：
1. 新建 chart.py（后端数据准备）：
   - get_chart_data() — 准备渲染数据
   - confirm_contact() — 圈出确认
2. 新建 chart.js（前端Canvas渲染）：
   - renderFleet() — 渲染己方舰队
   - renderEnemyContact() — 渲染敌军标记
   - renderScoutRoute() — 渲染侦察航线
   - renderSearchSector() — 渲染搜索扇面
   - 动效系统（lerp, 脉冲, 画圈动画）
3. 编写 21 个测试用例（见规格 §9.8）

**验证命令**：`python -m pytest tests/test_chart.py -v`

---

## 文件清单汇总

### 新建文件
| 文件 | 说明 | 依赖 |
|------|------|------|
| `src/pipeline.py` | TickStep + Pipeline | state.py |
| `src/aircraft.py` | 飞机管理 | state.py, dice.py |
| `src/mission.py` | 出击规划 | state.py, aircraft.py, coordinate.py |
| `src/npc.py` | NPC信息过滤 | state.py |
| `src/render/chart.py` | 海图数据准备 | state.py, coordinate.py |
| `tests/test_coordinate.py` | 地理测试 | coordinate.py |
| `tests/test_spatial.py` | 空间索引测试 | spatial.py |
| `tests/test_pipeline.py` | 管线测试 | pipeline.py |
| `tests/test_aircraft.py` | 飞机测试 | aircraft.py |
| `tests/test_mission.py` | 出击规划测试 | mission.py |
| `tests/test_chart.py` | 海图测试 | chart.py |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/state.py` | GamePhase, MissionPlan, AirGroup更新, Position统一 |
| `src/dice.py` | 三层分离架构, 大成功/大失败判定 |
| `src/entities.py` | 精简为移动引擎 |
| `src/events.py` | 重构为Pipeline |
| `src/scouting.py` | 大幅重写（航线生成、空间相遇、检定） |
| `src/npc_config.py` | 参数统一为0-10整数 |
| `tests/test_state.py` | 补充STATE测试 |
| `tests/test_dice.py` | 更新骰子测试 |
| `tests/test_scouting.py` | 重写侦察测试 |
| `tests/test_npc.py` | 更新NPC测试 |

---

## 验证步骤

每个 Phase 完成后：
1. 运行对应测试：`python -m pytest tests/test_xxx.py -v`
2. 运行全量测试：`python -m pytest tests/ -v`
3. 确保无回归

全部完成后：
1. `python -m pytest tests/ -v --tb=short`
2. 生成最终报告

---

## 已知规格模糊点（自行决策）

1. **entities.py 的 Position 删除**：统一使用 state.py 的 Position，entities.py 的 Position 删除
2. **AirGroup 与 ScoutMission 的关系**：侦察任务是 AirGroup 的一种（mission_type="scout"）
3. **Pipeline 的 check_game_over 步骤**：在 order=70 检查 game_time ≥ 08:00 或所有航母被击沉
4. **海图系统**：前端 Canvas 渲染，后端只提供数据接口
5. **NPC 参数统一**：risk_tolerance 从 0-1 浮点映射到 0-10 整数（×10）
