# Phase 1C: §7 骰子系统 — 实施报告

## 实施内容

### 修改文件
- `src/dice.py` — 更新为三层分离架构
- `src/npc_config.py` — 参数统一为 0-10 整数
- `tests/test_dice.py` — 更新测试
- `tests/test_npc.py` — 更新参数范围检查

### 核心变化
1. **三层分离架构**：
   - 原始骰 = d100（随机性层）
   - NPC层 = competence × 2（封顶 +20）
   - 情境层 = Σ 情境修正（封顶 ±20）
   - 总修正 = NPC层 + 情境层（封顶 ±30）

2. **大成功/大失败看原始骰**：
   - 原始骰 ≥ 95 → 大成功（即使修正后未达 95）
   - 原始骰 ≤ 9 → 大失败（即使修正后 > 9）

3. **NPC 参数统一**：
   - risk_tolerance: 0-1 → 0-10
   - initiative: 0-1 → 0-10
   - competence: 0-1 → 0-10

### 测试覆盖
- 30 个骰子测试全部通过
- 新增：test_npc_layer_capped_at_20, test_situational_layer_capped_at_20, test_total_modifier_capped_at_30, test_critical_success_on_raw_dice, test_critical_failure_on_raw_dice
- 新增着舰检定测试：test_landing_basic, test_landing_night_penalty, test_landing_fuel_penalty

### 规格对应
| 规则 | 状态 |
|------|------|
| 三层分离 | ✅ |
| 封顶规则 | ✅ |
| 大成功/大失败看原始骰 | ✅ |
| NPC 参数 0-10 | ✅ |
| 着舰检定 | ✅ |

### 已知问题
- 无

### 下一步
Phase 2A: §2 时间/AP系统（pipeline.py 新建）
