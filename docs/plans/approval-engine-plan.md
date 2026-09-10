# 实施计划：GAME_SPEC.md 第一章至第九章对齐

## 0. 前置问题

### 0.1 Critical: EntityTaskForce 未导入
- `src/state.py:268` 引用 `EntityTaskForce` 但未 import
- 导致 8 个模块无法导入（state, aircraft, ap, scouting, events, npc, pipeline, initial_state）
- 修复：添加 `from src.entities import TaskForce as EntityTaskForce`

### 0.2 Pytest Segfault
- pytest 9.0.3 在此 macOS 环境 segfault（非项目问题）
- 替代方案：用 Python 脚本直接跑测试逻辑

---

## Phase 1: 修复阻塞 Bug
- Step 1.1: src/state.py — 添加 EntityTaskForce import
- Step 1.2: 验证所有模块可导入

## Phase 2: Chapter 4 — 状态系统
- Step 2.1: actual_enemy 公开化（PrivateAttr → Field）
- Step 2.2: enemy_fleet 公开化（PrivateAttr → Field）
- Step 2.3: 统一 Position 类（删除 entities.py 重复定义）
- Step 2.4: 更新所有引用处
- Step 2.5: 验证 + 测试

## Phase 3: Chapter 3 — 地理系统
- Step 3.1: world_to_hex 输入校验（lat/lon 范围检查）
- Step 3.2: 验证 + 测试

## Phase 4: Chapter 2 — 时间/AP 系统
- Step 4.1: check_game_over pipeline step
- Step 4.2: server.py /advance 检查 game_phase
- Step 4.3: 验证 + 测试

## Phase 5: Chapter 7 — 骰子系统
- Step 5.1: 新增 roll_npc_decision 函数
- Step 5.2: 验证 + 测试

## Phase 6: Chapter 5 — 航空系统
- Step 6.1: POST /plan-strike, /confirm-strike, /reject-strike, /recall 端点
- Step 6.2: 验证 + 测试

## Phase 7: Chapter 6 — 侦察系统
- Step 7.1: 反向检定（SC-007）
- Step 7.2: POST /plan-scout, /confirm-scout 端点
- Step 7.3: 验证 + 测试

## Phase 8: Chapter 8 — NPC 系统
- Step 8.1: 新增 trigger_npc_speech 函数
- Step 8.2: 验证 + 测试

## Phase 9: Chapter 9 — 海图系统（确认完成）

## Phase 10: 全量测试 + 最终报告
