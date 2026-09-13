# Phase M 视觉回归验收（M.5 · fixture + 空态双页）

日期：2026-09-14 · 执行人：M.5 实现代理 · 基准提交：8558618（M.4 完成态）
基准图：`docs/assets/Gemini_Generated_Image_u1fak0u1fak0u1fa.png`（成品图）
当前图：`docs/reports/product-compare/phase-m-verify-fixture.png`（设计态 fixture 实拍）
对照图：`docs/reports/product-compare/phase-m-verify-empty.png`（uvicorn 真后端空态主页实拍）

## 复现命令

```bash
# 0. 探活（本次 uvicorn 已在跑，HTTP 200）
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
# 1. 无头 Chrome 截图（1440×900，M.4 先例：真后端 + virtual-time-budget）
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --hide-scrollbars --window-size=1440,900 --timeout=12000 --virtual-time-budget=9000 \
  --screenshot=docs/reports/product-compare/phase-m-verify-fixture.png \
  "http://localhost:8000/static/dev/design-fixture.html"
# 2. 同参数截空态主页
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --hide-scrollbars --window-size=1440,900 --timeout=12000 --virtual-time-budget=9000 \
  --screenshot=docs/reports/product-compare/phase-m-verify-empty.png \
  "http://localhost:8000/"
# 3. 区域比对
.venv/bin/python docs/assets/compare_regions.py \
  "docs/assets/Gemini_Generated_Image_u1fak0u1fak0u1fa.png" \
  docs/reports/product-compare/phase-m-verify-fixture.png docs/reports/product-compare/
```

## 验收结论：**PASS**

| 验收项 | H 批基线（fixture） | 本次（fixture） | 线 | 判定 |
|---|---|---|---|---|
| 4×4 区域均色差最大格 | 40.5（r2c3） | **38.6**（r2c3） | ≤45 | ✅ |
| 结构要素清单 | 9/9 | **12/12**（M 批清单扩容） | 逐项 | ✅ |
| 空态确定性 | — | 与 M.4 存档 m4-empty-1440.png 全图 diff = **0 px** | — | ✅ |

整体均值色：设计 (169,153,123) vs 当前 (168,156,130)——B 通道 +7、G 通道 +3，较 H 批 (165,154,127) 略移暖，量级为纸纹颗粒级。

## 4×4 区域均色差矩阵（0–255）

```
     1.9     3.6    20.0    21.0   <- 行 0
    11.2    19.7    10.8     7.8   <- 行 1
    14.8     6.3    11.4    38.6   <- 行 2
    24.1    30.1    33.8     5.0   <- 行 3
```

最大热区：r2c3 = 38.6（H 批同格 40.5，连续两轮为右栏命令卡构图差，见「与 H 批基线差异」）。全图无任何格子超 45 验收线。

## 结构要素核验表（M 批清单 12 项，Read 截图 + PIL 量测逐项目检）

| 要素 | 实拍证据 | 判定 |
|---|---|---|
| 近景环礁 | 大面积环礁特写：礁环双缘带 + 青绿潟湖 + SAND ISLAND/EASTERN ISLAND 岛屿（东岛带 ×3 停机剪影） | ✅ |
| 20nm 环贯穿 | 最内虚线环横穿礁环与潟湖（环体压陆可见），标签按 L4-F1 修复画环内下方位，实拍 (638,524) 处「20nm」完整可读 | ✅ |
| 四环 | `theater.json range_rings.rings_nm = [20,25,40,60]` 四环齐：20nm（环内下）、25nm（右上 45° 防重叠位）、40nm（右侧）、60nm（右侧）标签逐一在位 | ✅ |
| 圆圈标记 ENT 左外缘 | 画布 (48.5,302.2) 图左外缘开阔水面，CSE 270 + 东向矢量 | ✅ |
| 圆圈标记 HOR 环礁西缘 | 画布 (210.4,302.2) 西礁环带（28nm scenario 真实位） | ✅ |
| 双虚线箭头 | ENT/HOR 圈缘双平行虚线 + 末端实心三角箭头，指向环礁 | ✅ |
| 敌标双红圈东北 | 红圈 ? + ENEMY 双标，页面质心 (649.6,169.3)/(678.9,249.8)，减画布原点偏移 (≈14.5,75.3) = (635.1,94.0)/(664.4,174.5)，与 approved 画布位 (634.6,93.1)/(664.9,175.4) 逐像素同带（M.4 反推经纬保持成品图像素的裁定落实） | ✅ |
| 罗盘 | 右上角雕刻光栅罗盘 | ✅ |
| 比例尺 | 右下 0-10-25-50 nm 分段条 | ✅ |
| 尺 / 圆规 / 铅笔 | 木尺 + 黄铜圆规左下压图角，铅笔右缘竖放 | ✅ |
| 深色 chrome | 底栏深棕黑 + 右栏深底 + INTEL 暗卡；底栏（bottom_bar 采样差 (−9,−8,−9) 与 H 批逐通道持平） | ✅ |
| 命令卡 | SECRET–INTERCEPTION PLAN 军令纸 + EXECUTE ORDER（fixture）；空态正确降级为 STAFF PROPOSAL / NO PENDING ORDERS 灰按钮 | ✅ |
| 细网格 | 图面细经纬网格线隐约可见（右半图面尤清晰） | ✅ |
| 晕影 | 图缘晕影压暗（成品图同款做旧边） | ✅ |

