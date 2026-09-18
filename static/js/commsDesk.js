/**
 * commsDesk.js — S8 UI.2 COMMS 收报室（M8.3）。
 * 布局：左侧频道+电文索引，右侧电文详情与处理记录。
 * 频道：INCOMING / TF17·TF11 / CORRECTIONS / OUTGOING / ARCHIVE。
 * 纪律：在途与丢失内容不可见（服务端白名单保证）；原文只读；
 * 勘误链只追加；电文可跳转关联简报/判断（INTEL 区）。
 * 发报：草稿 → 确认（POST /comms/outgoing）；外发电文不构成正式命令。
 */
class CommsDesk {
  constructor() {
    this.channels = null;
    this.activeChannel = 'INCOMING';
    this.selectedId = null;
    this.el = null;
    this._fetchedAt = -Infinity;
  }

  mount(el) {
    this.el = el;
    this.refresh(true);
  }

  async refresh(force) {
    if (typeof fetch !== 'function') return;
    const now = performance.now();
    if (!force && now - this._fetchedAt < 5000) return;
    this._fetchedAt = now;
    try {
      const data = await fetch('/comms/channels').then(r => r.json());
      this.channels = data.channels || {};
    } catch (e) { this.channels = this.channels || {}; }
    this.render();
  }

  CHANNEL_LABELS = {
    INCOMING: 'INCOMING', TF17_TF11: 'TF17 · TF11',
    CORRECTIONS: 'CORRECTIONS', OUTGOING: 'OUTGOING', ARCHIVE: 'ARCHIVE',
  };

  render() {
    if (!this.el) return;
    const chans = Object.keys(this.CHANNEL_LABELS);
    if (!this.channels[this.activeChannel]) this.activeChannel = 'INCOMING';
    const list = this.channels[this.activeChannel] || [];
    const selected = list.find(m => m.id === this.selectedId) || list[0] || null;
    this.el.innerHTML = `
      <div class="comms-wrap">
        <nav class="comms-channels">
          ${chans.map(c => `
            <button class="comms-chan${c === this.activeChannel ? ' active' : ''}"
                    data-chan="${c}">${this.CHANNEL_LABELS[c]}
              <span class="comms-count">${(this.channels[c] || []).length}</span></button>`).join('')}
        </nav>
        <div class="comms-list">
          ${list.length ? list.slice().reverse().map(m => this.msgRow(m)).join('')
            : '<p class="comms-empty">本频道无电文</p>'}
        </div>
        <div class="comms-detail">${selected ? this.detail(selected) : ''}</div>
      </div>`;
    this.bind(list);
  }

  msgRow(m) {
    const esc = window.escapeHtml;
    const t = (m.received_at || m.filed_at || '').slice(11, 16);
    const flag = m.priority === 'flash' || m.priority === 'urgent' ? ' comms-hot' : '';
    return `<button class="comms-row${flag}${m.id === (this.selectedId || (this.channels[this.activeChannel] || [])[0]?.id) ? ' active' : ''}" data-msg="${esc(m.id)}">
      <span class="comms-row-time">${esc(t)}Z</span>
      <span class="comms-row-sender">${esc(m.sender)}</span>
      ${m.supersedes_message_id ? '<span class="comms-tag">勘误</span>' : ''}
      ${m.condition !== 'complete' ? `<span class="comms-tag">${esc(m.condition)}</span>` : ''}
    </button>`;
  }

  detail(m) {
    const esc = window.escapeHtml;
    const relay = (m.relay_chain || []).length
      ? `<p class="comms-meta">转述链：${esc((m.relay_chain || []).join(' → '))} · 原发送者 ${esc(m.origin_sender || '—')}</p>` : '';
    const route = (m.routed_to || []).length
      ? `<p class="comms-meta">已路由：${esc((m.routed_to || []).join(', '))}</p>` : '';
    const sup = m.supersedes_message_id
      ? `<p class="comms-meta">勘误对象：${esc(m.supersedes_message_id)}（原文保留，只追加更正）</p>` : '';
    const corrections = (this.channels['CORRECTIONS'] || [])
      .filter(c => c.supersedes_message_id === m.id);
    const corrHtml = corrections.length
      ? `<p class="comms-meta">已收勘误：${corrections.map(c => esc(c.id)).join(', ')}</p>` : '';
    const briefs = m.related_brief_ids || [];
    const judgments = m.related_assessment_ids || [];
    const links = (briefs.length || judgments.length)
      ? `<div class="comms-links">
          ${briefs.map(b => `<button class="btn" data-jump-brief="${esc(b)}">简报 ${esc(b)}</button>`).join('')}
          ${judgments.map(a => `<button class="btn" data-jump-brief="${esc(a)}">判断 ${esc(a)}</button>`).join('')}
         </div>` : '';
    const compose = this.activeChannel === 'OUTGOING' ? this.composeForm() : '';
    return `
      <article class="comms-card">
        <header class="comms-card-head">
          <span class="comms-stamp">SECRET</span>
          <span class="comms-card-title">${esc(m.sender)} · ${esc(m.id)}</span>
          <span class="comms-cond">${esc(m.condition)} · ${esc(m.status)}</span>
        </header>
        <p class="comms-meta">观测 ${(m.observed_at || '').slice(11, 16) || '—'}Z ·
           拍发 ${(m.filed_at || '').slice(11, 16) || '—'}Z ·
           收报 ${(m.received_at || '').slice(11, 16) || '—'}Z · 优先级 ${esc(m.priority)}</p>
        ${relay}${route}${sup}${corrHtml}
        <pre class="comms-raw">${esc(m.raw_text)}</pre>
        ${links}${compose}
      </article>`;
  }

  composeForm() {
    return `
      <div class="comms-compose">
        <p class="comms-kw">OUTGOING DRAFT（发报需确认；不构成正式命令）</p>
        <textarea id="comms-draft" rows="2" placeholder="输入外发电文正文..."></textarea>
        <button class="btn btn-execute" id="comms-send">确认拍发</button>
      </div>`;
  }

  bind(list) {
    if (!this.el) return;
    this.el.querySelectorAll('[data-chan]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.activeChannel = btn.dataset.chan;
        this.selectedId = null;
        this.render();
      });
    });
    this.el.querySelectorAll('[data-msg]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.selectedId = btn.dataset.msg;
        this.render();
      });
    });
    // 关联跳转：电文 → INTEL 区简报/判断（跨区上下文，UI.3 消费）
    this.el.querySelectorAll('[data-jump-brief]').forEach(btn => {
      btn.addEventListener('click', () => {
        window.__intelJumpTarget = btn.dataset.jumpBrief;
        if (window.__desk) window.__desk.switchSection('INTEL');
      });
    });
    const send = this.el.querySelector('#comms-send');
    if (send) send.addEventListener('click', async () => {
      const draft = this.el.querySelector('#comms-draft');
      const text = (draft ? draft.value : '').trim();
      if (!text) { if (window.ui) window.ui.showNotification('电文正文不能为空'); return; }
      if (!window.confirm('确认拍发该电文？')) return;   // 发报确认（M8.3.7）
      try {
        const res = await fetch('/comms/outgoing', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ raw_text: text }),
        });
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '拍发失败');
        if (window.ui) window.ui.showNotification('电文已拍发存档');
        this.refresh(true);
      } catch (e) {
        if (window.ui) window.ui.showNotification('❌ ' + e.message);
      }
    });
  }
}

window.CommsDesk = CommsDesk;
