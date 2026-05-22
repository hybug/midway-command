# Day 5 · 舰队实体系统

**目标**：建立完整的 Entity 体系，让所有单位可移动、可追踪。

**预估工作量**：5-6 小时

---

## 设计要点

**Entity 体系**：
- Entity（基类）→ NavalEntity → Carrier
- Entity → AirEntity（飞行单位）
- TaskForce（特混舰队，敌我通用）

**位置更新**：
- 每次 tick（15 分钟），所有实体按航向航速更新位置
- 飞行单位按飞行方向和速度移动
- 燃油消耗逻辑

**敌方实体**：
- 日军机动部队用同样的 TaskForce + Carrier 表示
- 有航向航速，能移动

---

## 任务清单

- [ ] 1. 新建 `src/entities.py`
  - Entity 基类（id, name, position）
  - NavalEntity（course, speed, faction）
  - Carrier（继承 NavalEntity，扩展 air_groups, cap_strength, damage_level）
  - AirEntity（aircraft_type, count, status, origin, destination, speed, fuel, mission）
  - TaskForce（name, faction, carriers, escorts, course, speed）
  - `update_position()` 方法

- [ ] 2. 更新 `src/state.py`
  - 使用新 Entity 结构
  - 保持向后兼容

- [ ] 3. 更新 `src/initial_state.py`
  - 用新 Entity 结构初始化美军
  - 用新 Entity 结构初始化日军

- [ ] 4. 更新 `src/events.py`
  - tick 时调用 `update_all_positions()`
  - 更新所有实体位置

- [ ] 5. 更新 `src/scouting.py`
  - 使用新 Entity 结构
  - 侦察检测基于实体位置

- [ ] 6. 单元测试
  - `tests/test_entities.py`
  - 位置计算、航向边界、阵营区分

---

## 成功标准

- [ ] 美军舰队按航向航速移动
- [ ] 日军舰队按航向航速移动
- [ ] 飞行队有位置、能飞
- [ ] 现有测试全部通过（61 个）
- [ ] Streamlit 正常启动

---

## 产出

- `src/entities.py`
- 更新 `src/state.py`
- 更新 `src/initial_state.py`
- 更新 `src/events.py`
- 更新 `src/scouting.py`
- `tests/test_entities.py`
