/**
 * ordersDesk.js — S5.6 ISSUE ORDER 类型化命令面板（M8.7.6 升级）。
 * 纪律（S5 计划）：
 * - 命令类型/目标/参数全部来自后端目录（/orders/catalog），前端不硬编码动作。
 * - 自然语言只能生成可编辑草稿（POST /orders/draft），确认后才签发。
 * - commander_intent_text 必填；签发需明确确认；冲突不静默覆盖（409 → 展示新旧参数）。
 * - 玩家只看 reported_status（status_visible）；执行经 Pipeline 异步生效。
 */
class OrdersDesk {
  constructor() {
    this.catalog = [];
    this.orders = [];
    this.taskForces = [];
    this.selectedType = 'SET_COURSE';
    this.conflict = null;       // {draftId, active_order}
    this.el = null;
  }

  mount(elId) {
    this.el = document.getElementById(elId);
    if (this.el) this.refresh(true);
  }

  async refresh(force) {
    if (!this.el || typeof fetch !== 'function') return;
    if (!force && this.catalog.length) return;
    try {
      const [cat, list, state] = await Promise.all([
        fetch('/orders/catalog').then(r => r.json()).catch(() => null),
        fetch('/orders').then(r => r.json()).catch(() => null),
        fetch('/state').then(r => r.json()).catch(() => null),
      ]);
      this.catalog = (cat && cat.actions) || [];
      this.orders = (list && list.orders) || [];
      this.taskForces = ((state && state.task_forces) || []).map(t => t.name);
    } catch (e) { /* 维持空态 */ }
    this.render();
  }

  render() {
    if (!this.el) return;
    const esc = window.escapeHtml;
    const typeOptions = this.catalog.map(a => `
      <option value="${esc(a.action_type)}"${a.action_type === this.selectedType ? ' selected' : ''}>
        ${esc(a.label)}</option>`).join('');
    const targetOptions = this.taskForces.map(tf =>
      `<option value="${esc(tf)}">${esc(tf)}</option>`).join('');
    this.el.innerHTML = `
      <p class="io-section-title">正式命令（S5 ORDER）——类型化表单，签发后经通信链与管线生效</p>
      <div class="io-form">
        <label>命令类型
          <select id="ord-type" data-action="select-order-type">${typeOptions}</select>
        </label>
        <label>目标
          <select id="ord-target">${targetOptions}</select>
        </label>
        <div id="ord-params">${this.paramFields(this.selectedType)}</div>
        <label>指挥官意图（必填，原文留档）
          <textarea id="ord-intent" rows="2" placeholder="为什么下这道命令…"></textarea>
        </label>
        <label>优先级
          <select id="ord-priority">
            <option value="routine">ROUTINE</option>
            <option value="urgent">URGENT</option>
            <option value="flash">FLASH</option>
          </select>
        </label>
        <button class="btn btn-execute" id="ord-create" data-action="create-order-draft">创建草稿</button>
      </div>
      <div class="io-nl">
        <p class="io-section-title">自然语言 → 草稿（不直接执行）</p>
        <textarea id="ord-nl" rows="2" placeholder="例：航向 095，另派 4 架侦察机向西北搜索 200 海里"></textarea>
        <button class="btn" id="ord-nl-draft" data-action="nl-draft">生成草稿</button>
      </div>
      <div id="ord-drafts"></div>
      <div id="ord-conflict"></div>
      <p class="io-section-title">在案命令（玩家可见状态）</p>
      <ol class="io-orders" id="ord-list">
        ${this.orders.length ? this.orders.map(o => `
          <li class="io-order io-order-${esc(o.status_visible)}">
            <span class="io-order-id">${esc(o.order_id)}</span>
            <span class="io-order-type">${esc(o.order_type)}</span>
            <span class="io-order-status">${esc(o.status_visible).toUpperCase()}</span>
            <span class="io-order-intent">${esc((o.intent || '').slice(0, 40))}</span>
          </li>`).join('') : '<li class="comms-empty">暂无命令</li>'}
      </ol>`;
    this.bind();
  }

  paramFields(type) {
    if (type === 'SET_COURSE') {
      return `<label>航向（0-359，EXACT）
        <input type="number" id="ord-course" min="0" max="359" value="125"></label>`;
    }
    return `
      <label>侦察目的<input type="text" id="ord-objective" placeholder="确认米西马方向接触"></label>
      <label>搜索区域<input type="text" id="ord-area" placeholder="西北 200nm"></label>
      <label>最大半径（海里）<input type="number" id="ord-range" min="50" max="400" value="200"></label>
      <label>时间窗<input type="text" id="ord-window" placeholder="上午"></label>`;
  }

  bind() {
    if (!this.el) return;
    const esc = window.escapeHtml;
    const typeSel = this.el.querySelector('#ord-type');
    if (typeSel) typeSel.addEventListener('change', () => {
      this.selectedType = typeSel.value;
      const box = this.el.querySelector('#ord-params');
      if (box) box.innerHTML = this.paramFields(this.selectedType);
    });
    const create = this.el.querySelector('#ord-create');
    if (create) create.addEventListener('click', () => this.createDraft());
    const nl = this.el.querySelector('#ord-nl-draft');
    if (nl) nl.addEventListener('click', async () => {
      const text = (this.el.querySelector('#ord-nl').value || '').trim();
      if (!text) { if (window.ui) window.ui.showNotification('请输入命令文本'); return; }
      try {
        const data = await this._post('/orders/draft', { text });
        this._drafts = data.drafts || [];
        if (window.ui) window.ui.showNotification(`已生成 ${this._drafts.length} 份草稿（未签发）`);
        this.renderDrafts();
      } catch (e) { if (window.ui) window.ui.showNotification('❌ ' + e.message); }
    });
    this.renderDrafts();
  }

