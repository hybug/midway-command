/**
 * 中途岛指挥官 — UI 控制器
 * Phase 4: 通信面板、军事命令文档、仪表盘、交互逻辑
 */

// NPC 标签页缩写（A9 文件夹标签样式）— 键与 /npcs 接口返回的真实 id 一致
const NPC_TAB_ABBR = {
  browning: 'COS', murray: 'TF16 CAPT', mitscher: 'HOR CAPT',
  radio_officer: 'COMM', intel_officer: 'INTEL',
};
// 接口数据缺省时回退到默认缩写映射
function tabLabel(npc) {
  if (typeof npc === 'string') npc = { id: npc };
  const key = (npc.id || npc.name || '').toString().toLowerCase();
  return NPC_TAB_ABBR[key] || (npc.name || '').slice(0, 8).toUpperCase();
}

// 机密消息判定（Phase 8d）：消息数据无密级字段，按内容关键词判定 →
// 暗色情报卡（.msg-classified）+ SECRET 印章（.msg-stamp）
const CLASSIFIED_MSG_RE = /机密|secret|密级/i;

class UIController {
  constructor() {
    this.npcIds = ['browning', 'murray', 'mitscher', 'radio_officer', 'intel_officer'];
    this.npcSenders = {
      browning: '布朗宁（BROWNING）· 参谋长',
      murray: '默里（MURRAY）· 企业号舰长',
      mitscher: '米切尔（MITSCHER）· 大黄蜂舰长',
      radio_officer: '通信官 · TBS',
      intel_officer: '情报官 · 情报参谋',
    };
    this.npcSections = {
      browning: 'PLAYER',
      murray: 'PLAYER',
      mitscher: 'PLAYER',
      radio_officer: 'INTEL',
      intel_officer: 'INTEL',
    };
  }

  // ═══════════════════════════════════════════════════════
  // NPC Tabs
  // ═══════════════════════════════════════════════════════
  renderNpcTabs(activeNpc, onSwitch) {
    const container = document.getElementById('npc-tabs');
    container.innerHTML = '';
    this.npcIds.forEach(id => {
      const tab = document.createElement('button');
      tab.className = 'npc-tab' + (id === activeNpc ? ' active' : '');
      tab.textContent = tabLabel(id);
      tab.dataset.npc = id;
      tab.addEventListener('click', () => onSwitch(id));
      container.appendChild(tab);
    });
  }

  // ═══════════════════════════════════════════════════════
  // Chat Log
  // ═══════════════════════════════════════════════════════
  renderChat(activeNpc, messages, gameTime) {
    const container = document.getElementById('chat-log');
    const section = this.npcSections[activeNpc] || 'PLAYER';
    const timeStr = gameTime
      ? new Date(gameTime).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
      : '04:00';

    let html = `<div class="section-header section-${section.toLowerCase()}">${section}</div>`;

    if (!messages || messages.length === 0) {
      html += '<div class="chat-empty">等待指令（AWAITING ORDERS）...</div>';
      container.innerHTML = html;
      return;
    }

    messages.forEach((msg, i) => {
      const isPlayer = msg.role === 'user';
      const sender = isPlayer ? '指挥官（SPRUANCE）' : this.npcSenders[activeNpc];
      const borderClass = isPlayer ? '' : ' msg-sender-npc';
      const safeText = msg.content.replace(/</g, '&lt;').replace(/\n/g, '<br>');
      const zTime = timeStr + ' Z';
      const classified = CLASSIFIED_MSG_RE.test(msg.content);
      const cardClass = (isPlayer || classified ? ' msg-classified' : '') + borderClass;
      const stamp = classified ? '<img class="msg-stamp" src="/static/assets/ui/secret_stamp.svg" alt="">' : '';
      html += `<div class="msg${cardClass}">
        ${stamp}
        <div class="msg-header">
          <span>${zTime}</span>
        </div>
        <div class="msg-sender">${sender}</div>
        <div class="msg-text">${safeText}</div>
      </div>`;
    });
    container.innerHTML = html;
    container.scrollTop = container.scrollHeight;
  }

