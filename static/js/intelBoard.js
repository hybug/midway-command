/**
 * intelBoard.js — S8 UI.3 INTEL 情报工作台（M8.4）+ 右栏迷你摘要。
 * 案卷台四视图：SITREP 态势摘要 / BRIEFS 判断书 / PLOTS 标图审批（审图模式）/
 * EVIDENCE 已呈报证据链。INBOX 已迁 COMMS 工作台（UI.2）。
 * 数据源（玩家白名单）：/intel/sitrep、/intel/briefs、/intel/plots(+history)、
 * /intel/work-items、/intel/evidence、/intel/after-action。
 * 视觉语义（S2.8 沿革）：事实（墨）/判断（红）/推测（淡）；PENDING 金圈/ APPROVED 印记；
 * 默认海图仍只显示已批准标图——审图动作只在本工作台。
 * 兼容：海图敌标一键反查 showPlotChain、AFTER ACTION 复盘弹层保留。
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
    this.tab = 'SITREP';      // SITREP | BRIEFS | PLOTS | EVIDENCE
    this._fetchedAt = -Infinity;
    this.data = { plots: null, briefs: null, work: null, sitrep: null, evidence: null };
    this.container = null;
    this.deskEl = null;
  }

  // ── 右栏迷你摘要（L1 值班层）──
  mount(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;
    this.container.innerHTML = `
      <header class="intel-head">
        <span class="intel-title">INTELLIGENCE</span>
        <span class="intel-mini-counts" data-mini="counts">—</span>
      </header>
      <div class="intel-mini" data-mini="latest"></div>`;
    this.refresh();
  }

  // ── 案卷台 INTEL 区（L2，M8.4）──
  mountDesk(el) {
    this.deskEl = el;
    el.innerHTML = `
      <header class="intel-desk-head">
        <span class="intel-title">INTELLIGENCE — 情报工作台</span>
        <nav class="intel-tabs">
          <button class="intel-tab" data-tab="SITREP">SITREP</button>
          <button class="intel-tab" data-tab="BRIEFS">BRIEFS <span class="intel-count" data-count="briefs">0</span></button>
          <button class="intel-tab" data-tab="PLOTS">PLOTS <span class="intel-count" data-count="plots">0</span></button>
          <button class="intel-tab" data-tab="EVIDENCE">EVIDENCE <span class="intel-count" data-count="evidence">0</span></button>
        </nav>
      </header>
      <div class="intel-desk-body" id="intel-desk-body"></div>`;
    el.querySelectorAll('.intel-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        this.tab = btn.dataset.tab;
        this.renderDesk();
      });
    });
    this.refresh(true).then(() => this.renderDesk());
    // COMMS 跳转目标（电文 → 简报/判断）
    if (window.__intelJumpTarget) {
      this.tab = 'BRIEFS';
    }
  }

  // ── 数据拉取（5s 节流；失败静默维持现状）──
  async refresh(force) {
    if (typeof fetch !== 'function') return Promise.resolve();
    const now = performance.now();
    if (!force && now - this._fetchedAt < 5000) return Promise.resolve();
    this._fetchedAt = now;
    const get = (path, key, pick) => fetch(path)
      .then(r => r.json())
      .then(d => { this.data[key] = pick(d); })
      .catch(() => {});
    await Promise.all([
      get('/intel/plots', 'plots', d => d),
      get('/intel/briefs', 'briefs', d => d.briefs),
      get('/intel/work-items', 'work', d => d.work_items),
      get('/intel/sitrep', 'sitrep', d => d),
      get('/intel/evidence', 'evidence', d => d.evidence),
    ]);
    this.renderCounts();
    this.renderMini();
    this.renderDesk();
  }

  renderCounts() {
    const plots = this.data.plots || {};
    const briefs = (this.data.briefs || []).length;
    const evidence = (this.data.evidence || []).length;
    if (this.deskEl) {
      const set = (k, v) => {
        const el = this.deskEl.querySelector(`[data-count="${k}"]`);
        if (el) el.textContent = v;
      };
      set('plots', (plots.pending_proposals || []).length);
      set('briefs', briefs);
      set('evidence', evidence);
    }
  }

  renderMini() {
    if (!this.container) return;
    const plots = this.data.plots || {};
    const sit = this.data.sitrep || {};
    const counts = this.container.querySelector('[data-mini="counts"]');
    if (counts) counts.textContent =
      `待批 ${(plots.pending_proposals || []).length} · 简报 ${(this.data.briefs || []).length}` +
      ` · 冲突 ${(sit.open_conflicts || []).length}`;
    const latest = this.container.querySelector('[data-mini="latest"]');
    if (latest) {
      const b = sit.latest_brief;
      latest.innerHTML = b
        ? `<p class="intel-mini-brief">${window.escapeHtml((b.at || '').slice(11, 16))}Z ${window.escapeHtml(b.author || '')}：<br>${window.escapeHtml((b.narrative || '').slice(0, 90))}…</p>`
        : '<p class="intel-mini-brief intel-empty">情报参谋研判后在此呈报</p>';
    }
  }

  renderDesk() {
    const body = this.deskEl && this.deskEl.querySelector('#intel-desk-body');
    if (!body) return;
    this.deskEl.querySelectorAll('.intel-tab').forEach(btn =>
      btn.classList.toggle('active', btn.dataset.tab === this.tab));
    if (this.tab === 'SITREP') this.renderSitrep(body);
    else if (this.tab === 'BRIEFS') this.renderBriefs(body);
    else if (this.tab === 'PLOTS') this.renderPlots(body);
    else this.renderEvidence(body);
  }

  // ── SITREP（M8.4.1）──
  renderSitrep(body) {
    const sit = this.data.sitrep || {};
    const work = (this.data.work || []).filter(
      w => w.status !== 'submitted' && w.status !== 'closed');
    const conflicts = (sit.open_conflicts || []).map(c =>
      `<p class="intel-anno intel-anno-object">冲突 ${window.escapeHtml(c.id)}（${window.escapeHtml(c.kind)}）：${window.escapeHtml(c.note)}</p>`).join('');
    body.innerHTML = `
      <div class="intel-sitrep">
        <div class="intel-sit-grid">
          <div class="intel-sit-cell"><p class="intel-kw">已批准接触</p><p class="intel-sit-val">${sit.approved_contacts ?? 0}</p></div>
          <div class="intel-sit-cell"><p class="intel-kw">最近批准</p><p class="intel-sit-val">${window.escapeHtml((sit.latest_approved_at || '').slice(11, 16) || '—')}Z</p></div>
          <div class="intel-sit-cell"><p class="intel-kw">待处理简报</p><p class="intel-sit-val">${sit.pending_briefs ?? 0}</p></div>
          <div class="intel-sit-cell"><p class="intel-kw">待研判工作项</p><p class="intel-sit-val">${work.length}</p></div>
        </div>
        <p class="intel-kw">未决冲突（登记不裁决）</p>
        ${conflicts || '<p class="intel-empty">无未决冲突</p>'}
      </div>`;
  }

  // ── PLOTS：审图模式（待批提案 + 版本比较 + 已批准历史）──
  renderPlots(body) {
    const plots = this.data.plots || {};
    const pending = plots.pending_proposals || [];
    const approved = plots.approved_plots || [];
    let html = '';
    if (!pending.length && !approved.length) {
      html = '<div class="intel-empty">NO PLOT PROPOSALS — 情报参谋呈报后在此审批</div>';
    }
    if (pending.length) {
      html += '<p class="intel-kw">审图模式 — 待指挥官决议（批准不等于确认事实）</p>';
    }
    pending.forEach(p => { html += this.plotProposalCard(p); });
    if (approved.length) html += '<p class="intel-kw">正式标图（海图唯一敌情输入）</p>';
    approved.forEach(ap => { html += this.approvedCard(ap); });
    body.innerHTML = html;
    body.querySelectorAll('[data-plot-act]').forEach(btn => {
      btn.addEventListener('click', () => this.plotAction(btn.dataset.plotAct, btn.dataset.proposalId));
    });
    body.querySelectorAll('[data-plot-compare]').forEach(btn => {
      btn.addEventListener('click', () => this.compareVersions(btn.dataset.plotCompare, body));
    });
  }

  plotProposalCard(p) {
    const esc = window.escapeHtml;
    const g = p.geometry || {};
    const geoLine = g.lat !== undefined && g.lat !== null
      ? `${Math.abs(g.lat).toFixed(1)}°${g.lat >= 0 ? 'N' : 'S'} ${Math.abs(g.lon).toFixed(1)}°${g.lon >= 0 ? 'E' : 'W'}`
      : '—';
    const conf = Object.entries(p.confidence || {})
      .map(([k, v]) => `${k} ${(Math.round(v * 100))}%`).join(' · ') || '—';
    const annos = (p.annotations || [])
      .map(a => `<p class="intel-anno intel-anno-${esc(a.stance || 'note')}">批注（${esc(a.by)}）：${esc(a.note)}</p>`)
      .join('');
    return `
    <article class="intel-card plot-card pending" data-proposal="${esc(p.id)}">
      <header class="intel-card-head">
        <span class="intel-stamp-word">SECRET</span>
        <span class="intel-card-subtitle">– PLOT PROPOSAL v${p.version} –</span>
      </header>
      <div class="intel-card-body">
        <p class="intel-line">${esc(p.change_summary || '')}</p>
        <p class="intel-meta">POS ${geoLine}${g.distance_nm ? ' · ' + Math.round(g.distance_nm) + 'nm' : ''}${g.bearing_line_deg ? ' · BRG ' + Math.round(g.bearing_line_deg) + '°' : ''} · ${esc(p.method || '')}</p>
        <p class="intel-meta">置信度：${esc(conf)}（参谋判断）· 证据：${esc((p.based_on_evidence_ids || []).join(', ') || '—')}</p>
        ${annos}
      </div>
      <footer class="intel-actions">
        <button class="btn btn-execute" data-plot-act="approve" data-proposal-id="${esc(p.id)}">批准上图</button>
        <button class="btn btn-revise" data-plot-act="reject" data-proposal-id="${esc(p.id)}">驳回</button>
        <button class="btn" data-plot-act="request-revision" data-proposal-id="${esc(p.id)}">要求修订</button>
        <button class="btn" data-plot-act="defer" data-proposal-id="${esc(p.id)}">暂缓</button>
        ${p.version > 1 || p.supersedes_version ? `<button class="btn" data-plot-compare="${esc(p.plot_id)}">版本比较</button>` : ''}
      </footer>
      <div class="intel-compare" data-compare-for="${esc(p.plot_id)}"></div>
    </article>`;
  }

  // 新旧版本比较（M8.2.4/M8.4）：标图链逐版本几何/摘要对照
  async compareVersions(plotId, body) {
    const box = body.querySelector(`[data-compare-for="${plotId}"]`);
    if (!box) return;
    let versions = [];
    try {
      const data = await fetch(`/intel/plots/${plotId}/history`).then(r => r.json());
      versions = data.versions || [];
    } catch (e) { return; }
    const rows = versions.map(v => {
      const g = v.geometry || {};
      const pos = g.lat !== undefined && g.lat !== null
        ? `${Math.abs(g.lat).toFixed(1)}N ${Math.abs(g.lon).toFixed(1)}W r${g.uncertainty_radius_nm ?? '?'}nm`
        : '—';
      return `<tr><td>v${v.version}</td><td>${window.escapeHtml(v.status)}</td>
        <td>${pos}</td><td>${window.escapeHtml(v.change_summary || '')}</td></tr>`;
    }).join('');
    box.innerHTML = `
      <p class="intel-kw">版本链比较（只追加，不覆盖）</p>
      <table class="intel-compare-table"><tbody>${rows}</tbody></table>`;
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
        <p class="intel-line">${window.escapeHtml(latest.change_summary || '')}</p>
        <p class="intel-meta">批准时间 ${window.escapeHtml((ap.approved_at || '').slice(11, 16) || '—')}Z · 决议 ${window.escapeHtml(latest.decision_id || '—')}</p>
      </div>
    </article>`;
  }

  // ── BRIEFS：情报判断书（事实/判断/来源 强区分）──
  renderBriefs(body) {
    const briefs = this.data.briefs || [];
    if (!briefs.length) {
      body.innerHTML = '<div class="intel-empty">NO BRIEFS — 情报参谋研判后在此呈报</div>';
      return;
    }
    body.innerHTML = briefs.slice().reverse().map(b => {
      const narrative = window.escapeHtml(b.narrative || '')
        .replace(/【事实】/g, '<b class="claim-fact">【事实】</b>')
        .replace(/【判断】/g, '<b class="claim-judgment">【判断】</b>')
        .replace(/【推测】/g, '<b class="claim-hyp">【推测】</b>');
      const qs = (b.unresolved_questions || [])
        .map(q => `<p class="intel-anno intel-anno-concern">未决：${window.escapeHtml(q)}</p>`).join('');
      return `
      <article class="intel-card brief-card">
        <header class="intel-card-head">
          <span class="intel-stamp-word">SECRET</span>
          <span class="intel-card-subtitle">– INTELLIGENCE BRIEF · ${window.escapeHtml(b.author || '')} · ${(b.created_at || '').slice(11, 16)}Z –</span>
        </header>
        <div class="intel-card-body">
          <p class="intel-line intel-brief-narrative">${narrative}</p>
          <p class="intel-meta">证据：<span data-evidence-links>${(b.new_evidence_ids || [])
            .map(id => `<button class="btn intel-ev-link" data-goto-evidence="${window.escapeHtml(id)}">${window.escapeHtml(id)}</button>`).join(' ') || '—'}</span></p>
          ${qs}
        </div>
      </article>`;
    }).join('');
    body.querySelectorAll('[data-goto-evidence]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.tab = 'EVIDENCE';
        this.renderDesk();
        const el = body.querySelector(`[data-evidence-id="${btn.dataset.gotoEvidence}"]`);
        if (el) el.scrollIntoView({ block: 'center' });
      });
    });
  }

  // ── EVIDENCE：已呈报证据链（M8.4.4）──
  renderEvidence(body) {
    const evidence = this.data.evidence || [];
    if (!evidence.length) {
      body.innerHTML = '<div class="intel-empty">无已呈报证据（证据随简报/标图呈报后可见）</div>';
      return;
    }
    body.innerHTML = evidence.slice().reverse().map(e => {
      const esc = window.escapeHtml;
      const usedBy = (e.used_by_assessment_ids || []).map(a =>
        `<button class="btn intel-ev-link" data-goto-brief="${esc(a)}">${esc(a)}</button>`).join(' ');
      const corr = (e.corroboration || []).length ? ` · 印证 ${esc(e.corroboration.join(','))}` : '';
      return `
      <article class="intel-card evidence-card" data-evidence-id="${esc(e.id)}">
        <header class="intel-card-head">
          <span class="intel-stamp-word ${e.status === 'active' ? '' : 'approved'}">${esc(e.status.toUpperCase())}</span>
          <span class="intel-card-subtitle">${esc(e.id)} · ${esc(e.source)}（${esc(e.source_type)}） · ${(e.received_at || '').slice(11, 16)}Z</span>
        </header>
        <div class="intel-card-body">
          <p class="intel-line">${esc(e.summary)}</p>
          <p class="intel-meta">使用该证据的判断：${usedBy || '—'}${corr}</p>
        </div>
      </article>`;
    }).join('');
    body.querySelectorAll('[data-goto-brief]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.tab = 'BRIEFS';
        this.renderDesk();
      });
    });
  }

  // ── 提案决议动作（S2 审批流保留）──
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

  // ── AFTER ACTION：证据—判断—批准 因果链复盘（UI.5 迁 LOG 后仍保留弹层）──
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
        <h3 class="aa-plot">PLOT ${window.escapeHtml(c.plot_id)} ${c.approved_state ? `· ${window.escapeHtml(c.approved_state)} v${c.current_version}` : '· 未上图'}</h3>
        <ol class="aa-steps">
          ${c.evidence.map(e => `<li class="aa-evidence"><b class="claim-fact">证据</b> ${window.escapeHtml(e.id)}（${window.escapeHtml(e.source)}，${window.escapeHtml(e.status)}）：${window.escapeHtml(e.summary)}</li>`).join('')}
          ${c.assessments.map(a => `<li class="aa-assessment"><b class="claim-judgment">判断</b> ${window.escapeHtml(a.id)}（${window.escapeHtml(a.author)}）：${window.escapeHtml(a.narrative)} <span class="aa-meta">骰子 ${window.escapeHtml((a.dice_record_ids || []).join(','))} 冲突 ${window.escapeHtml((a.conflict_ids || []).join(',') || '无')}</span></li>`).join('')}
          ${c.claims.map(cl => `<li class="aa-claim"><b class="claim-${window.escapeHtml(cl.type) === 'fact' ? 'fact' : window.escapeHtml(cl.type) === 'hypothesis' ? 'hyp' : 'judgment'}">${window.escapeHtml(cl.type)}</b> ${window.escapeHtml(cl.text)}</li>`).join('')}
          ${c.versions.map(v => `<li class="aa-proposal"><b>提案</b> v${v.version}（${window.escapeHtml(v.author)}）：${window.escapeHtml(v.change_summary)}${(v.annotations || []).map(an => ` <span class="aa-meta">批注 ${window.escapeHtml(an.by)}:${window.escapeHtml(an.note)}</span>`).join('')}</li>`).join('')}
          ${c.decisions.map(d => `<li class="aa-decision"><b>决议</b> ${window.escapeHtml(d.action)}（${window.escapeHtml(d.at || '')}）：${window.escapeHtml(d.comment || '')}</li>`).join('')}
        </ol>
      </section>`).join('')
      : '<p class="aa-empty">本局暂无标图链。</p>';
    const modal = document.getElementById('after-action');
    modal.querySelector('#aa-body').innerHTML = `
      ${chainHtml}
      <section class="aa-chain"><h3 class="aa-plot">推理工具调用（${tools.length}）</h3>
        ${tools.length ? `<ul>${tools.map(t => `<li class="aa-tool">${window.escapeHtml(t.actor)} → ${window.escapeHtml(t.tool)}（${window.escapeHtml((t.evidence_ids || []).join(', '))}）</li>`).join('')}</ul>` : '<p class="aa-empty">参谋未使用推理工具。</p>'}
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
