# Phase 2B: §5 航空参谋系统 — 实施报告

## 实施内容

### 新建文件
- `src/aircraft.py` — 飞机管理（create_air_group, launch, update_fuel, process_landing, recall）
- `src/mission.py` — 出击规划（calculate_intercept, calculate_fuel_budget, plan_mission）
- `tests/test_aircraft.py` — AIR-001~016 测试（14 个）
- `tests/test_mission.py` — AIR-017~022 测试（9 个）

### 修改文件
- `src/state.py` — Aircraft 添加 hp, group_id, losses 字段；AircraftStatus 添加 LOST

### 核心实现
1. **aircraft.py**:
   - create_air_group() — 创建编组
   - launch_air_group() — LAUNCHING→AIRBORNE
   - update_fuel() — 每tick消耗燃油
   - process_landing() — 着舰检定（五级结果）
   - recall_air_group() — 召回
   - damage_aircraft() — HP伤害
   - get_aircraft_status() / get_air_group_status()

2. **mission.py**:
   - calculate_intercept() — 拦截点计算（运动学方程）
   - calculate_fuel_budget() — 油量预算
   - plan_mission() — 创建出击规划
   - confirm_mission() / reject_mission()

### 测试覆盖
- 23 个测试全部通过
- 覆盖 AIR-001~022 规则

### 已知问题
- 无

### 下一步
Phase 3A: §6 侦察系统（scouting.py 重写）
