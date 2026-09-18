/**
 * notificationCenter.js — S8 UI.1/M8.7 通知中心
 * 分级：INFO/ROUTINE/URGENT/FLASH/STAFF_VISIT/CONFLICT（S8_INTERFACE.md §二）。
 * 行为纪律：只有 FLASH 与 STAFF_VISIT 主动打断（toast）；其余只更新角标与待处理队列。
 * 已读/已处理/暂缓分别记录；打开案卷台不推进时间（本模块不调用 /advance）。
 * 数据源：/intel/work-items、/intel/inbox、/intel/plots（全部玩家白名单接口）；
 * STAFF_VISIT/CONFLICT 事件经 s4Adapter（S4 未实施时为空）。
 */
class NotificationCenter {
  constructor() {
    this.items = [];            // {id, level, workbench, text, at, source, read, deferred}
    this.counters = { CHART: 0, COMMS: 0, INTEL: 0, STAFF: 0, LOG: 0 };
    this.onToast = null;        // (item) => void   仅 FLASH/STAFF_VISIT 回调
    this.onChange = null;       // () => void       角标/队列刷新
    this._seen = new Set();     // 已登记来源 id（防重复登记）
  }

  // ── 登记与维护 ──

  push(item) {
    if (!item || !item.id || this._seen.has(item.id)) return null;
    this._seen.add(item.id);
    const full = {
      level: 'INFO', workbench: 'CHART', text: '', at: '',
      source: '', read: false, deferred: false,
      interrupt: false, ...item,
    };
    full.interrupt = full.level === 'FLASH' || full.level === 'STAFF_VISIT';
    this.items.push(full);
    if (!full.read) this.counters[full.workbench] = (this.counters[full.workbench] || 0) + 1;
    if (full.interrupt && !full.read && this.onToast) this.onToast(full);
    if (this.onChange) this.onChange();
    return full;
  }

  markRead(id) {
    const item = this.items.find(i => i.id === id);
    if (item && !item.read) {
      item.read = true;
      this.counters[item.workbench] = Math.max(0, (this.counters[item.workbench] || 0) - 1);
      if (this.onChange) this.onChange();
    }
  }

  defer(id) {
    const item = this.items.find(i => i.id === id);
    if (item) {
      item.deferred = true;
      if (!item.read) {
        item.read = true;
        this.counters[item.workbench] = Math.max(0, (this.counters[item.workbench] || 0) - 1);
      }
      if (this.onChange) this.onChange();
    }
  }

  // 最高优先级事项（URGENT > FLASH > CONFLICT > STAFF_VISIT > ROUTINE > INFO）
  topPriority() {
    const rank = { 'FLASH': 0, 'URGENT': 1, 'CONFLICT': 2, 'STAFF_VISIT': 3, 'ROUTINE': 4, 'INFO': 5 };
    const open = this.items.filter(i => !i.read && !i.deferred);
    return open.sort((a, b) => (rank[a.level] ?? 9) - (rank[b.level] ?? 9))[0] || null;
  }

  pendingQueue() {
    return this.items.filter(i => !i.read && !i.deferred && i.level !== 'INFO');
  }

  // ── 从白名单接口聚合（main.js 每 tick 调用）──

  refreshFromIntel(plotsData, inbox, workItems, visitEvents, conflictEvents) {
    // URGENT：待研判工作项（INTEL）
    (workItems || []).filter(w => w.priority === 'urgent').forEach(w => {
      this.push({ id: `wu:${w.id}`, level: 'URGENT', workbench: 'INTEL',
        text: `待研判工作项 ${w.id}（${w.priority}）`, at: w.created_at || '',
        source: 'work-item' });
    });
    // FLASH：加急电文（COMMS）
    (inbox || []).filter(m => m.priority === 'flash').forEach(m => {
      this.push({ id: `msg:${m.id}`, level: 'FLASH', workbench: 'COMMS',
        text: `FLASH 电文 ${m.sender || m.id}`, at: m.received_at || '',
        source: 'message' });
    });
    // URGENT：待批准标图（INTEL）
    const pending = ((plotsData || {}).pending_proposals || []);
    pending.forEach(p => {
      this.push({ id: `plot:${p.id}`, level: 'URGENT', workbench: 'INTEL',
        text: `标图提案待批 ${p.plot_id} v${p.version}`, at: p.created_at || '',
        source: 'plot' });
    });
    // STAFF_VISIT / CONFLICT：S4 适配器（v0 空实现）
    (visitEvents || []).forEach(v => this.push({
      id: `visit:${v.actor_id}:${v.at}`, level: 'STAFF_VISIT', workbench: 'STAFF',
      text: `${v.actor_id} 请求入舱：${v.topic || ''}`, at: v.at || '',
      source: 's4' }));
    (conflictEvents || []).forEach(c => this.push({
      id: `conflict:${c.conflict_id}`, level: 'CONFLICT', workbench: 'STAFF',
      text: `参谋分歧：${c.topic || c.conflict_id}`, at: c.at || '',
      source: 's4' }));
  }
}

window.NotificationCenter = NotificationCenter;
