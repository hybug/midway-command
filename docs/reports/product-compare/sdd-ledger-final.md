# SDD ledger — plan: docs/plans/product-replica-plan.md

## Preflight (2026-09-12, BASE d6a31ab)
- R0: main 直提交（既定惯例），不 push。
- R1: 目检一律无头 Chrome --timeout=12000（virtual-time-budget 会因 rAF 挂死，禁用）；实现者可自行执行截图命令；服务器 :8000 控制器管理。
- R2: 测试基线 273 passed 0 failed（每任务后全量回归，数字单调增）。
- R3: 缓存号现值 1780997997（全链含 svgLoader paper_tex 条目；每次 JS/CSS/SVG 变更递增并同步 pin+svgLoader 版本一致性断言）。
- R4: 设计审计 17 项已消化进计划（E6/E7/E8/G7 新增，G3 勘误用 enemy_marker.svg）。
- R5: D2 改 paper 目标色 (225,207,168) 时同步：normalize_texture.py/test_texture_assets.py/raster-icon-review.md 登记（冲突审计 H4）。
- R6: G5 用 button_26 分拆圆规（冲突审计 H2：raster-icon-review 该行加注「G5 启用」）；G1 落地时 raster-icon-review:119 计数牌行加注（H3）。
- R7: 文档冲突审计（docs/reports/doc-conflict-audit.md）「现在就改」7 项并入 V3 收口（README 链接+端点表/docs-README GAME_RULES/CLAUDE 230/hex 描述/TECH_ARCH+implementation-plan 存档标注）；HISTORICAL_NOTES 加注并入 M.4。
- R8: Loop Fidelity 表按成品图 15 项新映射表在 Loop1 L2 重建；L5.5 设计师验收硬门（REJECT 未清零不得关轮）。
- R9: 工时记账——每阶段完成打时间戳进台账（预算保护：S/A/D-S 清零且 <10h 则 Loop 加深）。

