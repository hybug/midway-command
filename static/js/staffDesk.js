/**
 * staffDesk.js — S8 UI.4 STAFF 参谋工作台（M8.5）三栏布局。
 * 左：参谋名册（状态灯：待命/未读/分歧/来访）
 * 中：对话（普通交谈）与正式呈报（JudgmentResult+人物化报告）
 * 右：极简人物档案（身份/状态/关注/最近互动——不渲染任何关系数值）
 * 纪律：普通聊天不触发正式命令；「要求正式判断」产生 JudgmentTask；
 * NPC 权限与来源链可见（判断卡标注证据来源数）；S4 事件经 s4Adapter 预留。
 */
class StaffDesk {
  constructor() {
    this.staff = [];
    this.activeId = null;
    this.histories = {};        // actor_id → [{role, content}]（对话型）
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
      const data = await fetch('/staff/roster').then(r => r.json());
      this.staff = data.staff || [];
    } catch (e) { this.staff = this.staff || []; }
    if (!this.activeId && this.staff.length) {
      this.activeId = (this.staff.find(s => s.source === 'judgment')
        || this.staff[0]).actor_id;
    }
    this.render();
  }

  current() {
    return this.staff.find(s => s.actor_id === this.activeId) || null;
  }

  render() {
    if (!this.el) return;
    const cur = this.current();
    this.el.innerHTML = `
      <div class="staff-wrap">
        <nav class="staff-roster">
          <p class="staff-kw">参谋名册</p>
          ${this.staff.map(s => this.rosterRow(s)).join('')}
        </nav>
        <section class="staff-center">${cur ? this.center(cur) : ''}</section>
        <aside class="staff-dossier">${cur ? this.dossier(cur) : ''}</aside>
      </div>`;
    this.bind(cur);
  }

  rosterRow(s) {
    const esc = window.escapeHtml;
    const visited = (window.__staffVisits || []).some(v => v.actor_id === s.actor_id);
    const dot = visited || (s.source === 'judgment'
      && s.dossier.status_line !== '在舱待命') ? ' staff-dot-active' : '';
    return `<button class="staff-row${s.actor_id === this.activeId ? ' active' : ''}${dot}"
      data-staff="${esc(s.actor_id)}">
      <span class="staff-row-name">${esc(s.display_name)}</span>
      <span class="staff-row-role">${esc(s.role)}</span></button>`;
  }

  // 中栏：对话型=聊天；判断型=正式呈报（要求判断 + 判断列表）
  center(s) {
    if (s.source === 'chat') return this.chatPane(s);
    return this.judgmentPane(s);
  }

  chatPane(s) {
    const hist = this.histories[s.actor_id] || [];
    return `
      <p class="staff-kw">对话（普通交谈不构成正式命令）</p>
      <div class="staff-chat" id="staff-chat-log">
        ${hist.length ? hist.map(m => `
          <div class="staff-msg staff-msg-${m.role === 'user' ? 'player' : 'npc'}">
            <span class="staff-msg-sender">${m.role === 'user' ? '指挥官' : window.escapeHtml(s.display_name)}</span>
            <p>${window.escapeHtml(m.content)}</p>
          </div>`).join('')
          : '<p class="staff-empty">暂无对话</p>'}
      </div>
      <div class="staff-input">
        <input type="text" id="staff-chat-input" placeholder="交谈…" autocomplete="off">
        <button class="btn btn-send" id="staff-chat-send">发送</button>
      </div>`;
  }

  judgmentPane(s) {
    return `
      <p class="staff-kw">正式呈报（判断经规则引擎检定，普通交谈不可替代）</p>
      <div class="staff-ask">
        <input type="text" id="staff-question" placeholder="要求正式判断：如「这份接触报告是否足以支持立即放飞全力攻击？」" autocomplete="off">
        <button class="btn btn-execute" id="staff-ask-judgment">要求正式判断</button>
      </div>
      <div class="staff-judgments" id="staff-judgments"><p class="staff-empty">载入中…</p></div>`;
  }

  // 右栏：极简档案（M8.5.5 四行，无内部数值）
  dossier(s) {
    const esc = window.escapeHtml;
    const d = s.dossier || {};
    const recent = (d.recent || []).map(r =>
      `<p class="dossier-recent-item">· ${esc((r.at || '').slice(11, 16))}Z ${esc(r.note)}</p>`).join('');
    return `
      <p class="staff-kw">人物档案</p>
      <p class="dossier-name">${esc(s.display_name)}</p>
      <p class="dossier-role">${esc(s.role)}</p>
      <p class="staff-kw">当前状态</p>
      <p class="dossier-line">${esc(d.status_line || '—')}</p>
      <p class="staff-kw">当前关注</p>
      <p class="dossier-line">${esc(d.current_focus || '—')}</p>
      <p class="staff-kw">最近互动</p>
      ${recent || '<p class="dossier-recent-item">· 暂无</p>'}`;
  }

  bind(s) {
    if (!this.el || !s) return;
    this.el.querySelectorAll('[data-staff]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.activeId = btn.dataset.staff;
        this.render();
      });
    });
    if (s.source === 'chat') {
      const input = this.el.querySelector('#staff-chat-input');
      const send = this.el.querySelector('#staff-chat-send');
      const doSend = async () => {
        const text = (input ? input.value : '').trim();
        if (!text) return;
        input.value = '';
        const hist = this.histories[s.actor_id] = this.histories[s.actor_id] || [];
        hist.push({ role: 'user', content: text });
        this.render();
        try {
          const res = await fetch('/chat', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ npc_id: s.actor_id, message: text }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || res.statusText);
          hist.push({ role: 'assistant', content: data.text });
        } catch (e) {
          hist.push({ role: 'assistant', content: `[错误] ${e.message}` });
        }
        this.render();
      };
      if (send) send.addEventListener('click', doSend);
      if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') doSend(); });
    } else {
      const ask = this.el.querySelector('#staff-ask-judgment');
      if (ask) ask.addEventListener('click', () => this.requestJudgment(s));
      this.loadJudgments(s);
    }
  }

  // 要求正式判断（§7.3：STAFF → JudgmentTask → 判断/建议/依据）
  async requestJudgment(s) {
    const input = this.el.querySelector('#staff-question');
    const question = (input ? input.value : '').trim();
    if (!question) { if (window.ui) window.ui.showNotification('请输入判断问题'); return; }
    try {
      const res = await fetch('/judgment/tasks', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actor_id: s.actor_id, question }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      if (window.ui) window.ui.showNotification(`判断已呈报（${data.result.confidence_band}）`);
      await this.loadJudgments(s, data);
    } catch (e) {
      if (window.ui) window.ui.showNotification('❌ ' + e.message);
    }
  }

  bindJudgmentActions(s) {
    const box = this.el && this.el.querySelector('#staff-judgments');
    if (!box) return;
    box.querySelectorAll('[data-feedback]').forEach(btn => {
      btn.addEventListener('click', async () => {
        try {
          const res = await fetch(`/judgment/results/${btn.dataset.rid}/feedback`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ decision: btn.dataset.feedback }),
          });
          if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '失败');
          if (window.ui) window.ui.showNotification(`反馈已记录（${btn.dataset.feedback}）`);
          this.refresh(true);
        } catch (e) {
          if (window.ui) window.ui.showNotification('❌ ' + e.message);
        }
      });
    });
    // AS.1/R3：玩家转述入口已移除——下级信息按指挥链上呈（S4 ChainReport）
  }

  async loadJudgments(s, preloaded) {
    const box = this.el && this.el.querySelector('#staff-judgments');
    if (!box) return;
    let judgments = null;
    if (preloaded) {
      const all = await fetch(`/npcs/${s.actor_id}/judgments`).then(r => r.json()).catch(() => null);
      judgments = all ? all.judgments : [preloaded];
    } else {
      const all = await fetch(`/npcs/${s.actor_id}/judgments`).then(r => r.json()).catch(() => null);
      judgments = all ? all.judgments : [];
    }
    const esc = window.escapeHtml;
    box.innerHTML = judgments.length ? judgments.slice().reverse().map(j => {
      const r = j.result;
      const chosen = (j.hypotheses || []).find(h => h.id === r.chosen_hypothesis_id);
      const band = `conf-${esc(r.confidence_band)}`;
      const errLine = r.error_type && r.error_type !== 'none'
        ? `<span class="staff-err">认知错误：${esc(r.error_type)}（${r.error_severity}）</span>` : '';
      const refusal = r.refusal_reason
        ? `<p class="staff-refusal">拒绝判断：${esc(r.refusal_reason)}</p>` : '';
      const cmm = (r.change_my_mind || []).length
        ? `<p class="staff-meta">改变判断的条件：${esc(r.change_my_mind.join('；'))}</p>` : '';
      // S8 UI.6：S3 候选判断展示——备选解释（兼容集内非选定候选）
      const alts = (j.hypotheses || []).filter(h => h.id !== r.chosen_hypothesis_id);
      const altsHtml = alts.length
        ? `<p class="staff-meta">备选解释：${alts.map(h => esc(h.text)).join('；')}</p>` : '';
      // S8 UI.6：指挥官反馈（正式结果只读，反馈进记忆）；转述已按 AS.1/R3 移除
      const actions = `
        <div class="staff-judgment-actions">
          <span class="staff-kw">指挥官反馈：</span>
          <button class="btn" data-feedback="approve" data-rid="${esc(r.id)}">采纳</button>
          <button class="btn" data-feedback="reject" data-rid="${esc(r.id)}">驳回</button>
          <button class="btn" data-feedback="defer" data-rid="${esc(r.id)}">暂缓</button>
        </div>`;
      const hypo = chosen
        ? `<p class="staff-chosen">【判断】${esc(chosen.text)}</p>` : '';
      const assumptions = (r.assumptions || []).length
        ? `<p class="staff-meta">关键假设：${esc(r.assumptions.join('；'))}</p>` : '';
      return `
      <article class="staff-judgment-card">
        <header class="staff-judgment-head">
          <span class="intel-stamp-word">SECRET</span>
          <span class="staff-judgment-title">正式判断 ${esc(r.id)} · ${(r.created_at || '').slice(11, 16)}Z</span>
          <span class="staff-conf ${band}">${esc(r.confidence_band)}</span>
        </header>
        ${hypo}${refusal}
        ${r.recommendation ? `<p class="staff-recommendation">建议：${esc(r.recommendation)}</p>` : ''}
        ${assumptions}${cmm}${altsHtml}${errLine}
        ${j.report ? `<p class="staff-report">${esc(j.report)}</p>` : ''}
        ${actions}
      </article>`;
    }).join('') : '<p class="staff-empty">尚无正式判断——用上方入口要求判断</p>';
    this.bindJudgmentActions(s);
  }
}

window.StaffDesk = StaffDesk;
