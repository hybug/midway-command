# 光栅图标源池评审报告（Phase 6 · Task 6.1）

> 评审对象：`docs/assets/icons_extracted/` 47 枚抠图产物（源：绿幕素材表 `Gemini_Generated_Icon_Green.png`，2754×1536）。
> 把关方式：**客观质量门**（`docs/assets/quality_gate.py`，5 条判据）+ **逐枚目检**（4 张拼图，纸张底色模拟使用场景）。
> 结论先行：**47 枚中仅 6 枚可直接入库、5 枚需分拆/裁剪修复、1 枚备用、35 枚为文字碎片/规格样张应弃用。**
> 更新（Task 6.2）：5 枚 repair 档已完成分拆/裁剪，6 枚新产物与原始抠图共存于 `icons_extracted/`（现共 53 枚），记录见 3.2 / 3.2.1。

## 一、汇总

| 档位 | 数量 | 说明 |
|------|------|------|
| usable（可直接入库） | 6 | ENT 之外的单枚计数牌 ×3、红问号牌 ×1、罗盘玫瑰 ×2 |
| repair（需分拆/裁剪） | 5 | 合并切割 ×2、工具条 ×1、带标注的真图形 ×2 |
| 备用（合格但暂由 SVG 顶替） | 1 | 面板框样张 |
| reject（弃用） | 35 | 素材表标题文字碎片 ×30+、规格样张 ×2、字体样张 ×2 等 |

质量门客观判定分布：PASS 9 / MANUAL 3 / FAIL 35。**门判定 ≠ 最终判定**——PASS 的 9 枚中有 2 枚目检为文字/需裁剪（`fleet_01`="图"字、`fleet_25`=地图尺含标注文字），MANUAL 的 3 枚目检全部为文字碎片。**质量门是入库的必要条件，不是充分条件；最终以目检为准。**

## 二、质量门判据（所有新增抠图入库前必须通过）

```
G1 非空     alpha 最大值 > 0
G2 内容占比 0.03 ≤ 不透明像素占比 ≤ 0.98
G3 无绿边   绿主导像素 (g>r+25 且 g>b+25) 占比 ≤ 2%
G4 主体完整 最大连通域 / 不透明面积 ≥ 0.5（碎片化检测）
G5 尺寸可用 max(w,h) ≥ 24px
MANUAL：≥2 个面积占比 >20% 的连通域 → 合并切割嫌疑，人工分拆复审
```

用法：`.venv/bin/python docs/assets/quality_gate.py <file|dir> [--markdown] [--sheets <out_dir>]`
测试守卫：`tests/test_quality_gate.py`（合成图验证 4 类判定不回退）。

## 三、存量 47 枚逐枚评审

### 3.1 usable（6 枚，可直接进 Task 6.3 入库）

| 文件 | 尺寸 | 门判定 | 目检描述 → 建议用途 |
|------|------|--------|---------------------|
| aircraft_15_105x106.png | 105x106 | PASS | **HOR 名牌**，米黄圆角方块+黑字，干净完整 → `fleet_tag_hor.png` |
| aircraft_16_122x161.png | 122x161 | PASS | **CV 名牌**（主体 0.87，微小杂点无害）→ `fleet_tag_cv.png` |
| aircraft_17_104x106.png | 104x106 | PASS | **BB 名牌** → `fleet_tag_bb.png` |
| aircraft_18_123x162.png | 123x162 | PASS | **红底白"？"方块牌**（敌情接触的方块变体，与 A5 圆形版互补）→ `enemy_tag_q.png` |
| text_style_20_220x216.png | 220x216 | PASS | **罗盘玫瑰**，N/E/S/W 齐全、双环、线条干净 → `compass_raster.png`（A6 备选） |
| text_style_21_210x233.png | 210x233 | PASS | 另一枚罗盘玫瑰（针型略异）→ 备选，与 20 择优 |

### 3.2 repair（5 枚，进 Task 6.2 分拆/裁剪后过门复检）

