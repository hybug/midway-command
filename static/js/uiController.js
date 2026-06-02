/**
 * 中途岛指挥官 — UI 控制器
 * Phase 4: 通信面板、军事命令文档、仪表盘、交互逻辑
 */

class UIController {
  constructor() {
    this.npcIds = ['browning', 'murray', 'mitscher', 'radio_officer', 'intel_officer'];
    this.npcLabels = {
      browning: '参谋长',
      murray: '企业号舰长',
      mitscher: '大黄蜂舰长',
      radio_officer: '通信官',
      intel_officer: '情报官',
    };
    this.npcSenders = {
      browning: '布朗宁（BROWNING）· 参谋长',
      murray: '默里（MURRAY）· 企业号舰长',
      mitscher: '米切尔（MITSCHER）· 大黄蜂舰长',
      radio_officer: '通信官 · TBS',
      intel_officer: '情报官 · 情报参谋',
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
      tab.textContent = this.npcLabels[id];
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
    const timeStr = gameTime
      ? new Date(gameTime).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
      : '04:00';

    if (!messages || messages.length === 0) {
      container.innerHTML = '<div class="chat-empty">等待指令（AWAITING ORDERS）...</div>';
      return;
    }

    let html = '';
    messages.forEach((msg, i) => {
      const isPlayer = msg.role === 'user';
      const sender = isPlayer ? '指挥官（SPRUANCE）' : this.npcSenders[activeNpc];
      const borderClass = isPlayer ? '' : ' msg-sender-npc';
      const safeText = msg.content.replace(/</g, '&lt;').replace(/\n/g, '<br>');
      html += `<div class="msg${borderClass}">
        <div class="msg-header">
          <span>#${String(i + 1).padStart(3, '0')}</span>
          <span>${timeStr}</span>
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
    const msgCount = container.querySelectorAll('.msg').length;
    const isPlayer = role === 'user';
    const sender = isPlayer ? '指挥官（SPRUANCE）' : this.npcSenders[activeNpc];
    const borderClass = isPlayer ? '' : ' msg-sender-npc';
    const safeText = content.replace(/</g, '&lt;').replace(/\n/g, '<br>');

    const div = document.createElement('div');
    div.className = `msg${borderClass}`;
    div.innerHTML = `
      <div class="msg-header">
        <span>#${String(msgCount + 1).padStart(3, '0')}</span>
        <span>${timeStr}</span>
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
      clockEl.textContent = new Date(state.clock.game_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
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

    let html = '';
    state.pending_suggestions.forEach(sug => {
      const detailStr = Object.entries(sug.details).map(([k, v]) => `${k}=${v}`).join(', ');
      html += this._renderMilitaryOrder(sug, detailStr);
    });
    container.innerHTML = html;

    // Bind buttons
    container.querySelectorAll('.btn-approve').forEach(btn => {
      btn.addEventListener('click', () => onApprove(parseInt(btn.dataset.idx)));
    });
    container.querySelectorAll('.btn-reject').forEach(btn => {
      btn.addEventListener('click', () => onReject(parseInt(btn.dataset.idx)));
    });
  }

  _renderMilitaryOrder(sug, detailStr) {
    const timeStr = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
    return `
    <div class="mil-order">
      <div class="mil-order-header">
        <span class="mil-order-title">美 国 海 军 · 作 战 命 令</span>
        <span class="mil-order-class">机密 · SECRET</span>
      </div>
      <div class="mil-order-meta">
        <span>编号: TF16-${sug.action_type.toUpperCase()}-${timeStr.replace(':', '')}</span>
        <span>04 JUN 1942 · ${timeStr} (Z+12)</span>
      </div>
      <div class="mil-order-body">
        <div class="mil-order-sign">
          <div><span class="mil-label">签发</span><br><span class="mil-val">${sug.npc}</span></div>
          <div><span class="mil-label">呈报</span><br><span class="mil-val">指挥官 R.A. Spruance</span></div>
        </div>
        <div class="mil-order-section">
          <div class="mil-section-title">1. 任务 MISSION</div>
          <div class="mil-section-body">${sug.npc} 建议执行: ${sug.action_type}</div>
        </div>
        <div class="mil-order-section">
          <div class="mil-section-title">2. 执行 EXECUTION</div>
          <div class="mil-section-body mil-detail">${detailStr}</div>
        </div>
      </div>
      <div class="mil-order-footer">
        <div class="mil-signature">
          <div class="mil-label">指挥官签署</div>
          <div class="mil-sig-line"></div>
          <div class="mil-label">R.A. Spruance, 少将</div>
        </div>
        <div class="mil-order-actions">
          <button class="btn btn-approve" data-idx="${sug.index}">批准执行</button>
          <button class="btn btn-reject" data-idx="${sug.index}">驳回修改</button>
        </div>
      </div>
    </div>`;
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
