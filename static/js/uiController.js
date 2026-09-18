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

// S8 UI.1：五工作台一级导航（M8.1.1）——替代旧 NPC 页签的全局导航职责；
// NPC 选择下沉 STAFF 工作台（NPC_TAB_ABBR 保留供名册标签使用）
const WORKBENCHES = [
  { id: 'CHART', label: 'CHART', hint: '海图态势' },
  { id: 'COMMS', label: 'COMMS', hint: '收报室' },
  { id: 'INTEL', label: 'INTEL', hint: '情报工作台' },
  { id: 'STAFF', label: 'STAFF', hint: '参谋' },
  { id: 'LOG', label: 'LOG', hint: '记录与复盘' },
];

// 机密消息判定（Phase 8d）：消息数据无密级字段，按内容关键词判定 →
// 暗色情报卡（.msg-classified）+ SECRET 印章（.msg-stamp）
const CLASSIFIED_MSG_RE = /机密|secret|密级/i;

// HTML 转义（最小助手）：NPC 生成的文本（action_type / details 等）先转义再插值，
// 防止 <、>、"、'、& 破坏 DOM 结构（军令卡 renderOrderNote 使用）
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// 电传打字机（Phase 9.2）：逐字显示，40 字/秒；done 为可选完成回调
// （打字期间用 textContent 安全逐字显示，完成后恢复带 <br> 换行的完整 HTML）
function typewrite(el, text, cps = 40, done) {
  el.textContent = '';
  let i = 0;
  const timer = setInterval(() => {
    el.textContent = text.slice(0, ++i);
    if (i >= text.length) {
      clearInterval(timer);
      if (done) done();
    }
  }, 1000 / cps);
}

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
  // S8 UI.1 · 五工作台导航 + 值班栏（M8.1.1 / M8.7.2）
  // ═══════════════════════════════════════════════════════
  renderWorkbenchNav(activeSection, counters, onSwitch) {
    const container = document.getElementById('workbench-nav');
    if (!container) return;
    container.innerHTML = '';
    WORKBENCHES.forEach(wb => {
      const btn = document.createElement('button');
      btn.className = 'wb-tab' + (wb.id === activeSection ? ' active' : '');
      btn.dataset.workbench = wb.id;
      btn.title = wb.hint;
      const unread = (counters && counters[wb.id]) || 0;
      btn.innerHTML = `${wb.label}` +
        (unread > 0 ? `<span class="wb-badge" data-badge="${wb.id}">${unread}</span>` : '');
      btn.addEventListener('click', () => onSwitch(wb.id));
      container.appendChild(btn);
    });
  }

  // 值班栏（L1）：当前工作台/未读/最高优先级/最近判断或电报/打开案卷台
  renderDutySummary({ section, notifications, latest, onOpenDesk, onOpenItem }) {
    const container = document.getElementById('duty-summary');
    if (!container) return;
    const top = notifications ? notifications.topPriority() : null;
    const unreadTotal = notifications
      ? Object.values(notifications.counters).reduce((s, v) => s + v, 0) : 0;
    const esc = window.escapeHtml || escapeHtml;
    const topHtml = top
      ? `<button class="duty-item duty-top" data-notify-id="${esc(top.id)}">
           <span class="duty-level level-${esc(top.level.toLowerCase())}">${esc(top.level)}</span>
           ${esc(top.text)}</button>`
      : '<p class="duty-item duty-empty">无待处理事项（ALL CLEAR）</p>';
    const latestHtml = latest
      ? `<p class="duty-item duty-latest"><span class="duty-kw">${esc(latest.kind)}</span> ${esc(latest.text)}</p>`
      : '<p class="duty-item duty-latest duty-empty">暂无判断与电报</p>';
    container.innerHTML = `
      <p class="duty-kw">CURRENT SECTION</p>
      <p class="duty-section">${esc(section || 'CHART')}</p>
      <p class="duty-kw">PENDING <span class="wb-badge-inline">${unreadTotal}</span></p>
      ${topHtml}
      ${latestHtml}
      <button class="btn btn-execute duty-open-desk" id="btn-open-desk">打开案卷台</button>`;
    const openBtn = container.querySelector('#btn-open-desk');
    if (openBtn) openBtn.addEventListener('click', () => onOpenDesk());
    const topBtn = container.querySelector('.duty-top');
    if (topBtn && onOpenItem) topBtn.addEventListener('click', () => onOpenItem(top));
  }

  // ISSUE ORDER 弹层（全局唯一正式命令入口，M8.7.6）
  toggleIssueOrder(open) {
    const modal = document.getElementById('issue-order-modal');
    if (modal) modal.hidden = !open;
  }

  // ═══════════════════════════════════════════════════════
  // NPC Tabs（STAFF 工作台名册沿用；不再作为全局导航）
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
      // fix L4-F8 → Loop2-F5: 空态包 intel_card 纸卡（宽 88% 居中、chat-log 空态时垂直居中），
      // SECRET 红章移到卡片右上角（.idle-stamp 改 absolute 定位）
      html += `<div class="empty-card">
        <img src="/static/assets/ui/secret_stamp.svg" class="idle-stamp" alt="">
        <div class="chat-empty">等待指令（AWAITING ORDERS）...</div>
      </div>`;
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
      // 成品图复现 E2：INTEL 分区发信者（通信官/情报官）常驻深卡（无印章），PLAYER 卡维持现状
      const intelDark = !isPlayer && this.npcSections[activeNpc] === 'INTEL';
      const cardClass = ((isPlayer || classified || intelDark) ? ' msg-classified' : '') + borderClass;
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
    // 成品图复现 E2：INTEL 分区发信者（通信官/情报官）常驻深卡（无印章），PLAYER 卡维持现状
    const intelDark = !isPlayer && this.npcSections[activeNpc] === 'INTEL';
    const cardClass = ((isPlayer || classified || intelDark) ? ' msg-classified' : '') + borderClass;
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

    // Phase 9.2：NPC 新消息电传打字（仅 appendMessage 追加路径生效；
    // renderChat 整列表重绘路径直接赋值，历史消息不重复播放动画）
    if (role !== 'user') {
      const textEl = div.querySelector('.msg-text');
      typewrite(textEl, content, 40, () => { textEl.innerHTML = safeText; });
    }
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
    if (!tf) return;
    const c1 = tf.carriers[0];
    const dmgMap = { 0: 'OK', 1: 'LGT', 2: 'MOD', 3: 'HVY' };
    // O.3：舰名短字映射数据面化（珊瑚海约克城/列克星敦；缺省回退舰名首字）
    const shipShort = (name) => name.includes('Enterprise') ? '企'
      : name.includes('Hornet') ? '蜂'
      : name.includes('Yorktown') ? '约'
      : name.includes('Lexington') ? '列'
      : name.replace(/^USS /, '').slice(0, 1);

    this._setText('d-course', tf.course + '°');
    this._setText('d-speed', tf.speed);
    // O.3：南北/东西半球感知（珊瑚海 15.5°S 155.6°E；北半球读数不变）
    this._setText('d-pos', Math.abs(c1.position.lat).toFixed(1) + '°' + (c1.position.lat >= 0 ? 'N' : 'S')
      + ' ' + Math.abs(c1.position.lon).toFixed(1) + '°' + (c1.position.lon >= 0 ? 'E' : 'W'));
    this._setText('d-dmg', tf.carriers.map(c => `${shipShort(c.name)}:${dmgMap[c.damage_level] || '?'}`).join(' '));
    // 成品图复现 E1：任一航母损伤非 OK → .dash-val-damage 橙红警示
    const dmgEl = document.getElementById('d-dmg');
    if (dmgEl) dmgEl.classList.toggle('dash-val-damage', tf.carriers.some(c => c.damage_level > 0));

    // Deck info
    // fix L4-F9: 读数缩短为「企 80/80·0」格式（去「备/飞」字），配合 .dash-item nowrap/flex 1.6 防底栏裁切
    const deckParts = tf.carriers.map(c => {
      const short = shipShort(c.name);
      const total = c.air_groups.reduce((s, a) => s + a.count, 0);
      const ready = c.air_groups.filter(a => a.status === 'ready').reduce((s, a) => s + a.count, 0);
      const airborne = c.air_groups.filter(a => ['launched', 'in_flight', 'returning'].includes(a.status)).reduce((s, a) => s + a.count, 0);
      return `${short} ${total}/${ready}·${airborne}`;
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
    // fix Loop2-F6: 空态读数（「无/暂无」）60% 透明斜体
    this._setDashEmpty('d-scout', scouts.length === 0);

    // Enemy
    // 成品图复现 E1：敌情两行式——主行「N CV」+ 次行 (REPORTED) 小字（.dash-val small）。
    // 数据端描述为「敌航母约 N 艘 - 方位… - 距离…」（scouting.py / render/chart.py），
    // 无「/ N BB」段（known_enemy 不含战列舰数），故解析 N 后只出 CV 段；
    // 非标格式回退为截断描述。innerHTML 内容经 escapeHtml 转义防注入。
    const enemyEl = document.getElementById('d-enemy');
    if (state.known_enemy.length > 0) {
      const desc = state.known_enemy[0].description;
      const m = desc.match(/敌航母约\s*(\d+)\s*艘/);
      const mainLine = escapeHtml(m ? `${m[1]} CV` : desc.substring(0, 15));
      if (enemyEl) {
        enemyEl.innerHTML = `${mainLine}<small>(REPORTED)</small>`;
        enemyEl.style.color = 'var(--color-enemy-red)';
      }
    } else {
      this._setText('d-enemy', '暂无');
      if (enemyEl) enemyEl.style.color = '';
    }
    this._setDashEmpty('d-enemy', state.known_enemy.length === 0);

    // AP
    this._setText('ap-current', state.ap.current);
    this._setText('ap-max', state.ap.max);

    // Clock
    // O.3：Zulu 时间语义——UTC 渲染（O.1 §五.3 本地时区疣收口；中途岛 04:00Z 显示 04:00）
    const clockEl = document.getElementById('clock');
    if (clockEl && state.clock) {
      const timeStr = new Date(state.clock.game_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' });
      clockEl.innerHTML = timeStr + '<span class="topbar-clock-suffix"> Z</span>';
    }
    // O.3：顶栏日期/Z 时区/舰队题字随战区（state.theater 由 /state 下发；
    // fixture 桩态无 theater 键 → 保持静态 HTML 定妆）
    if (state.theater) {
      const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
      const local = new Date(new Date(state.clock.game_time).getTime() + state.theater.timezone_offset * 3600 * 1000);
      const dateEl = document.querySelector('.topbar-date');
      if (dateEl) {
        dateEl.textContent = String(local.getUTCDate()).padStart(2, '0') + ' ' + months[local.getUTCMonth()]
          + ' ' + local.getUTCFullYear() + ' · Z+' + state.theater.timezone_offset;
      }
      const subEl = document.querySelector('.topbar-subtitle');
      if (subEl && tf) subEl.textContent = tf.name.split('(')[0].trim().toUpperCase();
    }
  }

  // ═══════════════════════════════════════════════════════
  // Suggestions (Military Orders)
  // ═══════════════════════════════════════════════════════
  renderSuggestions(state, onApprove, onReject) {
    const container = document.getElementById('suggestions');
    const pending = state ? state.pending_suggestions : [];

    // 成品图复现 E6（A10）命令卡常驻化：空态/非空态互斥渲染——
    // 空态常驻占位军令纸（右栏底部不再留白），有建议时正常渲染命令卡
    if (pending.length === 0) {
      container.innerHTML = this.renderPlaceholderNote();
    } else {
      container.innerHTML = pending
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

    // N.5 命令卡联动：GET /pending-routes 有 proposed 航线提案时渲染 PENDING ROUTE
    // 军令纸卡（异步拉取，insertAdjacentHTML 不重建既有建议卡节点/按钮绑定）
    this.refreshPendingRoutes();
  }

  // ═══════════════════════════════════════════════════════
  // N.5 航线提案命令卡（航海参谋 PendingRoute → 军令纸）
  // 数据源 GET /pending-routes；仅 status=proposed 出卡（revised 为被修订旧条目，
  // approved/rejected 已处理）。空态（无 proposed）维持 E6 占位卡。
  // ═══════════════════════════════════════════════════════
  refreshPendingRoutes() {
    if (typeof fetch !== 'function') return;
    fetch('/pending-routes')
      .then(r => r.json())
      .then(data => {
        const proposed = ((data && data.pending_routes) || [])
          .filter(p => p.status === 'proposed');
        this.renderPendingRoutes(proposed);
      })
      .catch(() => { /* 提案接口不可用时维持现状（占位卡不受影响） */ });
  }

  renderPendingRoutes(pendings) {
    const container = document.getElementById('suggestions');
    if (!container) return;
    // 重绘航线提案卡（先移除旧卡防重复），不动建议卡/占位卡节点
    container.querySelectorAll('.order-note.route-note').forEach(el => el.remove());
    // 有提案时隐藏 E6 占位卡（非空态），空态恢复
    const ph = container.querySelector('.order-note.placeholder');
    if (ph) ph.style.display = pendings.length > 0 ? 'none' : '';
    if (pendings.length === 0) return;

    container.insertAdjacentHTML('afterbegin', pendings.map(p => this.renderPendingRouteNote(p)).join(''));

    // Bind buttons: data-route-act="approve|reject|comment"（与建议卡 data-act 区分防误绑）
    container.querySelectorAll('.route-note .btn[data-route-act]').forEach(btn => {
      const p = pendings.find(x => x.id === btn.dataset.pendingId);
      if (p) btn.addEventListener('click', () => this.onRouteAction(btn.dataset.routeAct, p));
    });
  }

  // PENDING ROUTE 军令纸卡：SECRET 头 + 「– ROUTE PROPOSAL –」副题 + rationale 正文
  // + 航点表（NO.·LAT·LON·ETA）+ 三按钮（批准实施/驳回/提修改意见）
  renderPendingRouteNote(p) {
    const owner = escapeHtml(p.owner || '');
    const rationale = escapeHtml(p.rationale || '');
    const rows = (p.waypoints || []).map((w, i) => {
      const lat = (w.lat >= 0 ? w.lat.toFixed(1) + '°N' : Math.abs(w.lat).toFixed(1) + '°S');
      const lon = (w.lon >= 0 ? w.lon.toFixed(1) + '°E' : Math.abs(w.lon).toFixed(1) + '°W');
      const eta = w.eta ? new Date(w.eta).toUTCString().slice(17, 22) + 'Z' : '—';
      return `<tr><td>${i + 1}</td><td>${lat}</td><td>${lon}</td><td>${eta}</td></tr>`;
    }).join('');
    const table = `
      <table class="route-wps" style="width:100%;border-collapse:collapse;margin:6px 0 2px;font-size:11px;color:#2a2218;">
        <thead><tr style="border-bottom:1px solid rgba(42,34,24,0.4);text-align:left;">
          <th style="padding:2px 8px 2px 0;font-weight:normal;">NO.</th>
          <th style="padding:2px 8px 2px 0;font-weight:normal;">LAT</th>
          <th style="padding:2px 8px 2px 0;font-weight:normal;">LON</th>
          <th style="padding:2px 0;font-weight:normal;">ETA</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
    return `
    <article class="order-note route-note" data-pending="${escapeHtml(p.id)}">
      <header class="order-note-head">
        <span class="order-stamp-word">SECRET</span>
        <span class="order-note-subtitle">– ROUTE PROPOSAL –</span>
      </header>
      <div class="order-note-body">
        <p class="order-kw">PENDING ROUTE · ${owner}</p>
        <p class="order-line">${rationale}</p>
        ${table}
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
          <button class="btn btn-execute" data-route-act="approve" data-pending-id="${escapeHtml(p.id)}">批准实施</button>
          <button class="btn btn-revise" data-route-act="reject" data-pending-id="${escapeHtml(p.id)}">驳回</button>
          <button class="btn" data-route-act="comment" data-pending-id="${escapeHtml(p.id)}">提修改意见</button>
        </div>
      </footer>
    </article>`;
  }

  // 三按钮动作：批准实施=POST /pending-routes/{id}/approve、驳回=reject、
  // 提修改意见=弹出输入框 → POST /routes/{route_id}/comment（修订回路走航线链 id）
  async onRouteAction(act, p) {
    try {
      if (act === 'approve') {
        await this._postApi(`/pending-routes/${p.id}/approve`);
        this.showNotification('✅ 航线提案已批准实施（草案已上图）');
      } else if (act === 'reject') {
        await this._postApi(`/pending-routes/${p.id}/reject`);
        this.showNotification('航线提案已驳回');
      } else if (act === 'comment') {
        const feedback = prompt('提修改意见（将发回航海参谋修订提案）：');
        if (!feedback) return;
        await this._postApi(`/routes/${p.route_id}/comment`, { feedback });
        this.showNotification('修改意见已发回航海参谋');
      }
    } catch (e) {
      this.showNotification('❌ 操作失败: ' + e.message);
      return;
    }
    this.refreshPendingRoutes();
  }

  async _postApi(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || JSON.stringify(err));
    }
    return res.json();
  }

  // E6 空态占位军令纸（.order-note.placeholder）：复用 A8 军令纸全套样式——
  // SECRET 头 + 「– STAFF PROPOSAL –」副题 + 正文 + 签名行；
  // 按钮不带 data-act（不绑回调）且 disabled（禁用态由 .btn:disabled 降低不透明度）
  renderPlaceholderNote() {
    return `
    <article class="order-note placeholder">
      <header class="order-note-head">
        <span class="order-stamp-word">SECRET</span>
        <span class="order-note-subtitle">– STAFF PROPOSAL –</span>
      </header>
      <div class="order-note-body">
        <p class="order-line placeholder-copy">NO PENDING ORDERS — AWAITING STAFF PROPOSAL</p>
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
          <button class="btn btn-execute" disabled>EXECUTE ORDER</button>
          <button class="btn btn-revise" disabled>REVISE PLAN</button>
        </div>
      </footer>
    </article>`;
  }

  // A8 军令纸卡（SECRET – INTERCEPTION PLAN）
  // 字段映射：action_type → MISSION 行；details（k=v 列表）→ EXECUTION 步骤；index → data-index
  renderOrderNote(s, i) {
    // NPC 文本统一转义后再插值，防止注入标记
    const mission = escapeHtml((s.action_type || '').replace(/_/g, ' ').toUpperCase());
    const steps = Object.entries(s.details || {}).map(([k, v]) => `${escapeHtml(k)}=${escapeHtml(v)}`);
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
  // O.1 开局层：战役选择卡（成品图深色 chrome 风格 — 深底+米色卡+墨字+SECRET 章）
  // 数据源 GET /theaters（theaters/ 全包摘要）；开始按钮由 main.js 绑定回调
  // ═══════════════════════════════════════════════════════
  renderCampaignList(theaters, onStart) {
    const container = document.getElementById('campaign-list');
    if (!container) return;
    if (!theaters || theaters.length === 0) {
      container.innerHTML = '<p class="campaign-loading">NO THEATER FILES FOUND</p>';
      return;
    }
    container.innerHTML = theaters.map(t => this.renderTheaterCard(t)).join('');
    container.querySelectorAll('.btn-campaign-start').forEach(btn => {
      btn.addEventListener('click', () => onStart(btn.dataset.theater, btn));
    });
  }

  // 战区卡：SECRET 章字 + 战区名/日期 + 简介（双方兵力名/胜利条件）+ 开始按钮
  renderTheaterCard(t) {
    const scen = t.scenario || {};
    const enemy = scen.enemy_force || {};
    const friendly = scen.friendly_forces || [];
    const victory = scen.victory || {};
    const friendlyLine = friendly.map(tf =>
      `${escapeHtml(tf.callsign || '')} ${escapeHtml(tf.name || '')}（${(tf.carriers || []).map(c => escapeHtml(c)).join(' / ')}）`
    ).join('<br>') || '—';
    const enemyLine = enemy.name
      ? `${escapeHtml(enemy.name)}（${(enemy.carriers || []).map(c => escapeHtml(c)).join(' / ')}）`
      : '—';
    const objective = victory.primary
      ? `<p class="campaign-kw">OBJECTIVE</p><p class="campaign-line">${escapeHtml(victory.primary)}</p>`
      : '';
    return `
    <article class="campaign-card" data-theater="${escapeHtml(t.id)}">
      <header class="campaign-card-head">
        <span class="campaign-card-stamp">SECRET</span>
        <h2 class="campaign-card-name">${escapeHtml(t.name)}</h2>
        <span class="campaign-card-date">${escapeHtml(t.date || '')}</span>
      </header>
      <div class="campaign-card-body">
        <p class="campaign-kw">FRIENDLY FORCES</p>
        <p class="campaign-line">${friendlyLine}</p>
        <p class="campaign-kw">ENEMY FORCE</p>
        <p class="campaign-line">${enemyLine}</p>
        ${objective}
      </div>
      <footer class="campaign-card-foot">
        <button class="btn btn-execute btn-campaign-start" data-theater="${escapeHtml(t.id)}">开始战役</button>
      </footer>
    </article>`;
  }

  showCampaignError(msg) {
    const el = document.getElementById('campaign-error');
    if (el) el.textContent = msg;
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

  // fix Loop2-F6: 底栏空态读数弱化——空值加 .dash-empty（60% 透明斜体），有值移除
  _setDashEmpty(id, isEmpty) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('dash-empty', isEmpty);
  }
}

window.UIController = UIController;
