/**
 * 中途岛指挥官 — 主入口
 * 负责初始化、API 调用、事件编排
 * UI 渲染委托给 UIController，地图渲染委托给 MapRenderer
 */

// ═══════════════════════════════════════════════════════
// State
// ═══════════════════════════════════════════════════════
let activeNpc = 'browning';
let gameState = null;
let histories = {};
let mapRenderer = null;
let ui = null;
let intelBoard = null;
// S8 UI.1：案卷台 + 通知中心
let desk = null;
let notifications = null;
let activeSection = 'CHART';

// ═══════════════════════════════════════════════════════
// API
// ═══════════════════════════════════════════════════════
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || JSON.stringify(err));
  }
  return res.json();
}

// ═══════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════
async function init() {
  // Load SVG icons first
  await loadSVGIcons();

  mapRenderer = new MapRenderer('tacticalMap');
  ui = new UIController();

  // S2.8：敌标一键反查——点击已确认敌情 → 打开该标图链的战后复盘
  mapRenderer.onEnemyContact((index) => {
    const e = (gameState?.known_enemy || [])[index];
    if (e && e.source && e.source.startsWith('plot:')) {
      intelBoard.showPlotChain(e.source.slice(5));
    } else {
      ui.showNotification('📡 该敌情无标图链（迁移期旧数据）');
    }
  });

  // S2.8：情报板（收报室/简报/审图/复盘；UI.3 起迁入案卷台 INTEL 区）
  if (window.IntelBoard) {
    intelBoard = new IntelBoard();
    intelBoard.mount('intel-board');
  }

  // S8 UI.1：通知中心（角标/队列/FLASH·STAFF_VISIT toast）
  notifications = new NotificationCenter();
  notifications.onChange = renderShell;
  notifications.onToast = showToast;

  // S8 UI.1：Commander Desk 壳（案卷台；工作台区块由后续阶段注册）
  desk = new CommanderDesk();
  desk.mount('commander-desk');
  desk.registerSection('COMMS', { mount: el => { el.innerHTML =
    '<p class="desk-placeholder">COMMS 收报室（UI.2 迁入）——收报室摘要见右栏与电文灯</p>'; } });
  desk.registerSection('INTEL', { mount: el => { el.innerHTML =
    '<p class="desk-placeholder">INTEL 情报工作台（UI.3 迁入）——当前情报板见右栏</p>'; } });
  desk.registerSection('STAFF', { mount: el => { el.innerHTML =
    '<p class="desk-placeholder">STAFF 参谋工作台（UI.4 迁入）——当前对话见右栏</p>'; } });
  desk.registerSection('LOG', { mount: el => { el.innerHTML =
    '<p class="desk-placeholder">LOG 时间线与复盘（UI.5 迁入）</p>'; } });
  desk.onSectionChange = (section) => {
    activeSection = section || 'CHART';
    renderShell();
  };

  // 设置确认敌情回调
  mapRenderer.onConfirmContact(async (index) => {
    try {
      const data = await api(`/confirm-contact/${index}`, { method: 'POST' });
      if (data.success) {
        // 触发画圈动画
        const pending = gameState.pending_suggestions || [];
        if (index < pending.length) {
          // 计算动画位置（简化：使用屏幕中心附近）
          mapRenderer.triggerConfirmAnimation(mapRenderer.centerX, mapRenderer.centerY);
        }
        ui.showNotification('✅ 敌情已确认，更新到海图');
        await loadState();
      }
    } catch (e) {
      ui.showNotification('❌ 确认失败: ' + e.message);
    }
  });

  ui.renderWorkbenchNav(activeSection, notifications.counters, switchWorkbench);
  await loadState();
  await loadHistory(activeNpc);
  ui.renderChat(activeNpc, histories[activeNpc], gameState?.clock?.game_time);
  renderShell();
  bindEvents();

  // O.1 开局层：默认显示，选战区开始后才隐藏（不阻塞底层游戏初始化）
  initCampaignSelect();

  // 启动动画循环
  mapRenderer.startAnimationLoop();

  window.__ui = { mapRenderer }; // 测试/调试钩子（批次 C4）

  console.log('[MAIN] 中途岛指挥官 · 初始化完成');
}

// ═══════════════════════════════════════════════════════
// S8 UI.1：工作台导航与 Shell 渲染
// ═══════════════════════════════════════════════════════
function switchWorkbench(section) {
  if (section === 'CHART') {
    desk.close();                       // CHART = 关闭案卷台回海图
    activeSection = 'CHART';
  } else {
    desk.open(section, { via: 'nav' }); // 打开案卷台不推进时间
  }
  renderShell();
}

