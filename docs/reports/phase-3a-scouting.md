# Phase 3A: §6 侦察系统 — 实施报告

## 实施内容

### 修改文件
- `src/scouting.py` — 添加航线生成函数、空间相遇检测
- `tests/test_scouting.py` — 添加航线生成和相遇检测测试

### 新增功能
1. **航线生成函数**:
   - generate_sector_route() — 扇形搜索航线
   - generate_expanding_square_route() — 扩展方形航线
   - generate_parallel_route() — 平行搜索航线

2. **空间相遇检测**:
   - check_detection() — 侦察机 hex vs 敌舰 hex

### 测试覆盖
- 23 个侦察测试全部通过
- 新增：TestSectorRoute, TestExpandingSquareRoute, TestParallelRoute, TestRouteLength, TestSpatialEncounter

### 规格对应
| 规则 | 状态 |
|------|------|
| SC-001 | ✅ test_sector_route_basic, test_sector_route_wrap_360 |
| SC-002 | ✅ test_expanding_square_route |
| SC-003 | ✅ test_parallel_track_route |
| SC-004 | ✅ test_route_length |
| SC-005 | ✅ test_detect_same_hex, test_detect_adjacent_hex, test_detect_no_enemy |

### 已知问题
- 无

### 下一步
Phase 3B: §8 NPC系统（npc.py 新建）
