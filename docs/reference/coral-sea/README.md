# 珊瑚海海战史实资料包（Coral Sea, 1942-05-04 ~ 05-08）

> 状态：**P0 完整 + P1 骨干**（P2 逐项位置见 §缺口）
> 上级计划：`docs/plans/coral-sea-historical-research-plan.md`
> 机器可读数据：`data/`（7+1 个 JSON，全部通过 `tools/validate_coral_sea_data.py`）
> 服务对象：S4 指挥链、S2/S3 通信与判断场景、S6 行动演算、S9 战区内容

## 使用纪律

1. **每条关键事实必须带 `source_ids`**；来源等级 PRIMARY / OFFICIAL / ARCHIVAL / SECONDARY / TERTIARY，事实等级 CONFIRMED / PROBABLE / UNKNOWN / CONFLICTED / ESTIMATED。
2. **时间双轨**：所有事件同时保留舰队当地时间和 Zulu 时间；舰队时区在 1942-05-07 17:00（当地）前为 **Z−11:30**，之后为 **Z−11**（SRC-TF17 原注）。战区民用时（莫尔兹比/拉包尔）为 **Z+10**，仅地理参考。
3. **`ESTIMATED` 是游戏建模值**，不是史实值，字段内必须带 `estimate_note`。
4. 未确认姓名一律**职务名 +（职务名）后缀**；禁止用影视、小说、游戏补全。
5. 数据缺口如实登记于 `uncertainties.md`，不编造。

## 文档地图

| 文档 | 内容 | 主要服务 |
|---|---|---|
| `sources.md` | 来源登记与等级、访问与版权 | 全部 |
| `timeline.md` | 战役时间线（当地/Zulu 双轨） | S2/S3 场景 |
| `order-of-battle.md` | 双方编制与旗舰 | S4/S6 |
| `command-relationships.md` | 指挥关系与通信关系 | S4 |
| `personnel.md` | 人员名单（含证据等级） | S4 |
| `communications.md` | 电报、接触报告、情报链、JN-25 | S2/S3 |
| `decisions.md` | 关键决策链（决策点/时间/依据） | S3/S7 |
| `geography.md` | 地理、港口、机场、水道与坐标 | S6/S9 |
| `environment.md` | 天气、日光、海况 | S6 |
| `aircraft.md` + `data/aircraft.json` | 飞机参数与航空队编制 | S6 |
| `ships.md` + `data/ships.json` | 舰艇参数 | S6 |
| `losses.md` + `data/losses.json` | 命中、损伤、沉没、伤亡 | S6/S7 |
| `uncertainties.md` | 冲突与缺口清单 | 全部 |
| `data/timeline.json` | 时间线脊柱（引用 events.json） | 校验 |
| `data/events.json` | 全部事件（含时间双轨） | S2/S3 |

## 机器数据校验

```bash
python tools/validate_coral_sea_data.py docs/reference/coral-sea
pytest tests/test_coral_sea_reference_data.py -q
```

校验覆盖：schema 枚举、来源引用闭合、CONFIRMED 需一手/官方来源、ESTIMATED 显式标注、
Zulu 换算、时间线单调、坐标落在战区包范围（lat −24..−4 / lon 144..170）、
编队旗舰存在、嵌套编队豁免的同日互斥、损失≤在编、S4 运行名册纪律。

## P0/P1/P2 完成度

| 层级 | 内容 | 状态 |
|---|---|---|
| P0 | 主要编队与旗舰；指挥官/参谋/舰长；五航母；主要舰载机参数；关键搜索/报告/决策；关键战损 | ✅ |
| P1 | 全部护航舰艇登记；航空兵编制与损失；通信/雷达/武器配置；天气日光；岸基航空 | ◐（骨干完成，缺逐日位置与完整电文） |
| P2 | 舰艇逐日位置；完整电文摘录；舰员个体档案；弹着图；影像 | ❌ 未采（登记于 uncertainties.md） |
