/**
 * intelBoard.js — S2.8 情报板（收报室/简报/审图/复盘）
 * 数据源：GET /intel/inbox、/intel/briefs、/intel/work-items、/intel/plots、
 * /intel/after-action（全部为玩家权限白名单接口）。
 * 视觉语义（S8.5）：事实（墨）/ 参谋判断（红）/ 情报来源（淡）强区分；
 * 未批准提案用 PENDING 金色，已批准标图 APPROVED 印记。
 * 复盘（M2.8.9）：AFTER ACTION 弹层展示 证据→判断→批准 因果链。
 */
// escapeHtml 兜底：fixture/独立加载（无 uiController）时自备，避免渲染崩溃
if (typeof window !== 'undefined' && typeof window.escapeHtml !== 'function') {
  window.escapeHtml = function (s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  };
}
class IntelBoard {
  constructor() {
    this.tab = 'PLOTS';       // PLOTS | INBOX | BRIEF
    this._fetchedAt = -Infinity;
    this.data = { plots: null, inbox: null, briefs: null, work: null };
    this.container = null;
  }

  mount(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;
    this.container.innerHTML = `
      <header class="intel-head">
        <span class="intel-title">INTELLIGENCE</span>
        <nav class="intel-tabs">
          <button class="intel-tab" data-tab="PLOTS">PLOTS <span class="intel-count" data-count="plots">0</span></button>
          <button class="intel-tab" data-tab="INBOX">INBOX <span class="intel-count" data-count="inbox">0</span></button>
          <button class="intel-tab" data-tab="BRIEF">BRIEF <span class="intel-count" data-count="briefs">0</span></button>
          <button class="intel-tab intel-tab-after" data-tab="AFTER">AFTER ACTION</button>
        </nav>
      </header>
      <div class="intel-body" id="intel-body"></div>`;
    this.container.querySelectorAll('.intel-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        if (tab === 'AFTER') { this.showAfterAction(); return; }
        this.tab = tab;
        this.render();
      });
    });
    this.refresh();
  }

  // ── 数据拉取（5s 节流；失败静默维持现状）──
  refresh(force) {
    if (typeof fetch !== 'function') return;
    const now = performance.now();
    if (!force && now - this._fetchedAt < 5000) return;
    this._fetchedAt = now;
    const get = (path, key, pick) => fetch(path)
      .then(r => r.json())
      .then(d => { this.data[key] = pick(d); this.renderCounts(); this.render(); })
      .catch(() => {});
    get('/intel/plots', 'plots', d => d);
    get('/intel/inbox', 'inbox', d => d.messages);
    get('/intel/briefs', 'briefs', d => d.briefs);
    get('/intel/work-items', 'work', d => d.work_items);
  }

  renderCounts() {
    if (!this.container) return;
    const set = (k, v) => {
      const el = this.container.querySelector(`[data-count="${k}"]`);
      if (el) el.textContent = v;
    };
    const plots = this.data.plots || {};
    set('plots', (plots.pending_proposals || []).length);
    set('inbox', (this.data.inbox || []).length);
    set('briefs', (this.data.briefs || []).length);
  }

  render() {
    const body = this.container && this.container.querySelector('#intel-body');
    if (!body) return;
    if (this.tab === 'PLOTS') this.renderPlots(body);
    else if (this.tab === 'INBOX') this.renderInbox(body);
    else this.renderBriefs(body);
  }

  // ── PLOTS：审图（待批提案卡 + 已批准历史）──
  renderPlots(body) {
    const plots = this.data.plots || {};
    const pending = plots.pending_proposals || [];
    const approved = plots.approved_plots || [];
    let html = '';
    if (!pending.length && !approved.length) {
      html = '<div class="intel-empty">NO PLOT PROPOSALS — 情报参谋呈报后在此审批</div>';
    }
    pending.forEach(p => { html += this.plotProposalCard(p); });
    approved.forEach(ap => { html += this.approvedCard(ap); });
    body.innerHTML = html;
    body.querySelectorAll('[data-plot-act]').forEach(btn => {
      btn.addEventListener('click', () => this.plotAction(btn.dataset.plotAct, btn.dataset.proposalId));
    });
  }

  plotProposalCard(p) {
    const g = p.geometry || {};
    const geoLine = g.lat !== undefined && g.lat !== null
      ? `${Math.abs(g.lat).toFixed(1)}°${g.lat >= 0 ? 'N' : 'S'} ${Math.abs(g.lon).toFixed(1)}°${g.lon >= 0 ? 'E' : 'W'}`
      : '—';
    const conf = Object.entries(p.confidence || {})
      .map(([k, v]) => `${k} ${(Math.round(v * 100))}%`).join(' · ') || '—';
    const annos = (p.annotations || [])
      .map(a => `<p class="intel-anno intel-anno-${escapeHtml(a.stance || 'note')}">批注（${escapeHtml(a.by)}）：${escapeHtml(a.note)}</p>`)
      .join('');
    return `
    <article class="intel-card plot-card pending" data-proposal="${escapeHtml(p.id)}">
      <header class="intel-card-head">
        <span class="intel-stamp-word">SECRET</span>
        <span class="intel-card-subtitle">– PLOT PROPOSAL v${p.version} –</span>
      </header>
      <div class="intel-card-body">
        <p class="intel-line">${escapeHtml(p.change_summary || '')}</p>
        <p class="intel-meta">POS ${geoLine}${g.distance_nm ? ' · ' + Math.round(g.distance_nm) + 'nm' : ''}${g.bearing_line_deg ? ' · BRG ' + Math.round(g.bearing_line_deg) + '°' : ''} · ${escapeHtml(p.method || '')}</p>
        <p class="intel-meta">置信度：${escapeHtml(conf)}（参谋判断）</p>
        ${annos}
      </div>
      <footer class="intel-actions">
        <button class="btn btn-execute" data-plot-act="approve" data-proposal-id="${escapeHtml(p.id)}">批准上图</button>
        <button class="btn btn-revise" data-plot-act="reject" data-proposal-id="${escapeHtml(p.id)}">驳回</button>
        <button class="btn" data-plot-act="request-revision" data-proposal-id="${escapeHtml(p.id)}">要求修订</button>
        <button class="btn" data-plot-act="defer" data-proposal-id="${escapeHtml(p.id)}">暂缓</button>
      </footer>
    </article>`;
  }

  approvedCard(ap) {
    const latest = (ap.history || []).slice(-1)[0] || {};
    return `
    <article class="intel-card plot-card approved">
      <header class="intel-card-head">
        <span class="intel-stamp-word approved">APPROVED</span>
        <span class="intel-card-subtitle">– OFFICIAL PLOT v${ap.current_version} –</span>
      </header>
      <div class="intel-card-body">
        <p class="intel-line">${escapeHtml(latest.change_summary || '')}</p>
        <p class="intel-meta">批准时间 ${escapeHtml((ap.approved_at || '').slice(11, 16) || '—')}Z · 决议 ${escapeHtml(latest.decision_id || '—')}</p>
      </div>
    </article>`;
  }

  // ── INBOX：旗舰收报室 ──
  renderInbox(body) {
    const msgs = this.data.inbox || [];
    if (!msgs.length) {
      body.innerHTML = '<div class="intel-empty">INBOX EMPTY — 未收到电文（在途内容不可见）</div>';
      return;
    }
    body.innerHTML = msgs.slice().reverse().map(m => `
      <article class="intel-card msg-card${m.status === 'corrected' ? ' corrected' : ''}">
        <header class="intel-card-head">
          <span class="intel-card-subtitle">${escapeHtml(m.sender || '')} · ${escapeHtml((m.received_at || '').slice(11, 16) || '')}Z</span>
          <span class="intel-cond">${escapeHtml(m.status)}${m.supersedes_message_id ? ' · 勘误' : ''}</span>
        </header>
        <div class="intel-card-body"><p class="intel-raw">${escapeHtml(m.raw_text)}</p></div>
      </article>`).join('');
  }

  // ── BRIEF：情报判断书（事实/判断/来源 强区分）──
  renderBriefs(body) {
    const briefs = this.data.briefs || [];
    if (!briefs.length) {
      body.innerHTML = '<div class="intel-empty">NO BRIEFS — 情报参谋研判后在此呈报</div>';
      return;
    }
    body.innerHTML = briefs.slice().reverse().map(b => {
      const narrative = escapeHtml(b.narrative || '')
        .replace(/【事实】/g, '<b class="claim-fact">【事实】</b>')
        .replace(/【判断】/g, '<b class="claim-judgment">【判断】</b>')
        .replace(/【推测】/g, '<b class="claim-hyp">【推测】</b>');
      const qs = (b.unresolved_questions || [])
        .map(q => `<p class="intel-anno intel-anno-concern">未决：${escapeHtml(q)}</p>`).join('');
      return `
      <article class="intel-card brief-card">
        <header class="intel-card-head">
          <span class="intel-stamp-word">SECRET</span>
          <span class="intel-card-subtitle">– INTELLIGENCE BRIEF · ${escapeHtml(b.author || '')} –</span>
        </header>
        <div class="intel-card-body">
          <p class="intel-line">${narrative}</p>
          <p class="intel-meta">证据：${escapeHtml((b.new_evidence_ids || []).join(', ') || '—')}</p>
          ${qs}
        </div>
      </article>`;
    }).join('');
  }

  // ── 提案决议动作 ──
  async plotAction(action, proposalId) {
    const path = action === 'request-revision'
      ? 'request-revision' : action;
    try {
      await this._post(`/intel/plots/${proposalId}/${path}`, {});
      const labels = { approve: '已批准上图', reject: '已驳回', defer: '已暂缓', 'request-revision': '已要求修订' };
      if (window.ui && window.ui.showNotification) {
        window.ui.showNotification(`📄 标图提案${labels[action] || action}`);
      }
    } catch (e) {
      if (window.ui && window.ui.showNotification) {
        window.ui.showNotification('❌ 操作失败: ' + e.message);
      }
    }
    this.refresh(true);
    if (window.__loadState) window.__loadState();
  }

  // ── AFTER ACTION：证据—判断—批准 因果链复盘 ──
  // showPlotChain(plotId)：海图敌标一键反查——只展开该标图链
  async showPlotChain(plotId) {
    let data;
    try {
      data = await fetch('/intel/after-action').then(r => r.json());
    } catch (e) { return; }
    const chain = (data.chains || []).find(c => c.plot_id === plotId);
    if (!chain) return;
    await this._renderAfterAction({ chains: [chain],
                                    tool_calls: (data.tool_calls || [])
                                      .filter(t => chain.assessments.length),
                                    check_records: data.check_records || [] });
  }

  async showAfterAction() {
    let data;
    try {
      data = await fetch('/intel/after-action').then(r => r.json());
    } catch (e) { return; }
    await this._renderAfterAction(data);
  }

  async _renderAfterAction(data) {
    const chains = data.chains || [];
    const tools = data.tool_calls || [];
    const dice = data.check_records || [];
    const chainHtml = chains.length ? chains.map(c => `
      <section class="aa-chain">
        <h3 class="aa-plot">PLOT ${escapeHtml(c.plot_id)} ${c.approved_state ? `· ${escapeHtml(c.approved_state)} v${c.current_version}` : '· 未上图'}</h3>
        <ol class="aa-steps">
          ${c.evidence.map(e => `<li class="aa-evidence"><b class="claim-fact">证据</b> ${escapeHtml(e.id)}（${escapeHtml(e.source)}，${escapeHtml(e.status)}）：${escapeHtml(e.summary)}</li>`).join('')}
          ${c.assessments.map(a => `<li class="aa-assessment"><b class="claim-judgment">判断</b> ${escapeHtml(a.id)}（${escapeHtml(a.author)}）：${escapeHtml(a.narrative)} <span class="aa-meta">骰子 ${escapeHtml((a.dice_record_ids || []).join(','))} 冲突 ${escapeHtml((a.conflict_ids || []).join(',') || '无')}</span></li>`).join('')}
          ${c.claims.map(cl => `<li class="aa-claim"><b class="claim-${escapeHtml(cl.type) === 'fact' ? 'fact' : escapeHtml(cl.type) === 'hypothesis' ? 'hyp' : 'judgment'}">${escapeHtml(cl.type)}</b> ${escapeHtml(cl.text)}</li>`).join('')}
          ${c.versions.map(v => `<li class="aa-proposal"><b>提案</b> v${v.version}（${escapeHtml(v.author)}）：${escapeHtml(v.change_summary)}${(v.annotations || []).map(an => ` <span class="aa-meta">批注 ${escapeHtml(an.by)}:${escapeHtml(an.note)}</span>`).join('')}</li>`).join('')}
          ${c.decisions.map(d => `<li class="aa-decision"><b>决议</b> ${escapeHtml(d.action)}（${escapeHtml(d.at || '')}）：${escapeHtml(d.comment || '')}</li>`).join('')}
        </ol>
      </section>`).join('')
      : '<p class="aa-empty">本局暂无标图链。</p>';
    const modal = document.getElementById('after-action');
    modal.querySelector('#aa-body').innerHTML = `
      ${chainHtml}
      <section class="aa-chain"><h3 class="aa-plot">推理工具调用（${tools.length}）</h3>
        ${tools.length ? `<ul>${tools.map(t => `<li class="aa-tool">${escapeHtml(t.actor)} → ${escapeHtml(t.tool)}（${escapeHtml((t.evidence_ids || []).join(', '))}）</li>`).join('')}</ul>` : '<p class="aa-empty">参谋未使用推理工具。</p>'}
      </section>
      <section class="aa-chain"><h3 class="aa-plot">骰子检定记录（${dice.length}）</h3>
        <p class="aa-meta">全部检定可回放（种子在案）；共 ${dice.length} 条。</p>
      </section>`;
    modal.hidden = false;
    const close = modal.querySelector('#aa-close');
    if (close && !close.dataset.bound) {
      close.dataset.bound = '1';
      close.addEventListener('click', () => { modal.hidden = true; });
    }
  }

  async _post(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || JSON.stringify(err));
    }
    return res.json();
  }
}

window.IntelBoard = IntelBoard;
