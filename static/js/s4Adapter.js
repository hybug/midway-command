/**
 * s4Adapter.js — S4 参谋班子与关系系统的前端契约适配器（S8_INTERFACE.md §四）。
 * S4 引擎已实施（src/staff/）：来访事件读取 /staff/visit-events（open 通知）；
 * 极简档案经 /staff/roster 与 /staff/channels 下发；UI 按「事件+自然语言摘要」
 * 渲染，不渲染关系数值/好感度/雷达图。
 * fixture 注入仅供测试/开发演示（installFixtures 后优先于真实数据源）。
 * D8：分歧案卷（ConflictDossier）属 v0 延期项——fetchConflictDossiers 恒为空。
 */
(function () {
  // 契约形状（运行时做形状校验）：
  // StaffVisitEvent  {actor_id, topic, at}
  // DossierSummary   {actor_id, status_line, current_focus, recent: [{at, kind, note}]}

  function asArray(v) { return Array.isArray(v) ? v : []; }

  let _fixtureVisits = [];
  let _fixtureConflicts = [];
  let _fixtureDossiers = [];

  function hasFixtures() {
    return _fixtureVisits.length || _fixtureConflicts.length || _fixtureDossiers.length;
  }

  const S4Adapter = {
    /** 参谋主动来访（STAFF_VISIT 通知源）：S4 后端 open 通知。 */
    async fetchVisitEvents() {
      if (_fixtureVisits.length) {
        return _fixtureVisits.map(v => this.sanitizeVisitEvent(v)).filter(Boolean);
      }
      try {
        const data = await fetch('/staff/visit-events').then(r => r.json());
        return asArray(data.visits).map(v => this.sanitizeVisitEvent(v)).filter(Boolean);
      } catch (e) { return []; }
    },

    /** 分歧案卷（CONFLICT 通知源）：v0 永久为空（延期接口，D8）。 */
    fetchConflictDossiers() {
      if (_fixtureConflicts.length) {
        return Promise.resolve(_fixtureConflicts.map(c => ({
          conflict_id: c.conflict_id, parties: c.parties || [],
          topic: String(c.topic || ''), at: String(c.at || ''),
        })));
      }
      return Promise.resolve([]);
    },

    /** 极简档案摘要（STAFF 右栏；正式数据在 /staff/roster，本方法仅供测试注入）。 */
    fetchDossierSummaries() {
      return Promise.resolve(_fixtureDossiers.map(d => this.sanitizeDossierSummary(d)).filter(Boolean));
    },

    /** fixture 注入（测试/开发桩；非玩法路径）。 */
    installFixtures({ visits = [], conflicts = [], dossiers = [] } = {}) {
      _fixtureVisits = visits.slice();
      _fixtureConflicts = conflicts.slice();
      _fixtureDossiers = dossiers.slice();
    },

    clearFixtures() {
      _fixtureVisits = []; _fixtureConflicts = []; _fixtureDossiers = [];
    },

    /** 玩家转述：AS.1/R3 已移除——恒为空（接口保留防旧调用崩溃）。 */
    fetchRelayRecords() {
      return Promise.resolve([]);
    },

    /** 形状守卫：S4 事件必须符合契约，否则丢弃（防脏数据入 UI）。 */
    sanitizeVisitEvent(v) {
      if (!v || typeof v.actor_id !== 'string') return null;
      return { actor_id: v.actor_id, topic: String(v.topic || ''), at: String(v.at || '') };
    },

    sanitizeDossierSummary(d) {
      if (!d || typeof d.actor_id !== 'string') return null;
      return {
        actor_id: d.actor_id,
        status_line: String(d.status_line || ''),
        current_focus: String(d.current_focus || ''),
        recent: asArray(d.recent).slice(0, 2),
      };
    },
  };

  window.S4Adapter = S4Adapter;
})();