function renderShell() {
  ui.renderWorkbenchNav(activeSection, notifications.counters, switchWorkbench);
  const latest = latestActivity();
  ui.renderDutySummary({
    section: activeSection,
    notifications,
    latest,
    onOpenDesk: () => switchWorkbench(activeSection === 'CHART' ? 'COMMS' : activeSection),
    onOpenItem: (item) => {
      notifications.markRead(item.id);
      if (item.workbench === 'CHART') return;
      desk.open(item.workbench, { via: 'notification', detail: item.id });
    },
  });
  if (desk.isOpen()) desk.switchSection(desk.section); // 案卷台打开时保持区块刷新
}

function latestActivity() {
  const top = notifications.topPriority();
  if (top) return { kind: top.level, text: top.text };
  if (gameState && gameState.known_enemy && gameState.known_enemy.length) {
    return { kind: 'PLOT', text: gameState.known_enemy[0].description };
  }
  return null;
}

// FLASH / STAFF_VISIT 主动打断（toast；点击进入对应工作台并标记已读）
function showToast(item) {
  const container = document.getElementById('notification-toasts');
  if (!container) return;
  const div = document.createElement('div');
  div.className = `toast toast-${item.level.toLowerCase()}`;
  div.textContent = `! ${item.text}（点击处理）`;
  div.addEventListener('click', () => {
    notifications.markRead(item.id);
    if (item.workbench !== 'CHART') desk.open(item.workbench, { via: 'toast' });
    div.remove();
  });
  container.appendChild(div);
  setTimeout(() => div.remove(), 8000);
}

// ── 通知聚合（白名单接口；案卷台/通知均不推进时间）──
async function refreshNotifications() {
  if (typeof fetch !== 'function') return;
  try {
    const [plots, inbox, work] = await Promise.all([
      fetch('/intel/plots').then(r => r.json()).catch(() => null),
      fetch('/intel/inbox').then(r => r.json()).catch(() => null),
      fetch('/intel/work-items').then(r => r.json()).catch(() => null),
    ]);
    const visits = window.S4Adapter ? await window.S4Adapter.fetchVisitEvents() : [];
    const conflicts = window.S4Adapter ? await window.S4Adapter.fetchConflictDossiers() : [];
    notifications.refreshFromIntel(plots, inbox?.messages || [], work?.work_items || [],
                                   visits, conflicts);
  } catch (e) { /* 通知不可用不阻断主流程 */ }
}

// ═══════════════════════════════════════════════════════
// Campaign select（O.1 战役选择）
// 开局层 #campaign-select 默认显示：拉 /theaters 渲染战区卡，
// 点击开始 → POST /game/new（服务端重建 GameState + NPC 会话清空）
// → 隐藏开局层，客户端历史/状态全量重载
// ═══════════════════════════════════════════════════════
async function initCampaignSelect() {
  const layer = document.getElementById('campaign-select');
  if (!layer || layer.hidden) return;
  try {
    const data = await api('/theaters');
    ui.renderCampaignList(data.theaters, startCampaign);
  } catch (e) {
    ui.showCampaignError('战区列表加载失败: ' + e.message);
  }
}

