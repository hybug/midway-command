/**
 * logDesk.js — S8 UI.5 LOG 工作台（M8.6）三视图。
 * TIMELINE：电报/判断/批准/反馈/OTC/S4 冲突统一时间线（点击跳转来源工作台）。
 * ORDERS：命令链（指挥官决议 + 外发电报 + 指挥权变化）。
 * AFTER ACTION：证据—判断—决议因果链 + S3 认知错误/事实误差分离 + 工具/骰子审计。
 * 纪律：旧判断与决议不被覆盖（追加制呈现）；只读视图（操作在其他工作台）。
 */
class LogDesk {
  constructor() {
    this.tab = 'TIMELINE';       // TIMELINE | ORDERS | AFTER
    this.data = null;
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
      this.data = await fetch('/log/timeline').then(r => r.json());
    } catch (e) { this.data = this.data || { events: [], s4_events: [] }; }
    this.render();
  }

  render() {
    if (!this.el) return;
    this.el.innerHTML = `
      <header class="log-head">
        <span class="intel-title">LOG — 记录与复盘</span>
        <nav class="log-tabs">
          <button class="log-tab${this.tab === 'TIMELINE' ? ' active' : ''}" data-log-tab="TIMELINE">TIMELINE</button>
          <button class="log-tab${this.tab === 'ORDERS' ? ' active' : ''}" data-log-tab="ORDERS">ORDERS</button>
          <button class="log-tab${this.tab === 'AFTER' ? ' active' : ''}" data-log-tab="AFTER">AFTER ACTION</button>
        </nav>
      </header>
      <div class="log-body" id="log-body"></div>`;
    this.el.querySelectorAll('[data-log-tab]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.tab = btn.dataset.logTab;
        this.render();
      });
    });
    const body = this.el.querySelector('#log-body');
    if (this.tab === 'TIMELINE') this.renderTimeline(body);
    else if (this.tab === 'ORDERS') this.renderOrders(body);
    else this.renderAfterAction(body);
  }

  // ── TIMELINE（M8.6.1/2）──
  renderTimeline(body) {
    const events = (this.data && this.data.events) || [];
    if (!events.length) {
      body.innerHTML = '<p class="staff-empty">本局暂无记录</p>';
      return;
    }
    const KIND_CN = {
      message: '电报', judgment: '判断', plot_decision: '标图决议',
      commander_feedback: '指挥官反馈', otc_change: '指挥权变化',
    };
    body.innerHTML = `<ol class="log-timeline">${events.map(e => `
      <li class="log-event log-event-${e.kind}">
        <span class="log-time">${window.escapeHtml((e.at || '').slice(11, 16))}Z</span>
        <span class="log-kind">${KIND_CN[e.kind] || window.escapeHtml(e.kind)}</span>
        <span class="log-text">${window.escapeHtml(e.actor)}：${window.escapeHtml(e.text)}</span>
        ${e.jump ? `<button class="btn log-jump" data-jump-wb="${window.escapeHtml(e.jump.workbench)}"
             data-jump-target="${window.escapeHtml(e.jump.target || '')}">查看</button>` : ''}
      </li>`).join('')}</ol>`;
    body.querySelectorAll('[data-jump-wb]').forEach(btn => {
      btn.addEventListener('click', () => {
        window.__intelJumpTarget = btn.dataset.jumpTarget;
        if (window.__desk) window.__desk.switchSection(btn.dataset.jumpWb);
      });
    });
  }

  // ── ORDERS（M8.6.3/4：谁批准/驳回、何时、对什么）──
  async renderOrders(body) {
    let data = {};
    try {
      data = await fetch('/log/after-action').then(r => r.json());
    } catch (e) { /* 维持空态 */ }
    const decisions = [];
    (data.chains || []).forEach(c => {
      c.decisions.forEach(d => decisions.push({
        at: d.at, actor: 'player',
        text: `标图 ${c.plot_id} v${(c.versions.find(v => v.proposal_id === d.proposal_id) || {}).version || '?'} — ${d.action}（${d.comment || '无附言'}）`,
      }));
    });
    let outgoing = [];
    try {
      const ch = await fetch('/comms/channels').then(r => r.json());
      outgoing = (ch.channels && ch.channels.OUTGOING || []).map(m => ({
        at: m.filed_at, actor: 'fletcher',
        text: `外发电报：${m.raw_text.slice(0, 50)}`,
      }));
    } catch (e) { /* 维持空态 */ }
    const otc = (((this.data || {}).events) || [])
      .filter(e => e.kind === 'otc_change')
      .map(e => ({ at: e.at, actor: e.actor, text: e.text }));
    const rows = decisions.concat(outgoing, otc)
      .sort((a, b) => String(a.at || '').localeCompare(String(b.at || '')));
    body.innerHTML = rows.length ? `<ol class="log-timeline">${rows.map(r => `
      <li class="log-event log-event-order">
        <span class="log-time">${window.escapeHtml((r.at || '').slice(11, 16))}Z</span>
        <span class="log-kind">${window.escapeHtml(r.actor)}</span>
        <span class="log-text">${window.escapeHtml(r.text)}</span>
      </li>`).join('')}</ol>`
      : '<p class="staff-empty">暂无命令记录（正式命令经 ISSUE ORDER 下达后在此留档）</p>';
  }

  // ── AFTER ACTION（M8.6.5-7：因果链 + 认知/事实误差分离）──
  async renderAfterAction(body) {
    body.innerHTML = '<p class="staff-empty">复盘载入中…</p>';
    let data = {};
    try {
      data = await fetch('/log/after-action').then(r => r.json());
    } catch (e) { /* 维持空态 */ }
    const esc = window.escapeHtml;
    const chainsHtml = (data.chains || []).map(c => `
      <section class="aa-chain">
        <h3 class="aa-plot">PLOT ${esc(c.plot_id)} ${c.approved_state ? `· ${esc(c.approved_state)} v${c.current_version}` : '· 未上图'}</h3>
        <ol class="aa-steps">
          ${c.evidence.map(e => `<li class="aa-evidence"><b class="claim-fact">证据</b> ${esc(e.id)}（${esc(e.source)}，${esc(e.status)}）：${esc(e.summary)}</li>`).join('')}
          ${c.assessments.map(a => `<li class="aa-assessment"><b class="claim-judgment">判断</b> ${esc(a.id)}（${esc(a.author)}）：${esc(a.narrative)}</li>`).join('')}
          ${c.versions.map(v => `<li class="aa-proposal"><b>提案</b> v${v.version}（${esc(v.author)}）：${esc(v.change_summary)}</li>`).join('')}
          ${c.decisions.map(d => `<li class="aa-decision"><b>决议</b> ${esc(d.action)}：${esc(d.comment || '')}</li>`).join('')}
        </ol>
      </section>`).join('') || '<p class="aa-empty">本局暂无标图链。</p>';

    const judgmentsHtml = (data.judgments || []).map(j => {
      const r = j.result;
      return `<li class="aa-assessment"><b class="claim-judgment">判断</b>
        ${esc(r.actor_id)}（置信 ${esc(r.confidence_band)}${r.refusal_reason ? ` · 拒绝:${esc(r.refusal_reason)}` : ''}）
        ${j.report ? `<span class="staff-report">${esc(j.report)}</span>` : ''}</li>`;
    }).join('');

    const errRows = (data.error_report || []).map(r => `
      <tr>
        <td>${esc(r.actor_id)}</td>
        <td>${esc(r.cognitive_error_type)}${r.cognitive_error_severity ? ` (${r.cognitive_error_severity})` : ''}</td>
        <td>${esc(r.factual_error_type)}${r.factual_error_severity ? ` (${r.factual_error_severity})` : ''}</td>
      </tr>`).join('');
    const errHtml = errRows ? `
      <p class="intel-kw">认知错误 vs 事实误差（复盘分离，D12）</p>
      <table class="log-error-table">
        <thead><tr><th>参谋</th><th>认知错误（相对证据）</th><th>事实误差（相对结果）</th></tr></thead>
        <tbody>${errRows}</tbody>
      </table>` : '<p class="aa-empty">暂无判断复盘数据。</p>';

    const tools = data.tool_calls || [];
    const dice = data.check_records || [];
    body.innerHTML = `
      ${chainsHtml}
      <section class="aa-chain"><h3 class="aa-plot">参谋正式判断（${(data.judgments || []).length}）</h3>
        <ol class="aa-steps">${judgmentsHtml || '<p class="aa-empty">无</p>'}</ol>
      </section>
      ${errHtml}
      <section class="aa-chain"><h3 class="aa-plot">推理工具调用（${tools.length}）</h3>
        ${tools.length ? `<ul>${tools.map(t => `<li class="aa-tool">${esc(t.actor)} → ${esc(t.tool)}（${esc((t.evidence_ids || []).join(', '))}）</li>`).join('')}</ul>`
          : '<p class="aa-empty">参谋未使用推理工具。</p>'}
      </section>
      <section class="aa-chain"><h3 class="aa-plot">骰子检定记录（${dice.length}）</h3>
        <p class="aa-meta">全部检定可回放（种子在案）。</p>
      </section>`;
  }
}

window.LogDesk = LogDesk;
