# Phase 1A: §4 状态系统 — 实施报告

## 实施内容

### 修改文件
- `src/state.py` — 添加 GamePhase, MissionPlan, 更新 AirGroup/AirGroupStatus, Position.to_tuple()

### 新增内容
1. **GamePhase 枚举**: PLAYING, GAME_OVER
2. **GameState.game_phase**: 默认 PLAYING
3. **AirGroupStatus 扩展**: 添加 PLANNING, ATTACKING, REFUELING, REARMING, LOST
4. **AirGroup 扩展**: 添加 id, carrier_name, plan_id, mission_type, launched_at, intercept_heading
5. **MissionPlan 数据模型**: 12 个字段（拦截点、油量、警告等）
6. **Position.to_tuple()**: 返回 (lat, lon)
7. **actual_enemy 公开属性**: 从 _hidden_actual_enemy 改为公开字段
8. **SearchPattern 更新**: GRID → EXPANDING_SQUARE
9. **ScoutPhase 精简**: 移除 DIVERTED, DITCHED

### 测试覆盖
- 新增 15 个测试，总计 139 个测试全部通过
- 覆盖 STATE-001~009 规则

### 规格对应
| 规则 | 状态 |
|------|------|
| STATE-001 | ✅ test_gamestate_creation |
| STATE-002 | ✅ test_position_unified |
| STATE-003 | ✅ test_position_to_tuple |
| STATE-004 | ✅ test_actual_enemy_accessible |
| STATE-007 | ✅ test_serialization_roundtrip, test_actual_enemy_in_model_dump |
| STATE-008 | ✅ test_field_constraints |
| STATE-009 | ✅ test_defaults |

### 已知问题
- 无

### 下一步
Phase 1B: §3 地理系统（coordinate.py + spatial.py 测试验证）
