# Phase N 玩法闭环验收（N.6 · 提案→批准→航行→上图端到端实证）

日期：2026-09-14 · 执行人：N.6 实现代理 · 基准提交：399953d（命令卡联动航线提案）
链路：`POST /routes`（模拟参谋产物，绕开 LLM——参谋链路由 fake client 测试覆盖）→ `POST /routes/{id}/approve` → `POST /advance {"minutes":15}` ×15 → `GET /routes` status=done → 海图实拍三态。

## 复现命令与请求/响应摘要

### 0. 探活与重启

```bash
curl -s -o /dev/null -w "%{http_code}" localhost:8000   # 200，但 GET /routes 404
```

**发现**：存活 uvicorn（PID 26536）系旧代码（航线端点合入前启动），`GET /routes` 404。kill 后由 `/tmp/uvicorn_keepalive.sh` 自动拉起新进程，`GET /routes` → `{"routes":[]}`（内存态同步复位为空）。

### 1. 截「批准前」图（空态）

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --hide-scrollbars --window-size=1440,900 --timeout=60000 --virtual-time-budget=1200 \
  --screenshot=docs/reports/product-compare/phase-n-verify-before.png "http://localhost:8000/"
```

实拍：海图无任何航线，TF16（ENT 圈标）在图左外缘 CSE 270，命令卡 STAFF PROPOSAL / NO PENDING ORDERS，时钟 13:00Z。
（phase-m 先例的 `--virtual-time-budget=9000` 本轮挂起：rAF 动画环每帧全量重绘做旧海图，9000 虚拟秒 ≈560 帧渲染未能在 Chrome --timeout 内收敛；1200 预算 4.5s 出图，首帧即触发 `/routes` 拉取，足够。）

### 2. 建航线 → 批准

```bash
curl -s -X POST localhost:8000/routes -H "Content-Type: application/json" \
  -d '{"kind":"mission","owner":"TF16","waypoints":[{"lat":28.4,"lon":-177.9},{"lat":28.8,"lon":-177.5},{"lat":29.2,"lon":-177.0}]}'
```

响应摘要：`{"id":"3c98a83ade0b42bf8d6e671814f8b4f0","kind":"mission","owner":"TF16","status":"draft","progress":0,...}`

```bash
curl -s -X POST localhost:8000/routes/3c98a83ade0b42bf8d6e671814f8b4f0/approve
```

响应摘要：同体，`"status":"active"`（draft → active 状态机正确）。

### 3. advance ×3 → 截「批准后+航行中」图

```bash
curl -s -X POST localhost:8000/advance -H "Content-Type: application/json" -d '{"minutes":15}'
# 响应：{"notifications":[],"ap":{"current":3,...},"game_over":false}（舰队位置读 GET /state）
```

3 tick 后 GET /state：TF16 (28.36972, -177.95333)，course 57（=起点→wp1 实时推导向 57.0°）；route `status=active progress=0`（未到 wp1 不切弯，符合 `advance_route_fleet` 语义）。

实拍 `phase-n-verify-during.png`：时钟 13:45Z；ENT/HOR 双标记 CSE 57 东北向移动；**墨蓝虚线 mission 航线在图**——routeBlue(#3d5a73) 像素沿 (404,82)→(310,188) 对角分布，拟合斜率 −1.128（投影预测 wp2→wp1 可见段 −1.137）；wp2/wp3 位于 45nm 取景框外，线出画上缘（取景特性）。

### 4. advance 至走完 → 截「完成」图

循环 `POST /advance {"minutes":15}` + 每 tick 读 /state 与 /routes，第 12 tick（累计第 15 tick）：

```
GET /routes → status: done | progress: 3 | kind: mission
```

实拍 `phase-n-verify-done.png`：时钟 16:45Z（13:00Z+15×15min ✓）；底栏 29.2°N 177.0°W / CSE 48°（=wp3 吸附位与末段实时导向）；舰队标记随航路出 45nm 取景框（预期）。done 航线淡化（alpha 0.35）在图：before/done 像素差分走廊 62 hits，拟合斜率 **−1.136 vs 预测 −1.137**。

### 5. track 点线演示（fixture，非自动生成）

**设计事实**：done 后系统**不**自动生成 track——mapRenderer.js L808 状态过滤裁定「done 淡（alpha 0.35）」，track 为独立 kind。按任务书要求演示点线样式，沿实际走过路径（起点→wp1→wp2→wp3）登记航迹：

```bash
curl -s -X POST localhost:8000/routes -H "Content-Type: application/json" \
  -d '{"kind":"track","owner":"TF16","waypoints":[{"lat":28.2,"lon":-178.251012},{"lat":28.4,"lon":-177.9},{"lat":28.8,"lon":-177.5},{"lat":29.2,"lon":-177.0}]}'