## Progress
P0完成: 23:38
Task P0.1: complete (92d9d95, review clean；基准升级声明+实测数字引用)
Task P0.2: complete (88f62c3, review clean；流水线确定性=产物逐字节一致)
P0: minor (deferred) x2: delta 列取整口径注释/requirements 不列 numpy-Pillow（既有模式）
BASE 批次D: 88f62c3
DA完成: 00:07
Task D1: complete (a5a3e71, review clean；几何独立复算吻合 68.9%/69.8%)
Task D2: complete (0d68b01, review clean；paper 均值偏差 0.69；H4 登记完成)
DA: minor (deferred) x3: npc-tab hover 旧纸色未压暗（EB E3 会重做标签）/token 未随 D2 调整（设计裁定：纹理承载色调）/断言守注释字面量（无 JS runner 既有局限）
BASE 批次DB: 0d68b01
DB完成: 00:23
Task D3: complete (2c28d29, review clean；#2b2118 已登记 SVG_PALETTE)
Task D4: complete (149bfa3, review clean；hatchNE 锚红测)
D4: minor (deferred): hatchNE 弱锚点（字符串存在性，沿套件 static-analysis 风格）
BASE 批次EB1: 149bfa3
EB1完成: 00:50
Task E1: complete (a5e39a2, review clean；三 token+损伤挂类+敌情两行式)
Task E2: complete (8772cc0, review clean；顺修 letterbox/透底两处真缺陷)
EB1: minor (deferred) x4: INTEL 卡深浅两说（批末目检对照成品图定夺）/敌情 BB 段需数据端扩展/注释失准/damage 色饱和度目检定
BASE 批次EB2: 8772cc0
EB2完成: 01:17
Task E3: complete (f55eabe, review clean；hover 死值披露属实)
Task E4: complete (41a3772, review clean；gear 几何独立证实)
Task E7: complete (8133ae9, review clean；红测经变异验证为真)
EB2: minor (deferred) x3: .btn:hover 基础变体实为压暗（措辞级）/npc-tab hover 2px 顶缝/rindex 切片锚（沿套件惯例）
BASE 批次EB3: 8133ae9
EB3完成: 01:37
EB3完成: 01:38
Task E6: complete (bdf9328, review clean；占位卡互斥分支+禁用双保险)
Task E8: complete (7089324, review clean；60px/320px 布局+全仓 grep 无残留)
批次E 视觉门: 通过——近景/深色 chrome/命令卡常驻对照成品图方向一致；残差：20nm 标注近景遮挡（Loop1）、东岛细节（G7 在办）、INTEL 卡深浅待实拍
EB3: minor (deferred) x3: 批内缓存时序/№btn:disabled 外溢语义/placeholder 挂点预留
BASE 批次GA: 7089324
GA完成: 01:54
Task G1: complete (84acd87, review clean；逐字落地+F2 对角错开恢复+计数牌退役)
G1: minor (deferred) x3: circle-outline 注释弱锚/CSE 叠字坐标行尾部（几何临界，Loop 微调）/清单消歧
BASE 批次GB: 84acd87
GB完成: 02:29
Task G2: complete (a0629d0, review clean；剪影 rotate+返航 alpha+回退分支)
Task G3: complete (6297c73, review clean；enemy_marker 形态勘误落地)
Task G4: complete (fa2dfe0, review clean；章 rotate -10°+字幕移除)
GB: minor (deferred) x3: chart-label 死规则待清理/route_display rotate 断言未开窗（风格不一致）/空态无机载目检以桩断言替代
预存缺陷转 GC 顺修: mapRenderer.js:991 midAngle 未定义（launch_scout 待定建议出现时 ReferenceError）
BASE 批次GC: fa2dfe0
GC完成: 02:58
Task G5: complete (46f8572, review clean；分拆像素级可复现+质量门 PASS 主体0.99)
Task G6: complete (d40c087, review clean；铅笔 rotate 几何推演独立验证 74px 恒定净距)
Task G7: complete (6149963, review clean；黄底块/跑道/停机剪影三件+红测真红)
顺修: complete (74b15b0, review clean；midAngle→midRad 根因正确)
GC: minor (deferred) x3: style.css 注释公式错误（代码值正确）/route_display 无角度断言覆盖缺口/报告勘测表述不准
BASE 批次H: 74b15b0
H完成(像素验收40.5≤45通过): 03:29
Task H1: complete (1e3663d, review clean；fixture 离线渲染+canned state 全字段)
Task H2: complete (8ea4831, review clean；独立复跑矩阵逐格一致，40.5≤45、B差-2、要素9/9)
H: minor (deferred) x3: 敌标#2 反推注释失真（数据精确）/theater.json 尚不存在（M.1 交付物，注释先行）/绝对构图偏西北 ~150-190px（残余热区口径已覆盖）
BASE Loop: 8ea4831
Loop1完成: 04:38
Loop 1: complete (7 提交；L5.5 硬门首次触发并闭合——F8 REJECT→::after 重做→ACCEPT；DESIGN 6.6→7.2 ↑)
Loop 1: minor (deferred) x3: 扇区方向标签被陆地遮挡/空态中心群拥挤/罗盘压标注（Loop 2 候选）
BASE Loop2: 93368b1
Loop2完成: 05:35
Loop 2: complete (4 提交；F1-F6 全 ACCEPT；DESIGN 7.3→7.8；舰队居中 wart 实锤撞上)
裁定: Loop 3 前置 M.4 实体层投影唯一化（拔舰队居中疣，根治 HOR 对位不可达）——从 Phase M 提前消化
BASE Loop3: 35cace9
Loop3完成: 06:42
Loop 3: complete (3 提交；F3-R REJECT→修复→ACCEPT；DESIGN 7.8→8.3 ↑+0.5；投影唯一化=M.4 前置半区落地)
Loop 3: minor (deferred) x3: CSE 标签压尾字符/PENDING 扇区出画随 M.4 复检/甲板展示序
BASE Loop4: 8c7f45b
Loop4完成(零差距): 06:48
Loop5完成(收敛确认): 06:51
Loop 4: complete (零差距轮；设计师独立判定收敛 8.3 持平)
Loop 5: complete (末轮确认；像素级零漂移硬证据；Loop 流程关闭)
BASE V: <HEAD=loop5 存档提交>
V2完成: 07:15
V1 全分支终审: APPROVE（零 C/I；1 Important=raster-icon H2/H3 加注漏网 → V2）
V2 修复波次: complete (36e2a58 + f7193e8, 复审 ALL-ADDRESSED；含冲突审计「现在就改」7 项收口)
V2: minor (deferred): V2 报告 H4 自述过时（实际已在位）
UI 复现段（P0→V）正式闭环。进入海图系统 Phase M。
BASE PhaseM: f7193e8
M.1完成: 07:42
Task M.1: complete (22c0d91, review clean；生成器与渲染公式逐系数同源+校验器负向自检真实)
M.1: minor (deferred) x5: REF_MIN_WH 漏 gap/标注锚语义/capacity 引用不实/origin_ref 悬空校验/view_nm 直径口径
裁定 R-M1: graticule.major_step 1.0→0.5（对齐渲染现值，M.3 消费前统一：theater.json+测试同步）
裁定 R-M2: view.center 需重推导使环礁中心落 (0.44w,0.46h) 构图位（数据真坐标不动，取景瞄准点偏移）——M.3 实现时解决
裁定 timezone: 沿用 ZD+12 纪法（双源先例），schema 注释说明纪法，CHART_SYSTEM 文档同步留 V3
BASE M.2: 22c0d91
M.2完成: 07:51
Task M.2: complete (7c490f8, review clean；fail-fast+原样下发+TestClient 首例)
M.2: minor (deferred) x4: import 归位/端点未含 scenario（裁定的形态）/fail-fast 无回归用例/TestClient 引入 MOONSHOT 依赖（既有耦合）
裁定 R-M1 落地点: M.3 消费 graticule 时 major_step 用 0.5（theater.json+测试同步改，视觉零变化优先）
裁定 R-M2 落地点: M.3 view.center 重推导——环礁中心 (28.2,-177.4) 须落在 (0.44w,0.46h) 构图位（view.center=该点 SE 偏移的 lat/lon，rings 原点仍=环礁中心）
BASE M.3: 7c490f8
M.3完成(待评审-排程至23:00): 21:48
Task M.3: complete (8ff4e3c，视觉零变化硬验收=逐像素 diff 4/1,296,000px 画布区0；R-M1/R-M2 落地 atoll_screen_frac；待派评审——已排程今晚 23:00 自动会话首先补派)
BASE M.4: 8ff4e3c（M.3 评审通过后生效）
排程: automation-ee3b9b47（今晚 23:00 自动继续：M.3 评审→M.4→M.5→Phase N→O）
M.3评审Approved: 23:09
Task M.3: complete (8ff4e3c, review clean；视觉零变化=独立复现 4px/1,296,000 画布区0；断言变异法证真)
M.3: Important→M.4 并入: BUILTIN_THEATER/atoll.rim+lagoon 子集无交叉断言（离线兜底可静默分叉）——M.4 派单带一致性守卫
M.3: minor (deferred) x3: loader 载荷验收只查 view（建议消费字段集齐才接受）/截图单视口/1440×900 基线图自存自比
BASE M.4: 8ff4e3c
M.4完成: 00:05
Task M.4: complete (8558618, review clean；投影唯一化=两参考系局限关闭；scenario 读文件布兵+双向守卫)
M.4: minor (deferred) x4: chartRenderer 注释指向不全/mapRenderer 0.44 字面量预存（随底图 GeoJSON 化收敛）/initial_state TF 级取 ENT 口径/提交措辞略异
BASE M.5: 8558618
M.5完成: 00:35
Task M.5: complete (docs: Phase M 视觉回归验收；PASS=最大格 38.6≤45 较 H 批 40.5 再降、要素 12/12 在位、空态与 m4 存档全图 0px diff、297 passed)
M.5: minor (deferred) x2: r2c3 右栏命令卡构图差 H 批延续留 Loop/中部格 ±6 上浮系 M.4 裁定内布兵位+跨会话纸纹噪声（非缺陷）
派评审: 未执行——全局约束「不派发子代理」与任务书「派评审」冲突，按约束优先（M.4 §五.5 同先例），请控制者派发（diff=docs/reports/product-compare/ M.5 产物）
M.5完成+PhaseM闭环: 00:15
Task M.5: complete (496372c, docs-only；区域差 38.6≤45 较 H 批再降；要素 12/12；INTEL 深卡与成品图一致定案)
Phase M: CLOSED（控制器验收通过；投影唯一化+scenario 布兵+近景构图全对齐）
M.5: minor (deferred): 环礁形态偏圆润（真实地理立场）/环标注排布差异（D-B 池）
BASE PhaseN: 496372c
N.1完成: 00:25
Task N.1: complete (e4b2021, review clean；Route 模型/四端点/四用例)
N.1: minor (deferred) x3: waypoint note 字段缺（brief 收窄）/非法状态转换 400 零用例（N.3/N.4 顺带补）/owner 命名约定（N.4 绑舰队时定：短名映射）
BASE PhaseN-NC: e4b2021
NC完成(修复轮ALL-ADDRESSED): 01:19
Task N.3: complete (d9eeee1 + fix 6fd8723, 复审 ALL-ADDRESSED；comment 多轮修订回路补实现/状态机 400 用例/Navigator TheaterContext 注入)
Task N.4: complete (9e75b3e, 并入 NC 评审；航行数学独立复算吻合)
NC: minor (deferred) x4: comment 空轮 AP 语义（同构已披露）/REVISED 可重复 approve（单用户原型接受）/FakeLLMClient 队列语义（测试内）/Waypoint note 字段缺
裁定: comment 端点为核心闭环必需（推翻此前派单裁剪）——N.5 命令卡三按钮接线 comment
BASE 批次NB: 6fd8723
NB完成: 01:47
Task N.2: complete (4f8cdec, review clean；三样式/节流/状态过滤/红测真实)
Task N.5: complete (399953d, review clean；三按钮端点逐一比对/互斥渲染/红测基线实证)
NB: minor (deferred) x4: 航点表列口径 LAT/LON vs 航向距离（文档张力）/loadState 闪现占位卡（自愈）/active 提案线铅笔 vs 文档 mission 线（文档张力登记）/PENDING 卡 220px 滚动
BASE N.6: 399953d
N.6完成(玩法闭环PASS): 02:10
Task N.6: complete (ed75060, docs-only 验收；draft→approve→15tick 89.64nm→done 端到端实证；三类线上图截图验证)
Phase N: CLOSED（N.1-N.6 全部完成；航线玩法闭环端到端贯通）
N.6: minor (deferred) x5: keepalive 无 reload 需手动重启/截图 timeout 1200 教训/done 不自动落航迹（设计裁定）/25kt=6.25nm 每 tick（任务书 12.5 误估）/wp2/wp3 出画（取景特性）
BASE PhaseO: ed75060
O.1完成: 02:36
Task O.1: complete (cf65b76, review clean；重建完整性全清单实测无串档；/theaters+/game/new 落地)
O.1: minor (deferred) x4: browning._pending_recon_plan 跨局残留登记/load_theater 500 转态/theaters 目录缺失边界/test 硬钉单包（O.2 落盘即更新）
BASE O.2: cf65b76
O.2修复轮ALL-ADDRESSED: 03:30
Task O.2: complete (c6de1be + fix 2a1bb07, 复审 ALL-ADDRESSED；瓜岛截 160.9E/GBR 西移/三 Minor 顺修)
O.2: minor (deferred) x3: 佛罗里达岛微叠压（0.01-0.02° 原有）/view_nm 半径语义钉 O.3 验收单/VF-5 数量来源分歧加注
BASE O.3: 2a1bb07
O.3完成(验收抓2真bug已修): 04:11
Task O.3: complete (2c98ac8+19e0141 修复 /game/new 换局+GeoJSON 地理层两真 bug、a8415ea 验收存档, review clean+1 Important 转下轮)
O.3 Important: FLEET_SHORT 缺珊瑚海条目（参谋提案腿新战区不可用）→ O.4 收口
O.3: minor (deferred) x5: 侦察腿未玩法化（敌情可测性分层设计）/O.3 报告路径映射/白名单外最小修复已披露/仪表只读 task_forces[0]/主信息措辞
BASE O.4: a8415ea
O.4轮2确认(珊瑚海贯通): 04:51
O.4 轮2: 确认收敛（珊瑚海游戏页全要素渲染+scenario 状态核对；登记项 C/B 级移交后续）
—— product-replica-plan.md 全部内容执行完毕（UI 复现 + 海图系统 Phase 1-3）
