# Coral Sea Theater Pack（珊瑚海战区包）

1942-05-04~08 珊瑚海海战（Battle of the Coral Sea）战区包，按 `docs/design/CHART_SYSTEM.md`
§六 agent 五步工作流（RESEARCH → GENERATE → VALIDATE → PREVIEW → COMMIT）由 theater-designer
agent 生成；结构同构于黄金样板 `theaters/midway/`。

## 数据来源（§六 标准 3）

- **AI 生成（agent 地理/战史知识手写，无第三方数据管线）**：geography.geojson 全部要素为
  agent 按 1942 海图精度立场（0.1°-0.3° 低多边形、单要素 8-30 顶点）手绘；scenario/theater
  兵力与配置按战史知识 + web 检索核对。
- **RESEARCH 检索引文（事实核对用）**：
  - [Battle of the Coral Sea — Wikipedia](https://en.wikipedia.org/wiki/Battle_of_the_Coral_Sea)：战役全程 4-8 May 1942、双方编成、MO 作战因祥凤战沉而推迟莫尔兹比港登陆；
  - [Task Force 17 — Coral Sea（HyperWar/ibiblio，TF17 官方行动报告）](https://www.ibiblio.org/hyperwar/USN/rep/Coral/TF17.html)："TF17 at daylight May 4 in latitude 15-00 S."、约克城航空队 pilot 数（VF 27 / VSB 27 / VT 12）、Shoho 六弹命中；
  - [USS Yorktown Action Report, Tulagi/Coral（HyperWar）](https://www.ibiblio.org/hyperwar/USN/ships/logs/CV/cv5-Coral.html)：5 月 4 日图拉吉空袭（SBD/TBD 自约克城起飞）；
  - [NHHC — Events of 7 May 1942](https://www.history.navy.mil/our-collections/photography/wars-and-events/world-war-ii/battle-of-the-coral-sea/battle-of-the-coral-sea--events-of-7-may-1942.html)：约克城侦察机发现祥凤掩护群（轻型航母+4 重巡）；
  - [Australian War Memorial — Battle of the Coral Sea](https://www.awm.gov.au/articles/encyclopedia/coral_sea/doc)：5 月 7 日 6:45 Fletcher 分离 Crace 支援群（改称 TF44）封锁乔马德水道；
  - [Raids on Deboyne (1942) — Wikipedia](https://en.wikipedia.org/wiki/Raids_on_Deboyne_(1942))：日军以 Kamikawa Maru 在德布瓦讷设水上机前进基地（5 月 4-11 日），7 日侦察误判尼欧肖号；
  - [Jomard Channel — Wikipedia](https://en.wikipedia.org/wiki/Jomard_Channel)：乔马德水道 = 路易西亚德群岛与新几内亚之间的通航咽喉（Solomon Sea ↔ Coral Sea）；
  - [Anzac Portal (DVA) — Australians and the Battle of the Coral Sea 1942](https://anzacportal.dva.gov.au/wars-and-missions/ww2/where/swpa/png/coral-sea-1942)：图拉吉 5 月 3-4 日陷落、日方水上侦察 5 月 6 日起自图拉吉出动。
- scenario 兵力口径：TF17（Fletcher，旗舰约克城 CV-5）+ TF11（Fitch，列克星敦 CV-2）已合兵
  （史实 5 月 5 日会合加油）；航空队 VF-5/VB-5+VS-5/VT-5（25/37/12）与 VF-2/VB-2+VS-2/VT-2
  （22/36/12）按行动报告 pilot 数与常见舰载机编制折算；日军 MO 机动部队（高木武雄/原忠一，
  翔鹤+瑞鹤）5 月 7 日黎明在所罗门群岛间海域西进重新入场，双方处于互相搜索状态。
- 关键点真坐标（≤0.3° 容差自检）：莫尔兹比港 9.44S/147.18E、图拉吉 9.1S/160.15E、
  努美阿 22.27S/166.44E、布因 6.75S/155.45E、德布瓦讷 10.93S/151.55E、
  东角（East Cape）10.68S/150.85E、乔马德水道 ~11.2S/152.4E。
  地理订正（评审修复轮 1）：瓜达尔卡纳尔东端（Marau Sound）截到 160.9°E（原 161.5°E 超差）、
  岛宽收敛至 0.95° 纬度；大堡礁外缘礁段西移至 145.35-146.0°E 带（Ribbon Reef 5=145.78°E）。

## 许可证

无第三方素材——全部要素为 AI 生成（agent 知识手绘）；检索引文仅用于史实核对，
不复制受版权保护的表达。无外部许可证义务。

## 生成方式

```bash
.venv/bin/python tools/validate_theater.py theaters/coral-sea   # 校验（硬校验 FAIL / 软校验 WARN）
```

五步记录见 `.superpowers/sdd/product-replica-plan/task-O.2-report.md`；
预览图 `docs/reports/product-compare/coral-sea-preview.png`。

## 备注（与任务书/中途岛样板的有意偏差）

- **view_nm 800（任务书草拟 220）**：校验器硬性要求全部 bases 落在视野圆内，而史实基地距
  取景中心（-15.2, 155.5，列克星敦战沉点）343-762nm——220nm 内无任何史实基地与岛屿，且
  §六 标准 1 要求基地真坐标（不许占位偏移）。取 800nm 后史实地理（新几内亚东段—所罗门链—
  路易西亚德—新喀里多尼亚—新赫布里底）与全部基地入画，环距 100/200/300 嵌套成立。
  中心坐标、环距、时区（UTC+10）、网格步进（1.0/5.0）出处：CHART_SYSTEM §三 schema 示例 +
  自选 05-07 开局（非任务书指定值）。
- 时钟：clock_start 1942-05-06T21:00Z = 当地（UTC+10）5 月 7 日 07:00 黎明（5 月 7 日主力
  交锋日开局）；date 字段按任务书为 1942-05-07。
- bases 类型口径：图拉吉=日占水上机基地（Gavutu，capacity 24）、布因=日占基地（Shortland/
  Ballale 一带，capacity 18）、德布瓦讷=日军前进水上机基地（capacity 12）均按 airfield 计；
  努美阿/莫尔兹比港为盟军港口（port，无 capacity，同 §三 schema 示例）。
- route_hint 两条为史实航线参考：`route_mo_approach`（日军绕所罗门群岛东端西进→乔马德
  水道方向）、`route_tf17_approach`（TF17 自努美阿西北进场）。
- 祥凤号（Shoho，轻型航母）属莫尔兹比港掩护群而非高木机动部队本队，scenario 的
  enemy_fleet（单对象 schema）取翔鹤/瑞鹤本队，祥凤经 event_seeds 表达。
