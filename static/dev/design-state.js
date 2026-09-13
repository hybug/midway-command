/**
 * design-state.js — 设计态 fixture（成品图复现 · H1，像素比对专用）
 *
 * 内嵌固定 theater 对象与 canned state（字段与 server.py GET /state 载荷一致），
 * 页面加载渲染器三件套（svgLoader/chartRenderer/mapRenderer）+ uiController 后
 * 以本模块数据 render(state)——不经后端，离线可渲染。仅供像素比对，非游戏页面。
 *
 * 坐标口径（M.4 实体层与底图全量同锚后为唯一参考系）：
 *  - 底图与实体层共用同一投影（ChartRenderer.makeProjector 消费 theater.view 全量、
 *    含 atoll_screen_frac 构图锚，等距圆柱 + cos(lat)），lat/lon 即真实地理语义：
 *    北向上、东向右，无翻转、无反推；实体位可直接按「对环礁心真坐标的 nm」给出。
 *  - 环礁/距离环绘制基准 (28.2,-177.4)→(w*0.44, h*0.46)（构图位）；经纬网仍为装饰性
 *    0.5/0.5 锚（与构图位差 (−65,−26)px，随底图 GeoJSON 化任务统一，与本 fixture 无关）。
 *    （下述 fleet/enemy 的 nm 距离均对环礁心真坐标；画布尺寸变化时偏差 <3px，截图定妆可行）
 */
