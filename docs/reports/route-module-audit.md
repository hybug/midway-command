# 航线模块覆盖度缺口审计（批次 C0）

> 计划：`docs/plans/ui-fidelity-fix-plan.md` 批次 C。审计对象为 Python 运动学核心 11 个函数；
> 覆盖点通过 grep `tests/test_entities.py` / `tests/test_mission.py` / `tests/test_scouting.py` 逐一核对，
> 几何结论均经 `.venv/bin/python` 数值验证（2026-09-11，基线 261 passed）。

## 一、逐函数审计表

| 函数 | 现有测试 | 缺口 | 计划用例（C1/C2） |
|---|---|---|---|
| `entities.calculate_new_position` | `test_move_north/south/east/west`（60nm 方向性）、`test_zero_distance`、`test_15_minutes_at_25_knots`（斜航向） | ①经度 ±180° 包裹零覆盖（现有用例均在 lon=-175 附近，不跨日界线）；②纯象限（0°/90°）在日界线附近位置未验证 | C1 `test_due_north_increases_lat`、`test_due_east_increases_lon_wrapped`、`test_zero_speed_stays` |
| `entities.update_entity_position` | `test_carrier_moves`、`test_task_force_moves` | `distance_nm<=0` 不动分支（L141 `if distance_nm > 0`）未测；TF 级 `course/speed` 不参与运动（递归用 carrier 自身值）仅为实现事实，无断言 | 本轮不加（低危：上层 `test_zero_speed_stays` 覆盖运动学层；分支逻辑简单） |
| `entities.update_all_positions` | `test_both_fleets_move_after_tick`（仅 TF16.carriers[0] + 敌 carriers[0]）、`test_fleets_diverge_over_time` | ⑤多舰队同 tick 一致性：TF16 两艘、敌舰队 4 艘未逐一验证；`actual_enemy[i]["position"] ← enemy_fleet.carriers[i]` 同步（L171-177）零覆盖 | C1 `test_update_all_positions_moves_both_fleets`（全部 TF + 敌方 + actual_enemy 同步断言） |
| `mission.calculate_intercept` | `test_intercept_basic`（快机有解，断言 distance/flight_time/heading 区间）、`test_intercept_no_solution`（**零断言**，仅"不抛异常"） | ②不可拦截分支（敌速≥机速 → None）完全未断言；`t<=0` 负时间拒判未测 | C2 `test_intercept_solvable_when_aircraft_faster`、`test_intercept_unsolvable_when_too_slow` |
| `scouting.calculate_bearing` | `test_bearing_north`（≈180°）、`test_bearing_southwest`（≈233°） | ④四象限正交方位（0°/90°/270°）未测，现有仅斜方位近似区间 | C2 `test_bearing_four_quadrants` |
| `scouting.calculate_distance_nm` | `test_distance_short`、`test_distance_midway` | 与 bearing 的往返一致性（bearing+distance→位置→反算回原值）未测 | C2 `test_bearing_distance_roundtrip` |
| `scouting.in_sector` | 5 断言：普通包含、外部、360° 环绕（350-10） | 覆盖充分 | 无新增 |
| `scouting.generate_sector_route` | `test_sector_route_basic`（len≥5）、`test_sector_route_wrap_360`（len>0） | ③扇区约束（航点方位落在扇面内）未测；出航+弧线点数与半径的关系未测 | C2 `test_sector_route_stays_within_sector` |
| `scouting.generate_expanding_square_route` | `test_expanding_square_route`（len≥10） | ③环带约束/回闭合性、起点为舰队位置未测 | C2 `test_expanding_square_route_closes_and_counts` |
| `scouting.generate_parallel_route` | `test_parallel_track_route`（len>0） | ③平行线束性质（行数=width//spacing、行距、往复）未测 | 本轮不加（低危：仅渲染用途；缺口记台账，后续如触碰再补） |
| `scouting._bearing_distance_to_position` | 无直接测试（经 generate_* 间接） | bearing+distance→Position 正确性未直接断言 | C2 `test_bearing_distance_roundtrip`（间接覆盖） |

## 二、五类高危缺口逐项结论

### ① `calculate_new_position` 航向象限与经度 ±180° 包裹

