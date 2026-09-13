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

  ui.renderNpcTabs(activeNpc, switchNpc);
  await loadState();
  await loadHistory(activeNpc);
  ui.renderChat(activeNpc, histories[activeNpc], gameState?.clock?.game_time);
  bindEvents();

  // O.1 开局层：默认显示，选战区开始后才隐藏（不阻塞底层游戏初始化）
  initCampaignSelect();

  // 启动动画循环
  mapRenderer.startAnimationLoop();

  window.__ui = { mapRenderer }; // 测试/调试钩子（批次 C4）

  console.log('[MAIN] 中途岛指挥官 · 初始化完成');
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
    const layer = document.getElementById('campaign-select');
    if (layer) layer.hidden = true;
    // O.1 遗留收口（O.3）：底图战区包随战役重拉——ChartEngine 换取新取景/经纬网/
    // GeoJSON 地理层并重投影（多岛战区不再沿用上一包底图）
    try {
      const t = await window.TheaterLoader.load();
      if (t && t.view) window.ChartRenderer.setTheater(t);
    } catch (e) { /* 重拉失败保持当前战区底图，不阻断开局 */ }
    ui.renderNpcTabs(activeNpc, switchNpc);
    await loadState();
    await loadHistory(activeNpc);
    ui.renderChat(activeNpc, histories[activeNpc], gameState?.clock?.game_time);
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
}

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
  const msg = ui.getInputValue();
  if (!msg) return;
  ui.clearInput();

  if (!histories[activeNpc]) histories[activeNpc] = [];
  histories[activeNpc].push({ role: 'user', content: msg });
  ui.appendMessage(activeNpc, 'user', msg, gameState?.clock?.game_time);

  ui.setInputEnabled(false);
  try {
    const data = await api('/chat', {
      method: 'POST',
      body: JSON.stringify({ npc_id: activeNpc, message: msg }),
    });
    histories[activeNpc].push({ role: 'assistant', content: data.text });
    ui.appendMessage(activeNpc, 'assistant', data.text, gameState?.clock?.game_time);
    gameState.ap = data.ap;
    ui.renderDashboard(gameState);
    await loadState();
  } catch (e) {
    histories[activeNpc].push({ role: 'assistant', content: `[错误] ${e.message}` });
    ui.appendMessage(activeNpc, 'assistant', `[错误] ${e.message}`, gameState?.clock?.game_time);
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
  const input = document.getElementById('chat-input');
  if (input) input.value = '报告当前态势。';
  sendChat();
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
  const input = document.getElementById('chat-input');
  if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });

  const sendBtn = document.getElementById('btn-send');
  if (sendBtn) sendBtn.addEventListener('click', sendChat);

  const advanceBtn = document.getElementById('btn-advance');
  if (advanceBtn) advanceBtn.addEventListener('click', advance);

  const sitrepBtn = document.getElementById('btn-sitrep');
  if (sitrepBtn) sitrepBtn.addEventListener('click', sitrep);

  window.addEventListener('resize', () => { /* 动画循环会自动处理 */ });
}

// ═══════════════════════════════════════════════════════
// Boot
// ═══════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', init);