| 文件 | 尺寸 | 门判定 | 问题与处置 | 修复结果（Task 6.2） |
|------|------|--------|-----------|---------------------|
| aircraft_14_232x161.png | 232x161 | FAIL G4(0.47) | **ENT 名牌 + 飞机顶视图被合并切割**（另含 "32x32px" 标注碎屑）。按 x≈110 分拆：左 → `fleet_tag_ent.png`，右 → `aircraft_topdown.png` | **已修复**：按中缝 x=114 分拆并裁除底部标注（见 3.2.1），两产物均 PASS，已进 6.3 入库 |
| aircraft_19_234x162.png | 234x162 | FAIL G4(0.47) | **红"？"牌 + 红"！！"牌合并**。分拆 → `enemy_tag_q2.png` / `enemy_tag_alert.png` | **已修复**：按中缝 x=117 分拆并裁除底部标注，两产物均 PASS（源池备查，暂无入库目标） |
| button_26_88x354.png | 88x354 | FAIL G4(0.42) | 竖条：**铅笔 + 圆规**两件工具。分拆后铅笔由 A15 SVG 顶替，**圆规是素材表独有道具**可作桌面新资产 | **不拆**：铅笔已由 A15 SVG 资产顶替（commit a088fce），圆规暂缓；保持合并原样，登记为弃用档 |
| fleet_24_176x355.png | 176x355 | FAIL G4(0.12) | **真·罗盘玫瑰矢量画**，顶部 40% 为玫瑰本体，下方 "Vector art, rotation axis" 标注。裁掉标注 → A6 的第二备选 | **部分修复**：裁剪出 `compass_raster_alt.png`（去标题/标注/右缘淡线），但门判定 FAIL G4(0.34)——矢量画由星体+多段刻度环+方位字母构成，主体占比天然 <0.5（目检为单一完整玫瑰，非合并切割）；作 A6 备选保留源池、**不入库**，入库主选 `compass_raster`（text_style_20，PASS） |
| fleet_25_60x354.png | 60x354 | PASS(需裁) | **竖版地图尺**（金褐色，与美术风格一致），顶部含 "MAP" 字样。裁掉文字 → A14 的实拍质感备选 | **已修复**：裁除顶部 "MAP" 文字 → `map_ruler_alt.png` PASS（A14 实拍质感备选，暂由 SVG 木尺顶替） |

#### 3.2.1 Task 6.2 分拆/裁剪记录（可重复运行）

产物与原始抠图共存于 `docs/assets/icons_extracted/`（共 53 枚 = 47 原始 + 6 新产物）。分割线由 alpha 行列分布实测（牌区中缝全空白，非目测估计）：

| 产物 | 源 | 裁剪框 (x1,y1,x2,y2) | 依据 | 门判定 |
|------|----|---------------------|------|--------|
| fleet_tag_ent.png (114x112) | aircraft_14_232x161.png | (0, 0, 114, 112) | 左牌 cols 1–102 / 右牌 cols 127–230，中缝 103–126 全空白，分割取 x=114；y2=112 裁除底部 "32x32px" 标注（rows 121–159） | PASS（主体 1.00） |
| aircraft_topdown.png (118x112) | aircraft_14_232x161.png | (114, 0, 232, 112) | 同上 | PASS（主体 1.00） |
| enemy_tag_q2.png (117x114) | aircraft_19_234x162.png | (0, 0, 117, 114) | 左牌 cols 1–105 / 右牌 cols 129–232，中缝 106–128 全空白，分割取 x=117；y2=114 裁除底部标注（rows 122–160） | PASS（主体 1.00） |
| enemy_tag_alert.png (117x114) | aircraft_19_234x162.png | (117, 0, 234, 114) | 同上 | PASS（主体 1.00） |
| compass_raster_alt.png (152x128) | fleet_24_176x355.png | (0, 28, 152, 156) | 玫瑰本体 rows 39–159 / cols 5–141；裁除标题 "COMPASS ROSE"（rows 1–24）、标注（rows 160–239，残尖始于 158 故 y2=156）、右缘淡线（cols 173–174） | FAIL G4(0.34)（多部件本性，备选保留不入库） |
| map_ruler_alt.png (60x324) | fleet_25_60x354.png | (0, 30, 60, 354) | 尺身 rows 40–352 / cols 1–47；裁除顶部 "MAP" 文字（rows 1–23） | PASS（主体 1.00） |

新产物质量门汇总：**PASS 5 / FAIL 1**（G3 绿边全量 0.000；逐枚目检拼图确认透明底完整、无绿边、无标注残留）。尝试过对 compass_raster_alt 做 3x3 形态学闭运算可使其过 G4（主体 0.884），但会把精细双环+刻度环填成粗黑环、破坏原画风格，故弃用该手段。

### 3.3 备用（1 枚）

| 文件 | 尺寸 | 门判定 | 说明 |
|------|------|--------|------|
| button_29_284x353.png | 284x353 | PASS | **UI PANELS & FRAMES 纸面板框**（折角+毛边，与 A8/A10 同族）。合格但当前由 SVG 资产顶替；若后续需要「照片级」面板可启用 |

### 3.4 reject（35 枚）

