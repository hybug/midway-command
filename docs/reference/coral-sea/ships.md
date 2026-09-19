# 舰艇资料（ships）

> 机器可读全量：`data/ships.json`（每舰含来源与置信度）。本表为主要舰艇速览。
> 规格口径：排水量注明「标准/满载/基准」；航速注明「设计/公试」；燃油/航程无一手条件记录处一律 UNKNOWN。

## 五航母（P0）

| 舰 | 型级 | 标准排水量 | 航速 | 舰长 | 结局 | 等级 |
|---|---|---|---|---|---|---|
| USS Yorktown (CV-5) | Yorktown 级 | 19,805 t（设计） | 32.5 kn 设计 / 5/8 实测 ≥30 | Buckmaster | 5/8 中 1 弹未沉 | CONFIRMED（SRC-CV5/SRC-TF17） |
| USS Lexington (CV-2) | Lexington 级 | 36,050 t 级（条约口径诸说） | 33.25 kn 海试 / 受损后 24 | Sherman | 5/8 沉没 | CONFIRMED |
| 翔鹤 Shōkaku | 翔鹤级 | 25,675 t | 34.2 kn 公试 | 城岛高次 | 5/8 重损退特鲁克 | PROBABLE（参数）/CONFIRMED（事件） |
| 瑞鹤 Zuikaku | 翔鹤级 | 25,675 t | 34.2 kn 公试 | 横川市治 | 未中弹；机队损耗大 | PROBABLE |
| 祥凤 Shōhō | 祥凤级（潜母改装） | 11,262 t | 28 kn | 眼目石之助 | 5/7 沉没 | CONFIRMED（事件）/PROBABLE（参数） |

### 关键武装/航空配置

- **约克城**（5/8 实装，SRC-CV5）：8×127mm/38，4×四联 28mm，24×20mm，18×12.7mm；
  CXAM 雷达（中弹失效）；航空队 VB5 18/VF 19(含备)/VS5 17/VT5 13（5/4 初）→
  5/8 出动 17VB+15VS+14VF+9VT。弹药消耗（全役）：5" 404 发、1.1" 2,906、20mm 7,900、12.7mm 15,600。
- **列克星敦**：12×127mm/25 + 28mm/20mm 若干；CXAM-1；载机约 65-70（VF-2/VB-2/VS-2/VT-2）。
- **翔鹤/瑞鹤**：8×127mm/40、12×三联 25mm；无雷达；各载约 63-70（零战/舰爆/舰攻 ≈ 均分）。
- **祥凤**：4×127mm/40、少量 25mm；搭载约 13-16（九六舰战与零战混+舰攻）。

## 巡洋舰（P1 骨干）

| 舰 | 型级 | 主炮 | 编队 |
|---|---|---|---|
| Astoria / Minneapolis / New Orleans | New Orleans 级 | 9×203mm | TG17.5 支援扇面 |
| Portland | Portland 级 | 9×203mm | TF17 |
| Chester | Northampton 级 | 9×203mm | TF17 |
| Chicago | Northampton 级 | 9×203mm | TG17.3 |
| HMAS Australia | County 级 | 8×203mm | Crace 旗舰 |
| HMAS Hobart | Leander 级 | 8×152mm | TG17.3 |
| 妙高 / 羽黑 | 妙高级 | 10×203mm | MO 机动部队（高木旗舰=妙高） |
| 青叶 / 衣笠 / 加古 / 古鹰 | 青叶/古鹰级 | 6×203mm | MO 掩护部队（五藤旗舰=青叶） |
| 鹿岛 Kashima | 香取级 | 4×140mm | 梶冈/井上旗舰位 |

## 驱逐舰与辅助舰（P1）

- 盟军：Sims/Walke/Morris/Anderson/Hammann/Russell（Sims 级，4×127+12.7mm）；
  Perkins（Mahan 级）；Farragut/Aylwin/Monaghan/Worden/Dewey（Farragut 级）；
  Phelps（Porter 级，8×127mm）；油船 Neosho（Cimarron 级）、Tippecanoe。
- 日军：阳炎级 Shiranui/Kagerō（CarDiv5 幕）；有明型 Ariake/Yugure；
  朝潮级 Ushio、特型 Sazanami（掩护部队）；睦月级×4（攻略护卫）+ Kikuzuki（图拉吉，5/4 坐底报废）；
  敷设舰 Okinoshima/Tsugaru；水上机母舰神川丸；油船东邦丸。

## 雷达与通信差异（S6 建模）

- 盟军航母装有 CXAM 级对空雷达 + 战斗定向台；巡洋舰部分装有早期对空雷达（细目 UNKNOWN）；
  驱逐舰对海搜索为主（SC 系，细目 UNKNOWN）。
- 日军全编队**无雷达**；依赖瞭望+水上侦察机+岸基中继。