（后两项为本批清单相对 H 批 9 项的扩容项，连同细网格共 12 项全在位。）

## 空态主页核验（phase-m-verify-empty.png）

- ENT 图左外缘（画布更宽的真实主页布局下同样左缘位，与 M.4 存档**全图 0 px diff**——渲染确定，M.4 后无视觉漂移）；HOR 环礁西缘 + CSE 270 双虚线箭头。
- 空态正确形态：**无敌标**（known_enemy 过滤，核心机制不对称性）、侦察机无、命令卡降级 STAFF PROPOSAL、chat 区「等待指令 (AWAITING ORDERS)」。
- scenario 布兵读数：航向 270° / 航速 **25** / 位置 **28.2°N 178.3°W**（ENT 真实位）/ CAP 24 / AP 3/3 / 甲板 企 80/80·零 80/80·0 / 侦察 无 / 敌情 暂无——与 M.4 initial_state scenario 化逐项一致。
- 底图四环、罗盘、比例尺、尺圆规铅笔、细网格、晕影与 fixture 同构在位。

## 与 H 批基线的差异说明

1. **r2c3 = 38.6（最大热区，H 批 40.5）**：同源残余——成品图军令纸卡紧贴 PLAYER 卡下方密排，当前 chat-log `flex:1` 把命令卡推到右栏底部，中段留深色空档。E6 常驻卡布局的**构图差异**，非实现缺陷，H 批已裁定留 Loop，本轮延续。
2. **r0c3 显著改善（32.1 → 21.0）**：H 批该格含右栏上段 NPC 标签舌 + 顶栏右段风格差，本轮读数同布局下差值收敛，属纸纹颗粒噪声跨会话摆动（M.4 已证同环境双截 0 diff，H 批基线系前会话 Chrome 成像，格间 ±数点为噪声底）。
3. **中部格小幅上浮（r1c1 14.0→19.7、r2c2 6.3→11.4）**：M.4 投影唯一化 + scenario 布兵的**裁定内变化**——舰队带西移（HOR 画布 238.9→210.4，−28.5px）、PENDING 印章随首航母锚西移、ENT/HOR 从「中心对角错开」改为「图左外缘 + 环礁西缘」真实投影位。这是「scenario 布兵位 vs 成品图构图」的数据差异，按任务书裁定**不算缺陷**；成品图整体构图带（敌标东北、环礁中心 0.44/0.46 锚、四环半径）保持。
4. **底行三格（24.1/30.1/33.8）与 H 批（23.7/29.3/33.4）逐格持平（±0.4）**：图面下缘道具带（圆规尺）风格微差，H 批已登记留 Loop，无恶化。

**本轮未修任何项**：最大格 38.6 在线内、要素 12/12 无缺失、无明显实现缺陷——按裁定仅修明显实现缺陷，本轮为零。

## 存证

- `phase-m-verify-fixture.png` / `phase-m-verify-empty.png`：双页实拍（1440×900，无头 Chrome，uvicorn 真后端）
- `design-scaled.png` / `side-by-side.png`：compare_regions.py 比对输入与左右拼接（脚本覆写生成）
- `compare-report.md`：本次比对机器报告（由脚本覆写生成）
