# Phase 2A: §2 时间/Pipeline 系统 — 实施报告

## 实施内容

### 新建文件
- `src/pipeline.py` — TickStep + Pipeline 实现
- `tests/test_pipeline.py` — TIME-008~009 测试（6 个）

### 核心实现
1. **TickStep dataclass**: name, handler, order, enabled
2. **Pipeline class**:
   - register(step) — 注册步骤，同名覆盖
   - disable(name) / enable(name) — 临时禁用/启用
   - execute(state, minutes) — 按 order 执行，异常跳过

### 测试覆盖
| 规则 | 测试 | 状态 |
|------|------|------|
| TIME-008 | test_pipeline_order | ✅ |
| TIME-008b | test_pipeline_step_exception_continues | ✅ |
| TIME-009 | test_pipeline_register_override | ✅ |
| — | test_pipeline_returns_notifications | ✅ |
| — | test_pipeline_disable | ✅ |
| — | test_pipeline_enable | ✅ |

### 已知问题
- 无

### 下一步
Phase 2B: §5 航空参谋系统（aircraft.py + mission.py）
