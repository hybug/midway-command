/**
 * design-state.js — 设计态 fixture（成品图复现 · H1，像素比对专用）
 *
 * 内嵌固定 theater 对象与 canned state（字段与 server.py GET /state 载荷一致），
 * 页面加载渲染器三件套（svgLoader/chartRenderer/mapRenderer）+ uiController 后
 * 以本模块数据 render(state)——不经后端，离线可渲染。仅供像素比对，非游戏页面。
 *
 * 坐标口径（两条投影链，见 tests/ui/route_display.test.mjs）：
 *  - 底图层 chartRenderer：latLonToChartPx，环礁中心固定画在 (w*0.44, h*0.46)；
 *  - 实体层 mapRenderer：_worldToHex/_hexToPixel 十边形量化 + 舰队居中平移
 *    （首航母恒画在画布中心，+lat 向下、+lon 向右）。
 *  已知怪味（known wart，本轮不修）：实体层北向画在屏幕下方——known_enemy /
 *  active_scouts 的 lat/lon 为「成品图像素目标 × 实体层投影」反推值（反推算式见
 *  各条注释），lat/lon 语义与屏幕朝向相反属预期，勿用地理常识"纠正"。
 */
(function () {
  'use strict';

  // ── 固定 theater（与 theaters/midway/theater.json 设计同源的最小字段集，
  //    取值与 chartRenderer.js 的 CHART_CENTER/CHART_VIEW_NM/RING_NM 常量一致）──
  const DESIGN_THEATER = {
    id: 'midway',
    name: 'MIDWAY ATOLL SECTOR',
    center: { lat: 28.2, lon: -177.4 },   // 环礁中心（chartRenderer CHART_CENTER 同源）
    view_nm: 45,                          // D1 近景取景（CHART_VIEW_NM 同源）
    range_rings_nm: [20, 25, 40, 60],     // RING_NM 同源
    atoll_radius_nm: { x: 34, y: 25 },    // D1 近景环礁半径（chartNmToPx 输入）
  };
  window.DESIGN_THEATER = DESIGN_THEATER;

  const NM_TO_DEG_LON = 1 / (60 * Math.cos(DESIGN_THEATER.center.lat * Math.PI / 180));

  // 舰队：course 270 / 30 KTS，按成品图 ENT 环礁西 ~40nm、HOR 西 ~25nm
  //（lat/lon 由 theater 中心反推：lon = center.lon − nm × NM_TO_DEG_LON）
  const ENT_LAT = DESIGN_THEATER.center.lat;
  const ENT_LON = DESIGN_THEATER.center.lon - 40 * NM_TO_DEG_LON; // ≈ -178.156 → 实体层量化 (-4, 0)
  const HOR_LAT = DESIGN_THEATER.center.lat;
  const HOR_LON = DESIGN_THEATER.center.lon - 25 * NM_TO_DEG_LON; // ≈ -177.873 → 量化 (-3, 0)

  // 敌情 ×2：成品图环礁东北（画布目标 ≈(792,138) 与 (855,156)，即 ~x55%/y22% 邻域）
  // 反推：canvas = hexPx + (ox,oy)，ox/oy 为舰队居中平移（ENT@画布中心）——
  //   (792,138) → hex (8,-17)  → lat 25.37 / lon -175.89
  //   (855,156) → hex (9,-13)  → lat 26.03 / lon -175.70
  const KNOWN_ENEMY = [
    {
      description: '敌航母约 4 艘 - 方位 55° - 距离 150nm',
      confidence: 'high',
      source: 'SCOUT-2',
      position: { lat: 25.37, lon: -175.89 },
    },
    {
      description: '敌航母约 4 艘 - 战列舰 2 艘护航',
      confidence: 'high',
      source: 'TBD-1',
      position: { lat: 26.03, lon: -175.7 },
    },
  ];

  // 在途侦察 ×1：HOR 西南航线、机上 2 架。位置为成品图像素目标 (690,522)
  //（舰队标记西南方）经实体层反推 → hex (-7,4) → lat 28.87 / lon -178.72。
  // 搜索扇区 30°-90°（成品图底栏「侦察 30°-90°」读数同源字段）。
  const ACTIVE_SCOUTS = [
    {
      id: 'SCOUT-2',
      direction: 'southwest',
      heading: 225,
      aircraft_count: 2,
      eta_minutes: 75,
      status: 'in_flight',
      launched_at: '1942-06-04T09:15:00Z',
      search_bearing_min: 30,
      search_bearing_max: 90,
      phase: 'outbound',
      fuel_pct: 80,
      aircraft_lost: 0,
      loss_reasons: [],
      position: { lat: 28.87, lon: -178.72 },
      search_pattern: 'sector',
    },
  ];

  // 待定建议 ×1：右栏军令纸卡（SECRET – INTERCEPTION PLAN 形态）来源；
  // details 同时驱动 _drawPendingRecon 的 NW 待定扇区（direction/sector/range）。
  const PENDING_SUGGESTIONS = [
    {
      index: 0,
      npc: 'browning',
      action_type: 'launch_scout',
      details: {
        direction: 'northwest',
        aircraft_count: 14,
        range_nm: 200,
      },
    },
  ];

  // 设计态 canned state（字段与 server.py GET /state 载荷一致）
  const DESIGN_STATE = {
    clock: { game_time: '1942-06-04T09:45:00Z' },   // 成品图 09:45 Z
    game_phase: 'playing',
    task_forces: [
      {
        name: 'Task Force 16',
        course: 270,
        speed: 30,
        carriers: [
          {
            name: 'USS Enterprise (CV-6)',
            position: { lat: ENT_LAT, lon: ENT_LON },
            course: 270,
            speed: 30,
            cap_strength: 6,                           // 成品图 巡逻 6 CAP
            damage_level: 1,                           // 损伤 minor（LGT → 橙红警示）
            air_groups: [
              { type: 'dive', count: 8, status: 'ready', fuel_pct: 100, ammo_pct: 100, squadron_name: 'VB-6' },
              { type: 'torpedo', count: 6, status: 'ready', fuel_pct: 100, ammo_pct: 100, squadron_name: 'VT-6' },
            ],                                         // 甲板合计 14（SBD/TBD）
          },
          {
            name: 'USS Hornet (CV-8)',
            position: { lat: HOR_LAT, lon: HOR_LON },
            course: 270,
            speed: 30,
            cap_strength: 0,
            damage_level: 0,
            air_groups: [],
          },
        ],
      },
    ],
    known_enemy: KNOWN_ENEMY,
    active_scouts: ACTIVE_SCOUTS,
    aircraft_losses: [],
    pending_reports: [],
    pending_suggestions: PENDING_SUGGESTIONS,
    incoming_messages: [],
    ap: { current: 14, max: 20, turn_type: 'normal', can_act: true }, // 成品图 14/20
  };
  window.DESIGN_STATE = DESIGN_STATE;

  // ── 右栏 canned 聊天：成品图 INTEL（暗卡）+ PLAYER（亮卡）双分区同屏，
  //    单 NPC 的 renderChat 不产出该组合，按 .msg 既有类结构静态拼装（样式同源）──
  function renderCannedChat() {
    const el = document.getElementById('chat-log');
    if (!el) return;
    const card = (time, sender, text, dark) => `
      <div class="msg${dark ? ' msg-classified' : ''} msg-sender-npc">
        <div class="msg-header"><span>${time}</span></div>
        <div class="msg-sender">${sender}</div>
        <div class="msg-text">${text}</div>
      </div>`;
    el.innerHTML = `
      <div class="section-header section-intel">INTEL</div>
      ${card('09:30 Z', '通信官 · TBS',
        '09:30 Z - INTEL: Urgent Report. Visual confirmation of 4 enemy carriers by TBD-1 (SCOUT-2).', true)}
      <div class="section-header section-player">PLAYER</div>
      ${card('09:32 Z', '指挥官（SPRUANCE）',
        '09:32 Z - TO ALL: Task Force 16, launch remaining SBD bombers. Priority targets: Enemy CVs. Coordinates: 30°N 178°W.', false)}
    `;
  }

  // ── 引导：图标就绪 → UI 面板 → 地图 render(state)。
  //    不启动动画循环（截图确定性；敌标脉冲 alpha 固定于初始值）──
  async function bootDesignFixture() {
    await window.loadSVGIcons();
    const ui = new window.UIController();
    ui.renderNpcTabs('browning', function () {});   // 标签静态（fixture 无切换语义）
    ui.renderDashboard(window.DESIGN_STATE);
    // 时钟定妆：renderDashboard 走 toLocaleTimeString（随机器时区漂移，截图不确定），
    // fixture 固定写 09:45 Z（state.clock.game_time 仍为 09:45Z 真值）
    const clockEl = document.getElementById('clock');
    if (clockEl) {
      clockEl.innerHTML = '09:45<span class="topbar-clock-suffix"> Z</span>';
    }
    ui.renderSuggestions(window.DESIGN_STATE, function () {}, function () {});
    renderCannedChat();
    const renderer = new window.MapRenderer('tacticalMap');
    renderer.render(window.DESIGN_STATE);
    window.__fixture = { renderer: renderer, state: window.DESIGN_STATE }; // 调试钩子
    console.log('[FIXTURE] 设计态渲染完成（像素比对专用）');
  }

  window.bootDesignFixture = bootDesignFixture;
})();
