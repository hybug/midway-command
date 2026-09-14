# O.4 珊瑚海收敛轮 1 — 设计师评价（2026-09-12）

> 评审人：游戏 UI 设计审查 agent（资深二战军事题材游戏 UI 设计师，独立只评审）
> 输入：珊瑚海游戏页实拍 / midway fixture 回归对照 / 修复报告 / 真实珊瑚海地理（战史知识+WebSearch 复核）

## ACCEPTANCE
- **FIX-A FLEET_SHORT 战区解耦 — ACCEPT**：`src/routes.py:54-100` 函数化映射（midway: TF16/TF17；coral-sea: TF17/TF11/TF44/MO）+ 精确→前缀→12 字符回退；跨包同名风险已声明登记。测试实证：珊瑚海短名 7 passed（含 TF16 在 coral-sea 白名单被拒且错误信息列出可用名册）；珊瑚海实拍页顶栏 TASK FORCE 17、YOR/LEX 双标上图，侧证名册走通。
- **FIX-B CSE 标签圈左定锚 — ACCEPT**：`textAlign=right` 锚 (tf.x-16, tf.y+4)，尾缘距 r=10 圈缘 6px≥4px；4× 放大实拍 `CSE 270°` 尾字符「0°」完整可读、圈压消除；珊瑚海页 YOR/LEX 同样不再压圈。route_display 右对齐守卫 PASS。

## CORALSEA-REVIEW（以图上坐标行 15°12'S 155°30'E 标定原点，≈0.57px/nm）
- **所罗门群岛链 — 对齐**：链体自 NW（布干维尔位）向 SE 斜贯至瓜达尔卡纳尔，带东南两小岛（圣克里斯托巴尔位），走向与真实 6°S→10°S / 155°E→160°E 双排链一致；瓜岛图位偏差 <1°。
- **新几内亚东端 — 对齐**：陆块向 SE 收细尾，尾端与东角(10.7°S 150.5°E)推算位偏差 <1°（图示容差）。
- **路易西亚德群岛 — 对齐**：小岛群位于新几内亚尾端 SE 外海，与真实 10-12°S 152-154°E（含 Jomard 通道——祥凤沉没海域）相对位置正确，与 5/7「MO 攻打队经 Jomard」叙事自洽。
- **新几内亚-所罗门间岛点 — 对齐**：瓜岛南侧两小岛与右中孤岛，量级/走向可信（图例级简化）。
- **新喀里多尼亚 — 对齐**：右下 NW-SE 长条岛，图位与推算位几乎重合，珊瑚海南缘标志物。
- **GBR 外缘/澳洲东北岸 — 偏差（C）**：取景西界未见昆士兰海岸与大堡礁外缘虚线，珊瑚海西界「开敞」。改法：左下补低对比海岸线+点状礁列，恢复「四面有界的海」空间叙事。
- **双舰队对峙态势 — 偏差（C）**：YOR/LEX 同位叠画（史实 5/7 已归 Fletcher 统一指挥、间隔数海里，同位可接受），但双圈+双 CSE 315° 同锚互叠成乱字。改法：同位/近距(<36px)时 CSE 锚 y 按舰序错行。
- **战区尺度感 — 偏差（C）**：右下比例尺 0-10-25-50nm（4.1px/nm）与环距/地理层（~0.6px/nm）差 ~6.6×——midway 装饰道具原样带穿。改法：珊瑚海重标比例尺（如 0-100-300nm）。
- **史实叙事 — 对齐**：`07 MAY 1942 · Z+10`、21:00Z≈当地 5/8 晨（恰在 5/8 航母对攻前夜）；玩家位与 TF17 战报 7 日航迹吻合；甲板 74/74 ≈约克城联队 ~75 架；敌情按 known_enemy 过滤不漏 god-view——机制不对称保持。偏差（B）：右侧页签仍静态 `TF16 CAPT / HOR CAPT`，珊瑚海战区页签未战区化（后续轮立项）。

## DESIGN-SCORE-CORALSEA（首评，满分 10）
- 地理保真 8.0（链/岛/礁相对位置全部落点，缺 GBR 西界）
- 史实叙事 7.0（日期/坐标/甲板数可信；对峙态势不可见、页签未战区化）
- 构图 7.0（环心焦点+四角陆块框景符合 mockup 语法；焦点处双标叠字减分）
- 信息可读性 6.0（双 CSE 315° 互叠、比例尺失真；环距标注/坐标行清晰）
- 工艺一致性 8.5（纸纹/晕影/道具/字/缓存号纪律与 midway 完全同源）
- **总分 7.3 / 10**

## REGRESSION（loop-5-fixture-1440 对照抽查）
罗盘玫瑰形制一致 ✓；页签行一致 ✓；晕影与纸纹一致 ✓；道具组齐全 ✓；SECRET 印章/环礁/ENT/HOR/PENDING/INTEL/PLAYER 面板/底栏九格布局均保持 ✓；CSE 标签让位无新缺陷（仅登记 A 线穿插）✓；缓存号 1780998018 ×7 在 index.html ✓；全量 `pytest tests/` **352 passed, 0 failed**；geo_render.test.mjs → GEO-RENDER PASS ✓。无回归。

## VERDICT
**O.4-CLOSED**（FIX-A/FIX-B 均 ACCEPT，珊瑚海图无 D-S 级问题）。登记项移交下轮（均 C/B 级）：① 同位双舰 CSE 标签错行；② GBR/澳洲海岸补图；③ 比例尺战区化；④ 页签 NPC 头衔战区化（B）；⑤ 东侧 MO「?」疑标种子；⑥ 登记A 航向线穿字微调 / 登记B ENT 左缘出画翻转锚。

## 资料来源
- [Battle of the Coral Sea – Wikipedia](https://en.wikipedia.org/wiki/Battle_of_the_Coral_Sea)
- [NHHC – Battle of the Coral Sea, Events of 7 May 1942](https://www.history.navy.mil/our-collections/photography/wars-and-events/world-war-ii/battle-of-the-coral-sea/battle-of-the-coral-sea--events-of-7-may-1942.html)
- [TF17 Coral Sea Report (HyperWar)](https://www.ibiblio.org/hyperwar/USN/rep/Coral/TF17.html)
- [Anzac Portal – Battle of the Coral Sea 1942](https://anzacportal.dva.gov.au/wars-and-missions/ww2/where/swpa/png/coral-sea-1942)
