# Day 2 · 骰子系统

**目标**：实现 d100 骰子系统，包括五级结果和修正值计算。

**预估工作量**：4-5 小时

---

## 设计要点

**基础机制**：
```
基础骰 = d100
修正值 = Σ(参数 × 权重)
最终值 = 基础骰 + 修正值
```

**五级结果**：
| 等级 | 范围 | 含义 |
|------|------|------|
| 大成功 | 95+ | 超出预期，历史转折 |
| 成功 | 70-94 | 达成目标 |
| 部分成功 | 40-69 | 达成目标但有代价 |
| 失败 | 10-39 | 未达成目标 |
| 大失败 | 9- | 灾难性后果 |

**修正值来源**：
| 来源 | 公式 |
|------|------|
| NPC 自主度 | autonomy × 3 |
| 风险容忍 | risk_tolerance × 20 |
| 主动性 | initiative × 15 |
| 能力值 | competence × 25 |
| 玩家命令质量 | -20 ~ +20 |
| 战场条件 | -30 ~ +10 |

---

## 任务清单

- [ ] 1. 创建 `src/dice.py`
  - `roll_d100()` — 掷一个 d100
  - `roll_with_modifier(base, modifiers)` — 基础骰 + 修正值
  - `get_result_level(final_value)` — 返回五级结果
  - `roll_advantage(modifiers)` — 优势骰（2d100 取高）
  - `roll_disadvantage(modifiers)` — 劣势骰（2d100 取低）

- [ ] 2. 在 `src/state.py` 新增 NPC 参数
  - `NPCProfile` 类：autonomy, risk_tolerance, initiative, competence
  - 在 `GameState` 中存储 NPC 参数

- [ ] 3. 实现修正值计算
  - `calculate_modifier(npc_profile, player_command_quality, battlefield_conditions)`
  - 返回总修正值

- [ ] 4. 在 `app.py` 显示骰子结果
  - 骰子动画（可选）
  - 结果分级显示（颜色区分）
  - 修正值分解显示

- [ ] 5. 单元测试
  - 测试骰子范围（1-100）
  - 测试修正值计算
  - 测试五级结果分类
  - 测试优势骰和劣势骰

---

## 成功标准

- [ ] 骰子结果在 1-100 范围内
- [ ] 修正值正确计算
- [ ] 五级结果正确分类
- [ ] 优势骰和劣势骰正常工作

---

## 产出

- `src/dice.py`（骰子系统）
- 更新 `src/state.py`（NPC 参数）
- 更新 `app.py`（骰子结果显示）
- `tests/test_dice.py`（骰子单元测试）