(function () {
  'use strict';

  // ── 固定 theater（M.3 起与 theaters/midway/theater.json 逐字段同值——
  //    含 atoll_screen_frac 构图位（R-M2）/graticule extent/环礁公式参数/图面标注；
  //    bootDesignFixture 经 ChartRenderer.setTheater 注入，fixture 渲染走战区包数据通道）──
  const DESIGN_THEATER = {
    id: 'midway',
    name: '中途岛',
    name_en: 'Midway',
    date: '1942-06-04',
    timezone_offset: 12,
    view: {
      center: { lat: 28.2, lon: -177.4 },     // 环礁中心（=range_rings.origin 真坐标）
      view_nm: 45,                            // D1 近景取景
      rotation: 0,
      atoll_screen_frac: { x: 0.44, y: 0.46 }, // R-M2：环礁构图位（成品图量取）
    },
    graticule: {
      minor_step: 0.25,
      major_step: 0.5,
      label_format: 'dms',
      extent: { lat_min: 26.0, lat_max: 30.0, lon_min: -183.0, lon_max: -172.0 },
    },
    range_rings: { origin: { lat: 28.2, lon: -177.4 }, rings_nm: [20, 25, 40, 60], labels: true },
    atoll: {
      radius_nm: { x: 34, y: 25 },
      rim: { x: 0.94, y: 0.90 },
      lagoon: { x: 0.80, y: 0.74 },
    },
    labels: {
      atoll: 'MIDWAY ATOLL',
      atoll_coords: "28°12'N 177°21'W",
      sand_island: 'SAND ISLAND',
      eastern_island: 'EASTERN ISLAND',
    },
    units: 'nm',
  };
  window.DESIGN_THEATER = DESIGN_THEATER;

  const NM_TO_DEG_LON = 1 / (60 * Math.cos(DESIGN_THEATER.view.center.lat * Math.PI / 180));

  // 舰队：course 270 / 30 KTS。M.4 投影全量同锚 + scenario 布兵——fixture 舰位与
  // theaters/midway/scenario.json 真实位同值（对环礁心真坐标：ENT 西 45nm / HOR 西 28nm），
  // 唯一投影下自然落位成品图构图（北向上东向右，1084×657 画布，与环礁心同一条水平线）：
  //   ENT（次位）: 图左外缘开阔水面 → 画布 (48.5, 302.2)
  //   HOR（carriers[0]，扇区/底栏首读槽位）: 环礁西缘礁环带 → 画布 (210.4, 302.2)
  const HOR_LAT = 28.2;
  const HOR_LON = -177.929519;
  const ENT_LAT = 28.2;
  const ENT_LON = -178.251012;

  // 敌情 ×2：成品图环礁东北、内外错开（Loop1-F2 定位延续；M.4 按唯一投影反推真实经纬，
  // 像素位与成品图 approved 位一致）：
  //   内标 ≈ 方位 56° / 23.8nm（礁环内缘）→ lat 28.422 / lon −177.027 → 画布 (664.9, 175.4)
  //   外标 ≈ 方位 37° / 27.5nm（礁环外缘）→ lat 28.566 / lon −177.087 → 画布 (634.6, 93.1)
  // （方位/距离对环礁心；1084×657 反推，画布尺寸变化时偏差 <3px）
  const KNOWN_ENEMY = [
    {
      description: '敌航母约 4 艘 - 方位 55° - 距离 150nm',
      confidence: 'high',
      source: 'SCOUT-2',
      position: { lat: 28.422, lon: -177.027 },
    },
    {
      description: '敌航母约 4 艘 - 战列舰 2 艘护航',
      confidence: 'high',
      source: 'TBD-1',
      position: { lat: 28.566, lon: -177.087 },
    },
  ];

  // 在途侦察 ×1：HOR 西南航线、机上 2 架。位置为成品图像素目标（环礁心西南偏下
  // ≈(−87,+138)px，避让 SAND ISLAND 胶囊/跑道横带）经唯一投影反推
  // → lat 27.959 / lon −177.573 → 画布 (390, 440)。
  // 搜索扇区 30°-90°（成品图底栏「侦察 30°-90°」读数同源字段；标签/底栏读数一律
  // 由 search_bearing 派生——扇区方向词 bearingToDirection((30+90)/2)=northeast，
  // 底栏定妆「1 架 · 30°-90°」，见 bootDesignFixture 消歧钉）；direction/heading
  // 保留出航航段语义（southwest/225，成品图字面），仅驱动剪影航向，不再驱动扇区
  // 标签/底栏方向词（L5.5 F3-R 设计师验收裁定）。
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
      position: { lat: 27.959, lon: -177.573 },
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
        // 次序即绘制序/仪表序：carriers[0] = 扇区/底栏首读槽位（Loop3-F1 拔锚点 wart
        // 后不再钉画布中心，Hornet 居首沿用 Loop2-F1 安排——搜索扇区楔形随首航母位）。
        // 底栏读数按位取值（uiController：位置/损伤取 carriers[0/1]、甲板按数组序），
        // damage 1 挂首位保「企业:LGT 大黄蜂:OK」读数、巡逻 6 CAP 同槽位
        // （合计不变）；甲板合计 14（SBD/TBD），企/蜂展示序残留见 loop-3.md。
        carriers: [
          {
            name: 'USS Hornet (CV-8)',
            position: { lat: HOR_LAT, lon: HOR_LON },
            course: 270,
            speed: 30,
            cap_strength: 6,                           // 巡逻 6 CAP（成品图合计同源）
            damage_level: 1,                           // 底栏「企业:LGT」橙红警示读数位
            air_groups: [],
          },
          {
            name: 'USS Enterprise (CV-6)',
            position: { lat: ENT_LAT, lon: ENT_LON },
            course: 270,
            speed: 30,
            cap_strength: 0,
            damage_level: 0,
            air_groups: [
              { type: 'dive', count: 8, status: 'ready', fuel_pct: 100, ammo_pct: 100, squadron_name: 'VB-6' },
              { type: 'torpedo', count: 6, status: 'ready', fuel_pct: 100, ammo_pct: 100, squadron_name: 'VT-6' },
            ],                                         // 甲板合计 14（SBD/TBD）
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

  // ── 引导：图标就绪 → 战区包注入 → UI 面板 → 地图 render(state)。
  //    不启动动画循环（截图确定性；敌标脉冲 alpha 固定于初始值）──
  async function bootDesignFixture() {
    await window.loadSVGIcons();
    // M.3 数据通道：fixture 离线无 /theater，经 setTheater 注入同值战区对象——
    // chartRenderer 的取景/经纬网/距离环/环礁/标注全部消费本对象
    window.ChartRenderer.setTheater(window.DESIGN_THEATER);
    const ui = new window.UIController();
    ui.renderNpcTabs('browning', function () {});   // 标签静态（fixture 无切换语义）
    ui.renderDashboard(window.DESIGN_STATE);
    // 时钟定妆：renderDashboard 走 toLocaleTimeString（随机器时区漂移，截图不确定），
    // fixture 固定写 09:45 Z（state.clock.game_time 仍为 09:45Z 真值）
    const clockEl = document.getElementById('clock');
    if (clockEl) {
      clockEl.innerHTML = '09:45<span class="topbar-clock-suffix"> Z</span>';
    }
    // L5.5 F3-R 消歧定妆：底栏侦察槽回归成品图基准字面（搜索扇区 30°-90° 口径），
    // 不随 uiController 的 direction 文案（出航航段 southwest→「1 西南 ETA:45分」）
    // 同源混入——uiController 属本轮文件白名单外，此处按 fixture 既有时钟钉模式改写
    const scoutEl = document.getElementById('d-scout');
    if (scoutEl) {
      scoutEl.textContent = '1 架 · 30°-90°';
      scoutEl.classList.remove('dash-empty');
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