  renderDrafts() {
    const box = this.el && this.el.querySelector('#ord-drafts');
    if (!box) return;
    const esc = window.escapeHtml;
    const drafts = this._drafts || [];
    box.innerHTML = drafts.length ? `
      <p class="io-section-title">待确认草稿（确认前不生效）</p>
      ${drafts.map(d => `
        <div class="io-draft" data-draft-id="${esc(d.id)}">
          <span class="io-order-type">${esc(d.order_type)}</span>
          <span class="io-order-intent">${esc(JSON.stringify(d.parameters))}</span>
          <span class="io-order-status">${esc((d.commander_intent_text || '').slice(0, 30))}</span>
          <button class="btn btn-execute" data-action="issue-order" data-draft-id="${esc(d.id)}">确认签发</button>
        </div>`).join('')}` : '';
    box.querySelectorAll('[data-action="issue-order"]').forEach(btn => {
      btn.addEventListener('click', () => this.issue(btn.dataset.draftId));
    });
  }

  async createDraft() {
    if (!this.el) return;
    const type = this.el.querySelector('#ord-type').value;
    const target = [this.el.querySelector('#ord-target').value];
    const intent = (this.el.querySelector('#ord-intent').value || '').trim();
    if (!intent) { if (window.ui) window.ui.showNotification('指挥官意图必填'); return; }
    let parameters = {};
    if (type === 'SET_COURSE') {
      parameters = { course: parseInt(this.el.querySelector('#ord-course').value, 10) };
    } else {
      parameters = {
        search_objective: this.el.querySelector('#ord-objective').value.trim(),
        search_area: this.el.querySelector('#ord-area').value.trim(),
        max_range_nm: parseInt(this.el.querySelector('#ord-range').value, 10),
        time_window: this.el.querySelector('#ord-window').value.trim(),
        constraints: [],
      };
    }
    const priority = this.el.querySelector('#ord-priority').value;
    try {
      const data = await this._post('/orders', {
        order_type: type, target_refs: target, parameters,
        commander_intent_text: intent, authority_mode:
          type === 'SET_COURSE' ? 'exact' : 'intent',
        priority,
      });
      this._drafts = [data.order];
      if (window.ui) window.ui.showNotification('草稿已创建（确认前不生效）');
      this.renderDrafts();
    } catch (e) { if (window.ui) window.ui.showNotification('❌ ' + e.message); }
  }

  async issue(orderId, supersedeIds) {
    // 明确确认（AS：状态改变动作必须二次确认）
    if (!window.confirm('确认签发该命令？签发后不可原地修改，将经通信链传达。')) return;
    try {
      const data = await this._post(`/orders/${orderId}/issue`,
                                     { supersede_ids: supersedeIds || [] });
      this._drafts = [];
      this.conflict = null;
      if (window.ui) window.ui.showNotification(`命令 ${data.order.id} 已签发（经 S2 传达）`);
      await this.refresh(true);
    } catch (e) {
      // 409 冲突：展示在位命令新旧参数，由指挥官决断（不静默覆盖）
      let detail = e.message;
      try { detail = JSON.parse(e.message); } catch (_) {}
      if (detail && detail.active_order) {
        this.conflict = { draftId: orderId, active: detail.active_order };
        this.renderConflict();
        return;
      }
      if (window.ui) window.ui.showNotification('❌ ' + detail);
    }
  }

  renderConflict() {
    const box = this.el && this.el.querySelector('#ord-conflict');
    if (!box || !this.conflict) return;
    const esc = window.escapeHtml;
    const a = this.conflict.active;
    box.innerHTML = `
      <div class="io-conflict">
        <p class="io-section-title">⚠ 与在位命令冲突（不静默覆盖）</p>
        <p class="io-order-intent">在位：${esc(a.id)} ${esc(a.order_type)}
          ${esc(JSON.stringify(a.parameters))}（${esc(a.status)}）</p>
        <button class="btn btn-execute" data-action="supersede-order"
          data-draft-id="${esc(this.conflict.draftId)}"
          data-active-id="${esc(a.id)}">以新命令替代旧命令</button>
        <button class="btn" data-action="drop-conflict">放弃新命令</button>
      </div>`;
    box.querySelector('[data-action="supersede-order"]').addEventListener('click', (ev) => {
      const draftId = ev.target.dataset.draftId;
      const activeId = ev.target.dataset.activeId;
      box.innerHTML = '';
      this.issue(draftId, [activeId]);
    });
    box.querySelector('[data-action="drop-conflict"]').addEventListener('click', () => {
      this.conflict = null;
      box.innerHTML = '';
    });
  }

  async _post(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(typeof err.detail === 'string'
        ? err.detail : JSON.stringify(err.detail));
    }
    return res.json();
  }
}

window.OrdersDesk = OrdersDesk;
