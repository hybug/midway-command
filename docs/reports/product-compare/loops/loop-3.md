# Loop 3 实施记录（2026-09-13，基准=成品图 u1fak0）

## 实拍
- before：loop-3-fixture-1440.png（Loop2 终态：HOR 锚点圈钉画布中心压标注群）
- after：loop-3-after-fixture-1440.png（设计态 09:45Z）· loop-3-after-empty-1440.png（空态 13:00Z，与 Loop2 空态同 server 状态基线）
- 对照基准：docs/assets/Gemini_Generated_Image_u1fak0u1fak0u1fa.png

## L2 已知项（Loop2 残留带入）

| # | 条目 | 来源 |
|---|------|------|
| 1 | HOR 锚点圈在环礁中心东侧（成品图在环礁西缘）——根因=实体层「首航母钉画布中心」wart，非数据可解 | Loop2 L5 残留 |
| 2 | 空态双舰标拥挤（wart 表现面：两航母同位挤画布中心） | Loop2 L5.5 NEW-ISSUES ② |
| 3 | southwest 方向词落点与扇区楔形疑对角 | Loop2 L5.5 NEW-ISSUES ① |
| 4 | 甲板读数企/蜂展示序对调（蜂 0/0·0 企 14/14·0） | Loop2 L5 残留 |
| 5 | ENT 存储经度 −181.9°（跨 ±180 反推值） | Loop2 L5 残留 |

## L4 修复清单（本轮实施）

| # | 条目 | 改法 |
|---|------|------|
| F1 | 实体层投影唯一化（拔舰队居中疣，核心） | chartRenderer 增 `makeProjector(view,w,h)` 导出（CHART_SYSTEM §四签名，v1 只消费 view.center，M.3 后由 theater.view 直供）；mapRenderer 实体层全部改 `this._project` 直接投影真实经纬，删除 `translate(ox,oy)` 舰队居中体系与 `_worldToHex/_hexToPixel/_hexToWorld` 十边形量化；ENT/HOR 让位/对角错开偏移随「同位」前提消失退役（标记=投影点本位）；drawTaskForceMarker 签名回归 `(ctx,tf,w,h)`；扇区标签外推上限 2.4×→3.4×（锚点西移后出环礁缓冲带距离变长，实算 ≈3.1×出带）；悬停命中/确认动画同步改屏幕系 |
| F2 | 空态双舰标拥挤 | 随 F1 消解：fixture 两舰队按真实位（ENT 图左外缘/HOR 环礁西缘）天然分离，无挤叠；游戏页空态见「M.4 依赖」条 |
| F3 | southwest 方向词语义核对 | 核对结论：**语义正确，不改**（见下） |
| F4 | route_display.test.mjs 回归 | 全部 translate 换算期望改直接投影期望；公式副本由 hex 系（worldToHex/hexToPixel 抄录）换为唯一投影公式（chartNmToPx+makeProjector 抄录）；C3「translate 守卫」改写为「防回潮守卫」（渲染帧中不得出现等于 画心−投影点 的 translate）；新增 makeProjector==latLonToChartPx 逐像素一致断言 |
| F5 | 缓存号收口 | 1780998008→1780998009（index.html 全部 ?v= + svgLoader paper_tex 同步 + test_ui_assets 断言/历史注释登记），并入 F1 提交 |

## F3 核对结论（不改依据）

- 扇区楔形/方向词/剪影航向的屏幕角均为 `bearing−90°`（canvas y 向下标准角）：bearing 270°(西)→180°→屏幕向左 ✓、0°(北)→−90°→向上 ✓、90°(东)→0°→向右 ✓。**方向语义无 y 翻转错位**。
- 「southwest 标签在东北」的观感对角源于**基准图数据自相反**：fixture 的 `direction/heading`（southwest/225，成品图字面）与 `search_bearing_min/max`（30°-90°，成品图底栏「侦察 30°-90°」读数字面）本就互斥，成品图自身即此搭配（底栏读 30°-90°、图面标签 southwest 落环礁东北）。二者均按字面保真，渲染层各画各的语义，无误。
- 旧体系真正有翻转的是**位置投影**（lat→+y 向下），F1 已随投影唯一化消除——现在实体北向上、东向右，与底图同系。

## L5 实施结果（2026-09-13）

