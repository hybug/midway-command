# Day 5 · 多 NPC

**目标**：实现多个 NPC，每个 NPC 有不同的自主度和职责范围。

**预估工作量**：5-6 小时

---

## 设计要点

**新增 NPC**：
| NPC | 职位 | 自主度 | 职责范围 |
|-----|------|--------|---------|
| Murray | 企业号舰长 | 5 | 本舰航行、CAP、损管 |
| Mitscher | 大黄蜂舰长 | 5 | 本舰航行、CAP、损管 |
| 通信官 | 通信官 | 1 | 电报收发 |
| 情报官 | 情报参谋 | 3 | 情报分析、敌情判断 |

**NPC 信息权限**：
- 通信官：原始电报
- 情报官：解读后的情报
- 参谋长：全局态势 + 建议
- 舰长：本舰状态
- 航空参谋：机群状态

**NPC 隔离**：
- 每个 NPC 是独立的 LLM 会话
- NPC 之间不直接对话
- 所有信息通过玩家中转

---

## 任务清单

- [ ] 1. 创建 NPC 配置文件
  - `src/npc_config.py`
  - 每个 NPC 的参数：autonomy, risk_tolerance, initiative, competence
  - 每个 NPC 的信息权限

- [ ] 2. 实现 NPC 基类扩展
  - 更新 `src/agents/base.py`
  - 支持自主度参数
  - 支持信息权限过滤

- [ ] 3. 实现新 NPC
  - `src/agents/murray.py`（企业号舰长）
  - `src/agents/mitscher.py`（大黄蜂舰长）
  - `src/agents/radio_officer.py`（通信官）
  - `src/agents/intel_officer.py`（情报官）

- [ ] 4. 更新 `app.py`
  - NPC 频道切换
  - 不同 NPC 的对话界面
  - NPC 信息权限显示

- [ ] 5. 单元测试
  - 测试 NPC 参数
  - 测试信息权限过滤
  - 测试 NPC 隔离

---

## 成功标准

- [ ] 5 个 NPC 可以切换对话
- [ ] 每个 NPC 有自己的性格和自主度
- [ ] 每个 NPC 只看到自己权限内的信息
- [ ] NPC 之间不直接对话

---

## 产出

- `src/npc_config.py`（NPC 配置）
- `src/agents/murray.py`
- `src/agents/mitscher.py`
- `src/agents/radio_officer.py`
- `src/agents/intel_officer.py`
- 更新 `app.py`（多 NPC 支持）
- `tests/test_npc.py`（NPC 单元测试）
