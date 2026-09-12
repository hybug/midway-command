# Midway Theater Pack（中途岛战区包）

## 数据来源

- **AI 生成（仓库自有公式移植，无第三方数据）**：`tools/gen_midway_pack.py` 把
  `static/js/chartRenderer.js` 的程序化环礁（atollOutline 三谐波系数）、双岛、跑道、
  标注公式移植为 GeoJSON 坐标产出——数据与渲染同源，视觉等价由 M.3/M.4 回归验收。
- theater.json 数值锚点 = chartRenderer 现值：center 28.2/-177.4、view_nm 45、
  graticule 0.25/1.0、rings [20,25,40,60]、扇区 30°-90° 沿用。
- 基地坐标 28.2072/-177.3735 = 沙岛机场史实位（美军中途岛陆基航空兵约 113 架，
  docs/reference/HISTORICAL_NOTES.md 口径）。
- scenario 双舰队初始位 = 成品图量取规则：环礁正西 ENT 45nm / HOR 28nm
  （cos(lat) 修正，与 makeProjector 投影同式），course 270、speed 25。

## 许可证

无第三方素材——全部由本仓库代码程序化生成（AI 生成声明），无外部许可证义务。

## 生成方式

```bash
.venv/bin/python tools/gen_midway_pack.py   # 重新产出本目录四文件
.venv/bin/python tools/validate_theater.py  # 校验（硬校验 FAIL / 软校验 WARN）
```

## 备注

- 跑道以 `route_hint` 线要素承载（`name` 前缀 `runway_`）：schema v1 无 runway class，
  虚线淡线渲染语义一致；M.3 ChartEngine 若需专属跑道样式，属 schema 扩展决策。
- 沙岛胶囊宽取 chartRenderer 文字度量守卫下限 62px（基准图面短边 764 换算，见生成器注释）。