# → id ba9fb97b714544b7b86d28aa8f713f9f, draft；approve → active
```

实拍 `phase-n-verify-track.png`：track 点线 [1,3] 沿实际航迹上图。start→wp1 段（mission 线不覆盖区）done/track 像素差分 **89 hits，距理论线段中位 1.1px / p90 1.6px**。

## 舰队位置序列 vs 航线 waypoints 对照

理论：25kt × 15min = **6.25 nm/tick**（任务书预估 ~12.5nm 系按 50kt 误估，实际 scenario TF16 speed=25）。全程 89.64 nm / 93.75 nm 预算。

| tick | 位置 (lat, lon) | course | 对照航线 |
|---|---|---|---|
| 0（批准时） | 28.20000, −178.25101 | 270 | 起点（wp1 下游 22.10nm @57°） |
| 1* | 28.25672, −178.15187 | 57 | 沿 57° 向 wp1（*推导位，见注） |
| 2* | 28.31335, −178.05262 | 57 | 同上（*推导位，见注） |
| 3 | 28.36972, −177.95333 | 57 | 距 wp1 3.1nm，「航行中」实拍态 |
| 4 | 28.43631, −177.86386 | 41 | **切弯 wp1 (28.4,−177.9)** → progress 1，导向 41.2° ✓ |
| 5 | 28.51461, −177.78582 | 41 | 航段 2 |
| 6 | 28.59286, −177.70766 | 41 | 航段 2 |
| 7 | 28.67107, −177.62939 | 41 | 航段 2 |
| 8 | 28.74923, −177.55100 | 41 | 距 wp2 3.0nm |
| 9 | 28.82465, −177.46936 | 47 | **切弯 wp2 (28.8,−177.5)** → progress 2，导向 47.4° ✓ |
| 10 | 28.89503, −177.38178 | 47 | 航段 3 |
| 11 | 28.96534, −177.29407 | 47 | 航段 3 |
| 12 | 29.03560, −177.20625 | 48 | 航段 3（临近 wp3 实时导向 48°） |
| 13 | 29.10580, −177.11831 | 48 | 航段 3 |
| 14 | 29.17594, −177.03025 | 48 | 距 wp3 3.2nm |
| 15 | **29.20000, −177.00000** | 48 | **精确吸附 wp3 → status=done, progress=3** ✓ |

注：tick 1–2 的 POST 已生效但响应解析脚本失误未留位，表内为同式（`_advance_formation` 步进公式 + `calculate_bearing`）推导值；tick 3 起全部为 GET /state 实录。到点吸附、切弯推进（progress 0→1→2→3）、逐段实时导向（57°/41°/47–48° vs 理论 57.0°/41.2°/47.4°）逐项吻合。

## 验收结论：**PASS**

| 验收项 | 证据 | 判定 |
|---|---|---|
| 建航线 draft | POST /routes → status=draft | ✅ |
| 批准 active | POST /routes/{id}/approve → status=active（非 draft 400 拒绝由测试覆盖） | ✅ |
| mission 航线上图 | during 实拍蓝虚线，斜率 −1.128 vs 预测 −1.137 | ✅ |
| 舰队沿航线移动 | 15 tick 位置序列逐段吻合，course 57/41/47-48 vs 理论 57.0/41.2/47.4 | ✅ |
| 走完 status=done | GET /routes → done, progress=3，wp3 精确吸附 | ✅ |
| done 淡化上图 | before/done 差分斜率 −1.136 | ✅ |
| track 点线 | fixture kind=track 差分 89 hits，中位距线 1.1px | ✅ |
| 时钟推进 | 13:00Z → 16:45Z = 15×15min | ✅ |

## 发现与偏差记录（均非代码缺陷，零修复）

1. **旧 uvicorn 进程**：存活进程系航线端点合入前启动，`GET /routes` 404——重启即愈。属环境态，非代码 bug（keepalive 脚本无 --reload）。
2. **9000 virtual-time-budget 挂起**：rAF 每帧全量重绘做旧海图，大虚拟时间预算无法在 Chrome timeout 内收敛（渲染进程 100% CPU 8 分钟未出图）。改 1200（首帧即拉 /routes）4.5s 出图。截图方法论项，非玩法链路缺陷。
3. **每 tick 位移 6.25nm 非 12.5nm**：TF16 scenario speed=25kt，任务书按 50kt 误估；实现按 `speed × minutes/60` 正确。
4. **done 不自动生成 track**：mapRenderer L808 状态过滤为设计裁定（done 淡化原样式）；track 独立 kind 经 fixture 演示点线在图。若需「走完自动落航迹」属新功能，不在本验收面。
5. **wp2/wp3 与完成态舰队标记出 45nm 取景框**：取景窗（28.75°N 以北出画）特性，位置读数由底栏 29.2°N 177.0°W 与 /state 实录佐证。

## 存证

- `phase-n-verify-before.png`：批准前空态（无航线，TF16 图左外缘 CSE 270）
- `phase-n-verify-during.png`：批准后航行中（mission 蓝虚线 + ENT/HOR CSE 57 沿线移动）
- `phase-n-verify-done.png`：走完态（done 淡化线，底栏 29.2°N 177.0°W）
- `phase-n-verify-track.png`：track 点线沿实际航迹上图（fixture 演示）
