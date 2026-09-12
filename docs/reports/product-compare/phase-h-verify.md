# Phase H 像素比对验收（H1 fixture + H2 验收流）

日期：2026-09-13 · 执行人：批次 H 实现代理
基准图：`docs/assets/Gemini_Generated_Image_u1fak0u1fak0u1fa.png`（成品图）
当前图：`docs/reports/product-compare/fixture-1440.png`（设计态 fixture 实拍，非空态）

## 复现命令

```bash
# 1. 静态服务（fixture 离线渲染，不经后端；svgLoader 需 http 才能 fetch SVG 资产）
.venv/bin/python -m http.server 8018   # 仓库根
# 2. 无头 Chrome 截图（1440×900）
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --hide-scrollbars --window-size=1440,900 --timeout=12000 \
  --screenshot=docs/reports/product-compare/fixture-1440.png \
  "http://localhost:8018/static/dev/design-fixture.html"
# 3. 区域比对
.venv/bin/python docs/assets/compare_regions.py \
  "docs/assets/Gemini_Generated_Image_u1fak0u1fak0u1fa.png" \
  docs/reports/product-compare/fixture-1440.png docs/reports/product-compare/
```

## 验收结论：**PASS**

| 验收项 | 基线（空态 final-1440） | 本次（fixture） | 线 | 判定 |
|---|---|---|---|---|
| 4×4 区域均色差最大格 | 98.7（r1c3 右栏空态） | **40.5**（r2c3） | ≤45 | ✅ |
| 图面空白采样 B 通道差 | 41 | **−2** | ≤20 | ✅ |
| 结构要素清单 | 部分缺失 | 9/9 在位 | 逐项 | ✅ |

## 4×4 区域均色差矩阵（0–255）

```
     3.9     1.2    20.9    32.1   <- 行 0
    11.4    14.0    14.7    10.1   <- 行 1
    11.9     4.8     6.3    40.5   <- 行 2
    23.7    29.3    33.4     6.8   <- 行 3
```

最大热区：r2c3 = 40.5（基线 98.7，降幅 59%）。整体均值色：设计 (169,153,123) vs 当前 (165,154,127)。

## 关键采样

| 采样 | 设计 RGB | 当前 RGB | 差（当前−设计） |
|------|----------|----------|------------------|
| chart_blank 图面空白 | (231,207,159) | (210,193,158) | (−21,−13,−2) |
| top_bar 顶栏 | (201,184,164) | (188,171,138) | (−12,−13,−26) |
| bottom_bar 底栏 | (62,50,41) | (53,42,33) | (−9,−8,−9) |
| right_col 右栏 | (138,120,102) | (118,105,84) | (−20,−15,−17) |

## 结构要素核验表（Read 截图逐项目检）

| 要素 | 位置（fixture 实拍） | 判定 |
|---|---|---|
| 圆圈标记 ×2（ENT/HOR 空心圆 + 字标） | 画布中心邻域（实体层舰队居中投影，ENT (−14,−28) / HOR (+14,0) 对角错开） | ✅ |
| 双虚线箭头（矢量指向环礁 + 箭头） | ENT/HOR 圈缘出发双平行虚线，末端三角箭头 | ✅ |
| 飞机剪影（在途 + 停机） | SCOUT-2 剪影（w≈26px，随航线 rotate）+ 东岛停机剪影 ×3（G7） | ✅ |
| 敌标 ×2（红虚线圈 + ? + ENEMY） | 环礁东北双标（画布实测质心 (631,96)/(693,167)，间距 Δ=(62,71) 与反推预测 (62,72) 一致） | ✅ |
| SECRET 章（−10° 横版） | 地图左上角 | ✅ |
| 罗盘（雕刻光栅） | 右上角 | ✅ |
| 比例尺（0-10-25-50nm 分段条） | 右下角 | ✅ |
| 尺 / 铅笔 / 圆规桌面道具 | 木尺+黄铜圆规左下、铅笔右缘竖放 | ✅ |
| 深色 chrome（底栏 + 右栏） | 底栏深棕黑（−9,−8,−9）+ 右栏 #241c14 深底 + INTEL 暗卡 + 军令纸卡 | ✅ |

另核验设计态读数：顶栏 09:45 Z（fixture 定妆，不受机器时区影响）、AP 14/20、底栏 航向 270°/航速 30/损伤 企业:LGT（橙红警示）/甲板 企 14/14·0/巡逻 6/侦察 1 西南/敌情 4 CV (REPORTED) 红字，右栏 NPC 标签 + INTEL/PLAYER 双分区 + SECRET–INTERCEPTION PLAN 军令纸（EXECUTE ORDER 在位）。

## 残余热区分析（>30 格）

- **r2c3 = 40.5**（右栏中段）：成品图军令纸卡占位更高（紧贴 PLAYER 卡下方），当前实现 chat-log `flex:1` 把命令卡推到右栏底部，中段留深色空档——**构图差异**（E6 常驻卡布局 vs 成品图密排），非实现缺陷，留 Loop（可议 chat-log 收缩/命令卡上移）。
- **r0c3 = 32.1**（右栏上段 + 顶栏右）：成品图 NPC 标签为浅纸舌深字、顶栏纸色更亮；当前深舌浅字 + 顶栏纸纹偏深（top_bar B 通道 −26 同源）。风格微差，留 Loop。
- **r3c2 = 33.4**（图面左下）：成品图左下为圆规+尺压图角，当前木尺横带更靠下、铅笔未入该格；道具布局微差，留 Loop。

本轮未修任何风格类差异（按裁定仅修明显实现缺陷——本轮无）。

## 存证

- `fixture-1440.png`：设计态 fixture 实拍（1440×900，无头 Chrome）
- `design-scaled.png` / `side-by-side.png`：compare_regions.py 比对输入与左右拼接
- `compare-report.md`：本次比对机器报告（由脚本覆写生成）