  appendMessage(activeNpc, role, content, gameTime) {
    const container = document.getElementById('chat-log');
    const timeStr = gameTime
      ? new Date(gameTime).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
      : '04:00';
    const isPlayer = role === 'user';
    const sender = isPlayer ? '指挥官（SPRUANCE）' : this.npcSenders[activeNpc];
    const borderClass = isPlayer ? '' : ' msg-sender-npc';
    const safeText = content.replace(/</g, '&lt;').replace(/\n/g, '<br>');
    const zTime = timeStr + ' Z';
    const classified = CLASSIFIED_MSG_RE.test(content);
    const cardClass = (isPlayer || classified ? ' msg-classified' : '') + borderClass;
    const stamp = classified ? '<img class="msg-stamp" src="/static/assets/ui/secret_stamp.svg" alt="">' : '';

    const div = document.createElement('div');
    div.className = `msg${cardClass}`;
    div.innerHTML = `
      ${stamp}
      <div class="msg-header">
        <span>${zTime}</span>
      </div>
      <div class="msg-sender">${sender}</div>
      <div class="msg-text">${safeText}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  showNotification(text) {
    const container = document.getElementById('chat-log');
    const div = document.createElement('div');
    div.className = 'notification';
    div.textContent = '! ' + text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  // ═══════════════════════════════════════════════════════
  // Dashboard
  // ═══════════════════════════════════════════════════════
  renderDashboard(state) {
    if (!state) return;
    const tf = state.task_forces[0];
    const c1 = tf.carriers[0], c2 = tf.carriers[1];
    const dmgMap = { 0: 'OK', 1: 'LGT', 2: 'MOD', 3: 'HVY' };

    this._setText('d-course', tf.course + '°');
    this._setText('d-speed', tf.speed);
    this._setText('d-pos', c1.position.lat.toFixed(1) + '°N ' + Math.abs(c1.position.lon).toFixed(1) + '°W');
    this._setText('d-dmg', `企业:${dmgMap[c1.damage_level] || '?'} 大黄蜂:${dmgMap[c2.damage_level] || '?'}`);

    // Deck info
    const deckParts = tf.carriers.map(c => {
      const short = c.name.includes('Enterprise') ? '企业' : '大黄蜂';
      const total = c.air_groups.reduce((s, a) => s + a.count, 0);
      const ready = c.air_groups.filter(a => a.status === 'ready').reduce((s, a) => s + a.count, 0);
      const airborne = c.air_groups.filter(a => ['launched', 'in_flight', 'returning'].includes(a.status)).reduce((s, a) => s + a.count, 0);
      return `${short} ${total}/${ready}备/${airborne}飞`;
    });
    this._setText('d-deck', deckParts.join(' '));

    const capTotal = tf.carriers.reduce((s, c) => s + c.cap_strength, 0);
    this._setText('d-cap', capTotal);

    // Scouts
    const scouts = state.active_scouts.filter(s => s.status === 'in_flight');
    if (scouts.length > 0) {
      const s = scouts[0];
      const elapsed = (new Date(state.clock.game_time) - new Date(s.launched_at)) / 60000;
      const remaining = Math.max(0, s.eta_minutes - elapsed);
      const dirCn = { northwest: '西北', north: '正北', northeast: '东北', east: '正东', southeast: '东南', south: '正南', southwest: '西南', west: '正西' }[s.direction] || s.direction;
      this._setText('d-scout', `${scouts.length} ${dirCn} ETA:${Math.round(remaining)}分`);
    } else {
      this._setText('d-scout', '无');
    }

    // Enemy
    const enemyEl = document.getElementById('d-enemy');
    if (state.known_enemy.length > 0) {
      this._setText('d-enemy', state.known_enemy[0].description.substring(0, 15));
      if (enemyEl) enemyEl.style.color = 'var(--color-enemy-red)';
    } else {
      this._setText('d-enemy', '暂无');
      if (enemyEl) enemyEl.style.color = '';
    }

    // AP
    this._setText('ap-current', state.ap.current);
    this._setText('ap-max', state.ap.max);

    // Clock
    const clockEl = document.getElementById('clock');
    if (clockEl && state.clock) {
      const timeStr = new Date(state.clock.game_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
      clockEl.innerHTML = timeStr + '<span class="topbar-clock-suffix"> Z</span>';
    }
  }

  // ═══════════════════════════════════════════════════════
  // Suggestions (Military Orders)
  // ═══════════════════════════════════════════════════════
  renderSuggestions(state, onApprove, onReject) {
    const container = document.getElementById('suggestions');
    if (!state || state.pending_suggestions.length === 0) {
      container.innerHTML = '';
      return;
    }

    container.innerHTML = state.pending_suggestions
      .map((sug, i) => this.renderOrderNote(sug, i))
      .join('');

    // Bind buttons: data-act="approve|reject" → 原有 onApprove/onReject 回调
    // （main.js 的 approveSuggestion/rejectSuggestion 仍走 /suggestion/{i}/approve|reject）
    container.querySelectorAll('.order-actions .btn[data-act]').forEach(btn => {
      const idx = parseInt(btn.dataset.index, 10);
      if (btn.dataset.act === 'approve') btn.addEventListener('click', () => onApprove(idx));
      else if (btn.dataset.act === 'reject') btn.addEventListener('click', () => onReject(idx));
    });
  }

  // A8 军令纸卡（SECRET – INTERCEPTION PLAN）
  // 字段映射：action_type → MISSION 行；details（k=v 列表）→ EXECUTION 步骤；index → data-index
  renderOrderNote(s, i) {
    const mission = (s.action_type || '').replace(/_/g, ' ').toUpperCase();
    const steps = Object.entries(s.details || {}).map(([k, v]) => `${k}=${v}`);
    return `
    <article class="order-note" data-suggestion="${i}">
      <header class="order-note-head">
        <span class="order-stamp-word">SECRET</span>
        <span class="order-note-subtitle">– INTERCEPTION PLAN –</span>
      </header>
      <div class="order-note-body">
        <p class="order-kw">MISSION:</p>
        <p class="order-line">${mission}</p>
        <p class="order-kw">EXECUTION:</p>
        <ol class="order-steps">${steps.map((t) => `<li>${t}</li>`).join('')}</ol>
      </div>
      <footer class="order-note-foot">
        <div class="order-sig">
          <span class="order-sig-label">COMMANDER SIGNATURE:</span>
          <svg class="sig-scrawl" viewBox="0 0 100 32" width="90" height="26" aria-hidden="true">
            <path d="M4,26 C14,6 20,30 30,14 C36,6 38,22 48,16 C58,10 60,24 72,14 C80,8 86,20 96,12"
                  fill="none" stroke="#2a2218" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="order-actions">
          <button class="btn btn-execute" data-act="approve" data-index="${i}">EXECUTE ORDER</button>
          <button class="btn btn-revise" data-act="reject" data-index="${i}">REVISE PLAN</button>
        </div>
      </footer>
    </article>`;
  }

  // ═══════════════════════════════════════════════════════
  // Input state
  // ═══════════════════════════════════════════════════════
  setInputEnabled(enabled) {
    const input = document.getElementById('chat-input');
    const btn = document.getElementById('btn-send');
    if (input) input.disabled = !enabled;
    if (btn) btn.disabled = !enabled;
  }

  clearInput() {
    const input = document.getElementById('chat-input');
    if (input) input.value = '';
  }

  getInputValue() {
    const input = document.getElementById('chat-input');
    return input ? input.value.trim() : '';
  }

  // ═══════════════════════════════════════════════════════
  // Utility
  // ═══════════════════════════════════════════════════════
  _setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }
}

window.UIController = UIController;