- 象限约定：`0°=北、90°=东、180°=南、270°=西`（docstring L90），公式为标准大圆航法（L105-113）。
- 包裹：L115-120 已实现 `[-180, 180]` while 循环包裹（历史提交 `fix: 经度包裹到 [-180, 180] 范围`）。
- 数值验证：自 `(28.0, 179.5)` 东向 600nm → `(27.539, -169.214)`，包裹正确且落在**西经（负值）**。
- **结论**：实现正确，缺的只是包裹路径的回归测试。注意：任务书 C1 草案断言 `pos.lon > 0`（"落在东经"）数学上不成立——东向跨越日界线后必落西经（负值），用例按同意图校正为 `pos.lon < 0`（详见 C1 报告）。

### ② `calculate_intercept` 不可拦截分支与拦截时间非负

- 实现三处 None 返回：`a==0 且 b==0`（L81-82）、判别式<0（L88-89）、两根均 ≤0（L84-85, L91-94）。
- 数值验证：敌 `(30,-178)` 航向 0°（向北远离南侧_launcher）速 200 节 vs 机速 100 节 → 两根均为负 → `None` ✓；机速 180 vs 敌速 20 航向 90° → 有解，`flight_time_min=36.6` ≥ 0 ✓。
- **结论**：实现正确；但现有 `test_intercept_no_solution` 零断言，None 分支实际处于无守卫状态——C2 用例将该分支首次纳入断言。

### ③ 三种 `generate_*_route` 航点序列性质

- 返回值均为**六边形坐标 `(q, r)` 列表**（经 `world_to_hex`，CELL_SIZE_NM=10nm），非 lat/lon——测试断言须先 `hex_to_world` 还原。
- 扇形：出航段（每 10nm 一步至半径）+ 弧线段（半径处按扇宽每 10° 一步）。数值验证 `center_bearing=60, sector_width=60, radius_nm=120` 共 19 点，扇面 [30°,90°] 内**唯一越界点是起点格 (0,0)**——10nm 出航第一步取整回舰队自身格，该点方位退化（距离 0），属六边形量化的固有伪影而非方位越界；用例对距离 <1nm 的起点格豁免并记录。
- 扩展方形：步长 1,1,2,2,3,3… 螺旋。数值验证 `max_radius_nm=90`（对应任务书 legs=3×leg_nm=30）得 91 点，起终点距离 70.6nm ≤ 90nm，闭合性成立。
- 平行：本轮不排用例（见表）。
- **结论**：三函数序列性质均可按意图断言，无需改 src。

### ④ `calculate_bearing` 四象限

- 公式为标准 initial-bearing 公式（L50-57），`(bearing+360)%360` 归一到 [0,360)。
- 数值验证赤道正交四点：北 0°/东 90°/南 180°/西 270° 全部精确。
- **结论**：实现正确，缺 0°/90°/270° 正交用例，C2 补齐。

### ⑤ `update_all_positions` 多舰队同 tick 一致性

- 实现：US 各 TF 递归到 carrier 按 **carrier 自身** course/speed 移动（TF 级 course/speed 仅存档不参与运动——state.Carrier 默认 course=240/speed=25，敌 entities.Carrier 显式 110°/20 节）；敌舰队移动后同步 `actual_enemy[i]["position"]`（仅同步到 `len(actual_enemy)` 截断，当前初始态为 1 条）。
- **结论**：实现行为自洽；现有测试只抽查两艘首舰，actual_enemy 同步零覆盖。C1 用例扩展为：全部 TF 首舰 + 敌全部 4 艘 + actual_enemy[0] 与 Akagi 移动后位置精确一致。

## 三、任务书签名差异校正备忘（C1/C2 落笔依据）

| 任务书原样 | 源码实际 | 处理 |
|---|---|---|
| `calculate_new_position(..., speed=24, minutes=60)` | 第三参为 `distance_nm`（L81-85） | 按语义换算 `distance_nm = speed * minutes / 60`，断言意图不变 |
| `generate_sector_route(origin=, bearing_min=, bearing_max=, distance_nm=)` | `(fleet_pos, center_bearing, sector_width, radius_nm)`（L81-86） | 改用 `center_bearing=60, sector_width=60, radius_nm=120` 等价覆盖扇面 [30°,90°] |
| `generate_expanding_square_route(origin=, legs=, leg_nm=)` | `(fleet_pos, max_radius_nm)`（L134-137） | `legs=3, leg_nm=30` → `max_radius_nm=90` |
| 拦截结果键 `time_to_intercept` | `flight_time_min`（mission.py L109/L115） | 键名以源码为准 |
| 航点直接取 `.lat/.lon` | 返回六边形 `(q, r)` | 经 `hex_to_world(q, r)` 还原 lat/lon 再断言 |
| 扩方闭合断言（数值前提） | 90nm 半径下实测闭合距离 70.6nm | 断言 `≤ 30*3` 可直接成立 |