**素材表标题/标注文字被误抠为图标（30 枚）**——这是源池最大的污染源，整批弃用：

| 文件 | 内容 | 文件 | 内容 |
|------|------|------|------|
| fleet_00_52x56 | 文字「切」 | status_bar_30_104x24 | 文字 "CLICKABLE" |
| fleet_01_48x57 | 文字「图」（形状实 so 门 PASS，**目检否决**） | status_bar_31_46x24 | 文字 "SHIP" |
| fleet_02_104x58 | 文字「资产」 | status_bar_32_132x24 | 文字 "PROFILE wHI"（乱码） |
| fleet_03_212x54 | 文字 "(SPRITESHEET" | status_bar_33_25x24 | 文字 "TO" |
| fleet_04_71x45 | 文字 "EET"（SPRITESHEET 残片） | status_bar_34_49x23 | 文字 "VIEW" |
| fleet_05_170x54 | 文字 "ASSETS)" | status_bar_35_87x23 | 文字 "DETAILED" |
| fleet_06_97x38 | 文字 "FLEET" | status_bar_36_81x24 | 文字 "DAMAGE" |
| fleet_07_102x38 | 文字 "ICONS" | status_bar_37_86x23 | 文字 "REPORTS" |
| fleet_38_88x30 | 文字 "32x32px" | compass_08_116x38 | 文字 "ENEMY" |
| fleet_39_88x30 | 文字 "32x32px" | compass_09_102x38 | 文字 "ICONS" |
| fleet_40_89x30 | 文字 "48x24px" | compass_10_165x38 | 文字 "COMPASS" |
| fleet_41_88x30 | 文字 "64x64px" | compass_11_86x38 | 文字 "ROSE" |
| map_tool_12_75x38 | 文字 "MAP" | button_44_19x23 | 文字 "UI" |
| map_tool_13_108x38 | 文字 "TOOLS" | button_45_74x23 | 文字 "PANELS" |
| button_42_88x30 | 微小文字碎片（缩略不可辨） | button_46_78x23 | 文字 "FRAMES" |
| button_43_88x30 | 微小文字碎片（缩略不可辨） | text_style_23_55x50 | 文字 "ite"（Special Elite 残片） |

**规格样张（4 枚）**——不是图标，是设计参考图，保留参考价值、不入资产库：
- button_27_256x355：BUTTON STATES 样张（EXECUTE/REVISE/SELECT 的 Normal/Hover/Pressed 双配色）——**恰好印证 A8 军令纸按钮的样式设计**
- button_28_196x356：TEXT STYLES / DATA FIELDS 样张（Caveat/Special Elite 字号、输入框/开关/下拉）
- text_style_22_221x215：字体样张（Caveat / Special E / Data Field）
- （button_29 归入备用，见 3.3）

## 四、新增抠图的把关结果

用同一脚本、同一参数对绿幕表重切（`/tmp/icons_recut`）：

- 产物 47 枚，**与存量文件清单完全一致**（同参确定性输出）；
- 质量门判定与存量逐枚一致（PASS 9 / MANUAL 3 / FAIL 35）。

**结论：** ① 抠图脚本本身是确定性的，「重跑」不产生质量增益，改善只能来自 Task 6.2 的**分拆/裁剪/调参**工序；② 任何新增抠图（调参重切、手工分拆产物）入库前必须过 `quality_gate.py`（PASS，或 MANUAL 复审通过），并按本报告 3.1 的用途清单归档命名；③ 绿边指标全量 0.000，`extract_icons.py` 的绿幕溢出抑制可靠，后续分拆（纯 Pillow crop）不会引入新绿边。

## 五、对后续任务的输入

- **Task 6.2**：优先处理 3.2 的 5 枚；`aircraft_14` 的分拆建议 x=110（名牌区约占左半）；`fleet_24` 玫瑰本体约在上部 0–40% 高度；`fleet_25` 尺子本体约在下部 8%–100%。（已完成：实测中缝为 x=103–126 / x=106–128，最终分割坐标见 3.2.1）
- **Task 6.3**：`curate_icons.py` 的 TARGETS 建议在原 4 项基础上扩为：`fleet_tag_ent`（分拆）、`fleet_tag_hor`（aircraft_15）、`fleet_tag_cv`（aircraft_16）、`fleet_tag_bb`（aircraft_17）、`enemy_tag_q`（aircraft_18）、`aircraft_topdown`（分拆）、`compass_raster`（text_style_20）。（已完成，见 `docs/assets/curate_icons.py`）
- **Task 7.9**：舰队标记的 callsign → 计数牌映射可升级为 ENT/HOR/CV/BB 四牌齐备。
