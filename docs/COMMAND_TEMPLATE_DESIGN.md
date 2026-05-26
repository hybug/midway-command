# 作战命令模板设计

> 基于真实的 CINCPAC Operation Plan No. 29-42 (1942年5月27日) 格式设计

---

## 一、真实格式分析

### 1.1 CINCPAC Operation Plan 29-42 结构

真实的二战美军海军作战计划使用**大纲编号式**，不是 SMEAC 五段式。

```
1. TASK ORGANIZATION（编队组织）
   1.a. Task Force 16 — Spruance
   1.b. Task Force 17 — Fletcher
   1.c. ...

2. TIME OF INITIAL DEPLOYMENT（初始部署时间）

3. RECONNAISSANCE（侦察）
   3.a. PBY patrol（PBY巡逻）
   3.b. Submarine patrol（潜艇巡逻）
   3.c. Patrol plane maintenance（巡逻机维护）
   3.d. Photographic reconnaissance（照相侦察）

4. BATTLE INSTRUCTIONS（作战指令）
   4.a. 战役概念
   4.b. 侦察计划（详细）
   4.c. 航空作业计划

5. WEATHER（气象）

6. SHORE-BASED AIRCRAFT（岸基航空）

7. SUBMARINES（潜艇）

8. PATROLLING AND ROUTE ASSIGNMENT（巡逻路线）

9. TASK FORCE 1 — MAIN BODY（主力舰队）
   9.a. 任务
   9.b. 行动计划
   9.c. 机动

10. TASK FORCE 7 — MIDWAY GARRISON（中途岛守军）

11. TASK FORCE 8 — SUPPORT GROUP（支援群）

12. TASK FORCE 16 + 17 — CARRIER TASK FORCES（航母特遣舰队）
    12.a. 任务
    12.b. 行动计划
    12.c. 侦察计划
    12.d. 通信
```

### 1.2 关键特点

| 特点 | 说明 |
|------|------|
| **大纲式** | 1, 1.a, 1.a.(1) 层级，不是五段式 |
| **规划式语言** | "将执行"、"应负责"，不是命令式 |
| **详细侦察** | 侦察计划单独一段，有扇面、高度、搜索模式 |
| **编队组织** | 每艘舰的名称都列出 |
| **任务嵌入** | 任务不在独立段落，而是嵌在各段落里 |

---

## 二、命令模板设计

基于真实格式，设计以下命令类型：

### 2.1 侦察命令 (RECON)

```
═══════════════════════════════════════════════════════
  美国海军 · 第16特混舰队 · 作战命令
═══════════════════════════════════════════════════════
  编号: TF16-RECON-001          1942年6月4日
  时间: 04:15 (Z+12)           分类: 机密
  签发: 参谋长 M.R. Browning
  呈报: 指挥官 R.A. Spruance
═══════════════════════════════════════════════════════

1. 任务 (MISSION)
  派出 SBD 侦察机搜索西北方向，定位日军机动部队。

2. 执行 (EXECUTION)

  2.a. 侦察计划
    飞机型号: SBD-3 Dauntless（侦察型）
    数量: 6 架
    来源: 企业号（CV-6）

  2.b. 搜索参数
    扇面: 280° - 340°
    航程: 200 海里
    高度: 1000 英尺

  2.c. 时间表
    起飞: 04:30
    到达搜索区域: 05:15
    完成搜索: 06:15
    预计回报: 05:30 - 06:00

3. 行政后勤 (LOGISTICS)
  燃油: 满载
  弹药: 无（侦察任务）
  通信: TBS 无线电报告

4. 指挥与信号 (COMMAND & SIGNAL)
  指挥官: TF16 指挥官
  通信频率: TBS Channel 1

═══════════════════════════════════════════════════════
  [批准执行]  [驳回修改]
═══════════════════════════════════════════════════════
```

### 2.2 航线命令 (COURSE)

```
═══════════════════════════════════════════════════════
  美国海军 · 第16特混舰队 · 作战命令
═══════════════════════════════════════════════════════
  编号: TF16-COURSE-001         1942年6月4日
  时间: 04:30 (Z+12)           分类: 机密
  签发: 参谋长 M.R. Browning
  呈报: 指挥官 R.A. Spruance
═══════════════════════════════════════════════════════

1. 任务 (MISSION)
  调整舰队航向至 300°，缩短接敌距离。

2. 执行 (EXECUTION)

  2.a. 航向调整
    当前航向: 240°
    新航向: 300°
    调整幅度: 60°

  2.b. 航速调整
    当前航速: 25 节
    新航速: 28 节

  2.c. 生效时间
    立即生效

3. 指挥与信号 (COMMAND & SIGNAL)
  指挥官: TF16 指挥官

═══════════════════════════════════════════════════════
  [批准执行]  [驳回修改]
═══════════════════════════════════════════════════════
```

### 2.3 打击命令 (STRIKE)

