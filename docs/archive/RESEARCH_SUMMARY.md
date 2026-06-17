# 研究资料汇总

> 调研日期：2026-05-26
> 主题：二战美军海军作战命令格式 + 侦察系统设计

---

## 一、核心发现

### 1.1 作战命令格式

**来源**: CINCPAC Operation Plan No. 29-42 (1942年5月27日)
**文件**: `docs/CINCPAC-Operation-Plan-29-42.pdf` (243KB, 16页)

**关键发现**:
- 美军海军作战计划使用**大纲编号式**，不是 SMEAC 五段式
- 结构：1. TASK ORGANIZATION → 2. TIME → 3. RECONNAISSANCE → 4. BATTLE INSTRUCTIONS → ...
- 语言是**规划式**（"将执行"），不是命令式
- 侦察计划非常详细，有扇面、高度、搜索模式

### 1.2 Task Force Admiral 游戏设计

**来源**: `docs/TASK_FORCE_ADMIRAL_RESEARCH.md` + `docs/TFA-Demo-Manual.pdf` (46页)

**关键发现**:
- 侦察系统：玩家手动绘制搜索扇区，每架飞机分配一个扇区
- CAP系统：巡逻强度 × 2 = 总飞机数，巡逻高度设置
- 打击系统：打击规划器，出发模式（Deferred/Normal），挂载偏好
- 指挥层级：TF → TG → TU → Individual Ships

### 1.3 中途岛历史背景

**来源**: `docs/HISTORICAL_NOTES.md` + 网络资料

**关键发现**:
- 04:30 PBY 4V58 报告"Enemy carriers"，极短
- 06:07 PBY 报告"Two carriers and main body"（实际有四艘）
- 侦察机找不到日舰 → McClusky 跟踪日驱逐舰找到机动部队
- Spruance 的决策：提前起飞 vs 等情报齐全

---

## 二、对游戏设计的影响

### 2.1 侦察系统

**旧设计**: 玩家说"派侦察机"→ 系统自动生成搜索扇面 → 自动执行

**新设计**: 
- 玩家说"派侦察机"
- 参谋长生成**详细侦察方案**（飞机、扇面、航程、高度、时间线）
- 玩家确认后执行
- 侦察有真实延迟和误差

### 2.2 作战命令格式

**旧设计**: 简单的参数列表

**新设计**:
- 真实的美军海军作战命令格式
- 大纲编号式，不是五段式
- 包含任务、执行、后勤、指挥通信

### 2.3 NPC 自主度

**旧设计**: 简单的"执行/请示"分类

**新设计**:
- 参谋长：直接执行（航向、速度），但侦察要先规划后确认
- 通信官：事事确认
- 舰长：本舰事务自主，大事请示

---

## 三、资料清单

| 文件 | 来源 | 内容 | 大小 |
|------|------|------|------|
| `CINCPAC-Operation-Plan-29-42.pdf` | midway42.org | 中途岛作战计划原文 | 243KB |
| `TFA-Demo-Manual.pdf` | Steam | Task Force Admiral 游戏手册 | 10.7MB |
| `TASK_FORCE_ADMIRAL_RESEARCH.md` | 网络调研 | TFA 游戏机制详解 | 19.6KB |
| `COMMAND_TEMPLATE_DESIGN.md` | 本次设计 | 作战命令模板设计 | 新建 |

---

## 四、下一步

1. 基于真实格式实现作战命令渲染器
2. 集成到侦察方案流程
3. 扩展到航线、打击、防御命令
4. 优化起飞作业流程（参考TFA手册）