async function startCampaign(theaterId, btn) {
  if (btn) { btn.disabled = true; btn.textContent = 'LOADING...'; }
  try {
    await api('/game/new', {
      method: 'POST',
      body: JSON.stringify({ theater_id: theaterId }),
    });
    // 服务端已重建 GameState 并清空 NPC 会话 → 客户端历史缓存作废全量重载
    histories = {};
    activeNpc = 'browning';
    activeSection = 'CHART';
    if (desk) desk.close();
    if (notifications) { notifications.items = []; notifications._seen = new Set();
      notifications.counters = { CHART: 0, COMMS: 0, INTEL: 0, STAFF: 0, LOG: 0 }; }
    const layer = document.getElementById('campaign-select');
    if (layer) layer.hidden = true;
    // O.1 遗留收口（O.3）：底图战区包随战役重拉——ChartEngine 换取新取景/经纬网/
    // GeoJSON 地理层并重投影（多岛战区不再沿用上一包底图）
    try {
      const t = await window.TheaterLoader.load();
      if (t && t.view) window.ChartRenderer.setTheater(t);
    } catch (e) { /* 重拉失败保持当前战区底图，不阻断开局 */ }
    ui.renderWorkbenchNav(activeSection, notifications.counters, switchWorkbench);
    await loadState();
    await loadHistory(activeNpc);
    ui.renderChat(activeNpc, histories[activeNpc], gameState?.clock?.game_time);
    renderShell();
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = '开始战役'; }
    ui.showCampaignError('开战失败: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════
// State loading
// ═══════════════════════════════════════════════════════
async function loadState() {
  gameState = await api('/state');
  ui.renderDashboard(gameState);
  ui.renderSuggestions(gameState, approveSuggestion, rejectSuggestion);
  if (mapRenderer) mapRenderer.render(gameState); // 首帧渲染并置 _currentState，此后动画循环接管
  if (intelBoard) intelBoard.refresh(); // S2.8：情报板随状态刷新（节流）
  renderShell();
  refreshNotifications();
}
window.__loadState = loadState;

async function loadHistory(npcId) {
  if (histories[npcId]) return;
  const data = await api(`/npc/${npcId}/history`);
  histories[npcId] = data.messages;
}

// ═══════════════════════════════════════════════════════
// NPC switching
// ═══════════════════════════════════════════════════════
async function switchNpc(npcId) {
  activeNpc = npcId;
  ui.renderNpcTabs(activeNpc, switchNpc);
  await loadHistory(npcId);
  ui.renderChat(activeNpc, histories[activeNpc], gameState?.clock?.game_time);
}

// ═══════════════════════════════════════════════════════
// Chat
// ═══════════════════════════════════════════════════════
async function sendChat() {
  // S8 UI.1：全局常驻聊天输入已移除——交谈迁入 STAFF 工作台（UI.4）；
  // 本函数保留供 STAFF 桌面复用，无输入元素时直接返回
  const msg = ui.getInputValue();
  if (!msg) return;
  return sendChatTo(activeNpc, msg);
}

// 向指定 NPC 发送对话（STAFF 工作台与 SITREP 共用；对话不构成正式命令）
async function sendChatTo(npcId, msg) {
  if (!histories[npcId]) histories[npcId] = [];
  histories[npcId].push({ role: 'user', content: msg });
  ui.appendMessage(npcId, 'user', msg, gameState?.clock?.game_time);

  ui.setInputEnabled(false);
  try {
    const data = await api('/chat', {
      method: 'POST',
      body: JSON.stringify({ npc_id: npcId, message: msg }),
    });
    histories[npcId].push({ role: 'assistant', content: data.text });
    ui.appendMessage(npcId, 'assistant', data.text, gameState?.clock?.game_time);
    gameState.ap = data.ap;
    ui.renderDashboard(gameState);
    await loadState();
  } catch (e) {
    histories[npcId].push({ role: 'assistant', content: `[错误] ${e.message}` });
    ui.appendMessage(npcId, 'assistant', `[错误] ${e.message}`, gameState?.clock?.game_time);
  } finally {
    ui.setInputEnabled(true);
  }
}

// ═══════════════════════════════════════════════════════
// Actions
// ═══════════════════════════════════════════════════════
async function advance() {
  try {
    const data = await api('/advance', { method: 'POST', body: JSON.stringify({ minutes: 15 }) });
    gameState.ap = data.ap;
    ui.renderDashboard(gameState);
    if (data.notifications && data.notifications.length > 0) {
      data.notifications.forEach(n => ui.showNotification(n));
    }
    await loadState();
  } catch (e) {
    alert('推进失败: ' + e.message);
  }
}

async function sitrep() {
  // 全局输入移除后：SITREP 直接向参谋长发问（普通交谈不构成正式命令）
  await sendChatTo('browning', '报告当前态势。');
}

async function approveSuggestion(idx) {
  try {
    const data = await api(`/suggestion/${idx}/approve`, { method: 'POST' });
    ui.showNotification(`已执行: ${data.result}`);
    await loadState();
  } catch (e) {
    alert('执行失败: ' + e.message);
  }
}

async function rejectSuggestion(idx) {
  try {
    await api(`/suggestion/${idx}/reject`, { method: 'POST' });
    await loadState();
  } catch (e) {
    alert('驳回失败: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════
// Events
// ═══════════════════════════════════════════════════════
function bindEvents() {
  // S8 UI.1：全局聊天输入已移除（交谈限 STAFF 工作台）；
  // ISSUE ORDER = 全局唯一正式命令入口
  const issueBtn = document.getElementById('btn-issue-order');
  if (issueBtn) issueBtn.addEventListener('click', () => ui.toggleIssueOrder(true));

  const ioClose = document.getElementById('io-close');
  if (ioClose) ioClose.addEventListener('click', () => ui.toggleIssueOrder(false));

  const advanceBtn = document.getElementById('btn-advance');
  if (advanceBtn) advanceBtn.addEventListener('click', advance);

  const sitrepBtn = document.getElementById('btn-sitrep');
  if (sitrepBtn) sitrepBtn.addEventListener('click', sitrep);

  // ESC：关闭案卷台 / ISSUE ORDER（M8.1.6）
  window.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const io = document.getElementById('issue-order-modal');
    if (io && !io.hidden) { ui.toggleIssueOrder(false); return; }
    if (desk && desk.isOpen()) desk.close();
  });

  window.addEventListener('resize', () => { /* 动画循环会自动处理 */ });
}

// ═══════════════════════════════════════════════════════
// Boot
// ═══════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', init);
