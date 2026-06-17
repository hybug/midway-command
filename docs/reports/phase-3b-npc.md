# Phase 3B: §8 NPC系统 — 实施报告

## 实施内容

### 新建文件
- `src/npc.py` — 信息过滤、LLM 数据准备
- `tests/test_npc_system.py` — NPC-001~007 测试（9 个）

### 核心实现
1. **filter_state_for_npc()** — 根据信息权限过滤 GameState
2. **get_npc_params()** — 获取 NPC 参数
3. **prepare_llm_data()** — 准备 LLM 数据包
4. **get_npc_list()** — 获取 NPC 列表

### 测试覆盖
- 9 个测试全部通过
- 覆盖 NPC-001~007 规则

### 规格对应
| 规则 | 状态 |
|------|------|
| NPC-001 | ✅ test_info_filter_browning, test_info_filter_murray, test_info_filter_comms |
| NPC-007 | ✅ test_no_actual_enemy |
| NPC-006 | ✅ test_llm_data_package, test_llm_data_personality |

### 已知问题
- 无

### 下一步
Phase 4: §9 海图参谋系统（前端 Canvas 渲染）
