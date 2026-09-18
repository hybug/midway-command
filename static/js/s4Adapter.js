/**
 * s4Adapter.js — S4 参谋班子与关系系统的前端契约适配器（S8_INTERFACE.md §四）。
 * S4 引擎未实施：本适配器固定事件形状并在无后端时返回空集合——
 * UI 一律按「事件 + 自然语言摘要」消费，不渲染关系数值/好感度/雷达图。
 * S4 落地后仅需让本适配器读取真实事件源，UI 不改。
 */
(function () {
  // 契约形状（仅注释级契约，运行时做形状校验）：
  // StaffVisitEvent  {actor_id, topic, at}
  // RelayRecord      {from_actor, to_actor, summary, at}
  // DossierSummary   {actor_id, status_line, current_focus, recent: [{at, kind, note}]}
  // ConflictDossier  {conflict_id, parties: [], topic, at}

  function asArray(v) { return Array.isArray(v) ? v : []; }

  // S4 引擎未实施：事件桩（fixture）仅供测试/开发演示——
  // installFixtures 后 fetch* 返回注入的事件，UI 按「事件+自然语言摘要」渲染。
  let _fixtureVisits = [];
  let _fixtureConflicts = [];
  let _fixtureDossiers = [];

  const S4Adapter = {
    /** 参谋主动来访（STAFF_VISIT 通知源）。 */
    fetchVisitEvents() {
      return Promise.resolve(_fixtureVisits.map(v => this.sanitizeVisitEvent(v)).filter(Boolean));
    },

    /** 分歧案卷（CONFLICT 通知源）。 */
    fetchConflictDossiers() {
      return Promise.resolve(_fixtureConflicts.map(c => ({
        conflict_id: c.conflict_id, parties: c.parties || [],
        topic: String(c.topic || ''), at: String(c.at || ''),
      })));
    },

    /** 极简档案摘要（STAFF 右栏；无数据回退到名册静态职责行）。 */
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

    /** 玩家转述记录（UI.6 接入转述链时的数据形状）。 */
    fetchRelayRecords() {
      return Promise.resolve([]);
    },

    /** 形状守卫：S4 落地后事件必须符合契约，否则丢弃（防脏数据入 UI）。 */
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
