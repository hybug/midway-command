# 技术架构文档 · TECH_ARCH.md

> 描述 Phase 3 阶段的系统设计。

---

## 1. 总体架构

```
┌───────────────────────────────────────────────────────┐
│   Frontend  ·  Streamlit (Python)                      │
│   - 对话窗口                                          │
│   - 战况一览(state 投影)                              │
│   - 状态变化通知横幅                                  │
│   - 手动修正面板(调试用)                              │
└────────────────────────┬──────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────┐
│   Orchestrator  ·  app.py                              │
│   - 玩家输入接收                                      │
│   - 状态变化检测(pre/post digest 比较)                │
│   - 状态变化横幅渲染                                  │
│   - 手动修正命令                                      │
└───────┬───────────────────────┬───────────────────────┘
        │                       │
        ▼                       ▼
┌──────────────────┐   ┌───────────────────────────────┐
│  GameState       │   │  NPC Agents                   │
│  src/state.py    │◀──│ src/agents/*.py               │
│                  │   │                               │
│  (Pydantic,      │   │ (每个 = 一个 LLM 会话)        │
│   唯一真相源)    │   │ - Browning · 参谋长           │
│  - TaskForce     │   │                               │
│  - AirGroup      │   │ 直接执行:                     │
│  - EnemyKnown    │   │ execute_action → 修改 state   │
│  - _hidden actual│   │                               │
└──────────────────┘   └───────────────────────────────┘
```

---

## 2. 核心设计变更(Phase 3)

### 从"Tool Use"到"直接执行"

Phase 1-2 的设计是 LLM 调用 tool → 返回结果 → 玩家确认 → 执行。

**Phase 3 改为**: LLM 输出自然语言 → App 层捕获状态变化 → 直接执行 → 事后通知。

**原因**:
- Kimi Code 的 function calling 不可靠(经常不调用 tool)
- "直接执行 + 偏差"更符合核心玩法"理解偏差"
- 减少交互步骤,节奏更快

### execute_action 工具

Browning 现在使用 `execute_action` 而非 `propose_action`:

| 动作类型 | 效果 | 偏差表现 |
|---------|------|---------|
| `set_course` | 直接修改 `task_force.course` | 总是更激进的航向(更接近敌人) |
| `set_speed` | 直接修改 `task_force.speed` | 倾向于加速 |
| `adjust_cap` | 直接修改 `carrier.cap_strength` | 倾向于减少 CAP(腾出飞机准备攻击) |

**关键**: execute 的 handler 直接修改 state,不记录 pending,不等待确认。

---

## 3. 状态变化检测

### 3.1 机制

在 NPC 执行前,App 层捕获 state digest:
```python
pre_digest = (course, speed, tuple(cap_strengths), ...)
```

NPC 执行后,比较 post state:
```python
post_changes = detect_changes(pre_digest, state)
```

如果有变化,UI 显示横幅:
```
⚡ Browning 已执行调整：航向 240° → 320°
```

### 3.2 目的

- 让玩家**事后发现**偏差(而不是事前确认)
- 创造"你怎么擅自改了?"的惊喜感
- 纠正需要额外的对话轮次(有成本)

---

## 4. 模块职责

### 4.1 GameState (`src/state.py`)

**唯一真相源**。所有游戏数据。

- Pydantic v2 模型
- `pending_suggestions` 字段已废弃(Phase 3 不再使用)
- 序列化/反序列化用于测试和调试

### 4.2 Tools (`src/tools.py`)

- `query_fleet_status`: 查询舰队状态（只读）
- `propose_recon`: 规划侦察任务（生成方案，等待玩家确认）
- `execute_action`: 直接执行行动（航向、速度、CAP）
  - `set_course`: 0-359°
  - `set_speed`: 0-35节
  - `adjust_cap`: ≥0
- `set_course()`: App 层手动修正用

**侦察流程**：`propose_recon` → 玩家确认 → `execute_action(launch_scout)`

### 4.3 NPC Agents (`src/agents/*.py`)

- `base.py`: 抽象基类,`chat()` 方法,情绪检测
- `browning.py`: 参谋长
  - system prompt 强调"直接执行,不要确认"
  - 中文回复 + "中文(英文)"术语格式
  - 激进的性格设定

### 4.4 LLM Client (`src/llm.py`)

- Kimi Code API (OpenAI-compatible)
- `User-Agent: claude-code` header(必需)
- Tool use 循环(备用,主要用 execute_action)
- `reasoning_content: ""` (Kimi Code 要求)

---

## 5. 项目结构(Phase 3)

```
midway-command/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── docs/
│   ├── GAME_DESIGN.md        ← 玩法
│   ├── TECH_ARCH.md          ← 本文档
│   └── HISTORICAL_NOTES.md   ← 历史事实
│
├── plan/
│   ├── OVERVIEW.md           ← 进度总览
│   └── day01-10.md           ← 每日计划
│
├── logs/                     ← 决策日志
│   ├── decision.log
│   └── streamlit.log
│
├── src/
│   ├── __init__.py
│   ├── app.py                ← Streamlit 入口
│   ├── config.py             ← 环境变量
│   ├── llm.py                ← Kimi Code SDK 封装
│   ├── state.py              ← GameState
│   ├── initial_state.py      ← 04:00 史实初始化
│   ├── tools.py              ← execute_action + query
│   └── agents/
│       ├── __init__.py
│       ├── base.py           ← NPCAgent 基类
│       └── browning.py       ← 参谋长 NPC
│
└── tests/
    ├── __init__.py
    ├── test_state.py
    └── test_agents.py
```

---

## 6. 关键决策记录

| 决策 | 选项 | 选择 | 原因 |
|------|------|------|------|
| 核心玩法 | 精确命令 / 理解偏差 | **理解偏差** | 更有游戏性,符合史实 |
| 执行方式 | 建议→确认→执行 / 直接执行 | **直接执行** | 创造纠正成本,体现性格 |
| LLM tool | 可靠调用 / 备用方案 | **备用方案**(execute) | Kimi Code function calling 不稳定 |
| 开局 | 已知敌情 / 双方盲搜 | **双方盲搜** | 更符合史实,增加紧张感 |
| 前端 | React / Streamlit | **Streamlit** | 快速迭代 |
| LLM | Claude / Kimi | **Kimi Code** | 用户已有订阅,中文强 |

---

## 7. 性能与成本

**单次游玩**: ~20-30 分钟,20-40 轮对话
**成本**: ~¥0.5-2 (Kimi Code)
**资源**: 本地 CPU,内存 < 500MB