```
═══════════════════════════════════════════════════════
  美国海军 · 第16特混舰队 · 作战命令
═══════════════════════════════════════════════════════
  编号: TF16-STRIKE-001         1942年6月4日
  时间: 06:30 (Z+12)           分类: 机密
  签发: 参谋长 M.R. Browning
  呈报: 指挥官 R.A. Spruance
═══════════════════════════════════════════════════════

1. 任务 (MISSION)
  派出攻击波打击日军机动部队。

2. 执行 (EXECUTION)

  2.a. 攻击波组成
    SBD 俯冲轰炸机: 35 架
    TBD 鱼雷机: 12 架
    F4F 护航战斗机: 10 架
    来源: 企业号（CV-6）

  2.b. 目标
    日军航母机动部队
    方位: 320°，距离: 180 海里

  2.c. 出发时间
    起飞: 06:30
    预计到达: 08:00

  2.d. 出发模式
    Deferred Departure: 元素等待彼此，整体前往目标区

  2.e. 挂载偏好
    Offensive Power: 重载荷优先

3. 行政后勤 (LOGISTICS)
  燃油: 满载
  弹药: SBD 挂 1000 磅炸弹，TBD 挂 Mk13 鱼雷
  通信: TBS 无线电报告

4. 指挥与信号 (COMMAND & SIGNAL)
  指挥官: TF16 指挥官
  攻击波指挥: McClusky

═══════════════════════════════════════════════════════
  [批准执行]  [驳回修改]
═══════════════════════════════════════════════════════
```

### 2.4 防御命令 (DEFENSE)

```
═══════════════════════════════════════════════════════
  美国海军 · 第16特混舰队 · 作战命令
═══════════════════════════════════════════════════════
  编号: TF16-DEFENSE-001        1942年6月4日
  时间: 05:00 (Z+12)           分类: 机密
  签发: 参谋长 M.R. Browning
  呈报: 指挥官 R.A. Spruance
═══════════════════════════════════════════════════════

1. 任务 (MISSION)
  加强战斗空中巡逻（CAP），防御日军空袭。

2. 执行 (EXECUTION)

  2.a. CAP 部署
    企业号: 12 架 → 16 架
    大黄蜂号: 12 架 → 16 架

  2.b. 巡逻高度
    低空: 5000 英尺
    中空: 10000 英尺
    高空: 20000 英尺

  2.c. 轮换间隔
    每 2 小时轮换一次

3. 指挥与信号 (COMMAND & SIGNAL)
  指挥官: TF16 指挥官
  通信频率: TBS Channel 1

═══════════════════════════════════════════════════════
  [批准执行]  [驳回修改]
═══════════════════════════════════════════════════════
```

---

## 三、技术实现

### 3.1 通用模板类

```python
@dataclass
class OperationOrder:
    """通用作战命令模板"""
    order_type: str          # RECON, COURSE, STRIKE, DEFENSE
    order_number: str        # TF16-RECON-001
    date: str               # 1942年6月4日
    time: str               # 04:15 (Z+12)
    classification: str     # 机密
    issuer: str             # 参谋长 M.R. Browning
    recipient: str          # 指挥官 R.A. Spruance
    mission: str            # 任务描述
    execution: dict         # 执行细节
    logistics: dict         # 行政后勤
    command: dict           # 指挥与信号
    
    def render(self) -> str:
        """渲染为格式化文本"""
        ...
```

### 3.2 命令工厂

```python
class OrderFactory:
    """命令工厂 - 根据类型生成命令"""
    
    @staticmethod
    def create_recon_order(params: dict) -> OperationOrder:
        """创建侦察命令"""
        return OperationOrder(
            order_type="RECON",
            mission=f"派出 {params['aircraft_type']} 侦察机搜索{params['direction']}方向",
            execution={
                "aircraft": f"{params['aircraft_type']} × {params['count']}",
                "sector": f"{params['sector_start']}° - {params['sector_end']}°",
                "range": f"{params['range_nm']} 海里",
                "altitude": f"{params['altitude_ft']} 英尺",
                "timeline": params['timeline'],
            },
            ...
        )
    
    @staticmethod
    def create_course_order(params: dict) -> OperationOrder:
        """创建航线命令"""
        ...
    
    @staticmethod
    def create_strike_order(params: dict) -> OperationOrder:
        """创建打击命令"""
        ...
```

### 3.3 渲染器

```python
class OrderRenderer:
    """命令渲染器"""
    
    def render(self, order: OperationOrder) -> str:
        """渲染命令为格式化文本"""
        return f"""
═══════════════════════════════════════════════════════
  美国海军 · 第16特混舰队 · 作战命令
═══════════════════════════════════════════════════════
  编号: {order.order_number}          {order.date}
  时间: {order.time}           分类: {order.classification}
  签发: {order.issuer}
  呈报: {order.recipient}
═══════════════════════════════════════════════════════

{self._render_mission(order)}
{self._render_execution(order)}
{self._render_logistics(order)}
{self._render_command(order)}

═══════════════════════════════════════════════════════
  [批准执行]  [驳回修改]
═══════════════════════════════════════════════════════
"""
```

---

## 四、实施计划

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | 渲染器 | 实现命令文本渲染 |
| P1 | 侦察命令 | 集成到侦察方案流程 |
| P2 | 航线命令 | 集成到航向调整流程 |
| P3 | 打击命令 | 集成到攻击流程（Day 9） |
| P4 | 防御命令 | 集成到 CAP 调整流程 |