| # | 状态 | 实施 | 证据/备注 |
|---|------|------|----------|
| F1 | ✅ | chartRenderer：`makeProjector` 导出 + latLonToChartPx 委托同式；mapRenderer：render 构造 `this._project`（view.center=REF_LAT/REF_LON，与 CHART_CENTER 同源），实体层（扇区/待定建议/侦察机/方向词/舰队/敌标/确认动画）全部直投影，ox/oy 与 hex 体系删除 | 两参考系已知局限关闭（CHART_SYSTEM §四 C3 落地，M.4 前置） |
| F1 数据面 | ✅ | design-state.js 全量改真实经纬（北向上东向右，无反推）：ENT lat 28.246/lon −178.383→画布 (47,302)=图左外缘；HOR lat 28.246/lon −178.002→(239,302)=环礁西缘；敌标内 28.468/−177.156（方位 56°/23.8nm 礁环内缘）、外 28.612/−177.216（37°/27.5nm 礁环外缘）——Loop1-F2 定位口径换唯一投影反推；侦察机 28.005/−177.702→(390,440)（首版 (347,387) 压 SAND ISLAND 胶囊，截图自查后调位） | after-fixture：ENT 左外缘/HOR 西缘/双红圈东北/中心干净 全项在位 |
| F2 | ✅ | fixture 双舰标分离目检通过（ENT↔HOR 间距 ≈192px）；**M.4 依赖登记**：游戏页空态舰队按真位（31.5°N/176°W）在 45nm 近景画外不显示——初始位 scenario 化（西移画内）仍是 M.4 范围，本轮不越界 | after-empty：中心无假象舰标（Loop2 拥挤问题不复存在），待 M.4 后舰标回画内 |
| F3 | ✅（不改） | 核对结论见上节 | — |
| F4 | ✅ | route_display 重写：CSE/标记/剪影/敌标锚点期望全部=直接投影（无 toCanvas 补偿、无 F2 偏移）；translate 回潮守卫 + makeProjector 一致性断言新增；hex 公式副本删除 | ROUTE-DISPLAY PASS |
| F5 | ✅ | 缓存号 1780998009 全链同步 | test_index_html_cache_version_consistent PASS |

**test_ui_assets.py pin 同步**：`drawTaskForceMarker(ctx, tf, w, h, ox = 0, oy = 0)` 签名 pin、`atollCenter - ox` 换算 pin、mapRenderer 调用点 ox/oy pin → 改为「签名回归 (ctx,tf,w,h) + makeProjector 接线 + 无 `ctx.translate(ox, oy)` 残留」防回潮 pin；F2 对角错开 pin（`px - 14 : px + 14`）→ 退役守卫（不得再出现）。

**验证**：node --check 六 JS 通过；`node tests/ui/route_display.test.mjs` PASS；全量 pytest **285 passed / 0 failed**。
**截图自查（Read）**：loop-3-after-fixture——ENT 圈画布 (47,302) 图左外缘、CSE 270°+双虚线矢量指向环礁（成品图同形态）；HOR 圈环礁西缘 (239,302) 同排；双红圈东北内外错开、让出罗盘；环礁中心仅剩 MIDWAY ATOLL+坐标行（Loop2 中心四层群 → 干净）；southwest 纸衬标签东北开阔水面 (684,45)、不压敌标/罗盘；SCOUT-2 剪影 (390,440) 环礁西南泻湖、避让 SAND ISLAND 胶囊（首版压胶囊已调位）；底栏读数「28.2°N 178.0°W / 企业:LGT 大黄蜂:OK / 蜂 0/0·0 企 14/14·0 / 6 / 1 西南 ETA:45分 / 4 CV」全保持。loop-3-after-empty——与 Loop2 空态同基线（13:00Z/3AP），中心无假象舰标。
**目检对比成品图**：ENT 左外缘✓ HOR 西缘✓（两圈+CSE+东指矢量与成品图同构）双红圈东北✓ 中心干净✓ —— L2-A1/A2 主差距闭合。

**M.4 范围确认（grep 实证）**：`src/initial_state.py` 仍写死 `tf16_position = (31.5, -176.0)`（NE 200nm）且双航母同位——initial_state scenario 化**未在 Loop 2 前完成，M.4 保留该范围**；本轮仅落地 M.4 的「实体层投影唯一化」半区（让位 hack 删除、两参考系关闭均按 M.4 任务书口径），scenario 布兵与「grep 31.5N 旧引用更新」留给 M.4。

## 残留（Loop 4 / M.4 候选）
- 游戏页空态舰队画外（31.5°N 在 45nm 近景外）——M.4 scenario 化后回画内（计划原文「近景下 ENT/HOR 按新初始位天然在画内」）；
- 甲板读数企/蜂展示序对调残留（carriers[0]=扇区/底栏首读槽位仍按 Loop2 安排为 Hornet，数据换位会牵动扇区楔形锚位，维持现状登记）；
- PENDING 金色待定扇区随锚点西移大部出画左缘（数据驱动几何，alpha 0.12 观感轻微）；
- main.js `triggerConfirmAnimation(centerX, centerY)` 仍发画心（确认动画位置语义待接悬停命中点，本轮文件白名单外未动）。

## 提交
- 599bff0（F1+F4+缓存号 1780998009，未 push）/ 2d1a149（本存档）
