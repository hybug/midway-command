/**
 * commandDesk.js — S8 UI.1/M8.1 Commander Desk（L2 旗舰案卷台）。
 * 覆盖海图与底栏，保留 TOPBAR；打开/切换/关闭不推进游戏时间
 * （本模块不调用任何推进接口）；ESC 或「返回海图」关闭。
 * 工作台内路由：COMMS / INTEL / STAFF / LOG（CHART=关闭案卷台回海图）。
 * 来源上下文：记录打开来源（通知/工作台/海图），关闭时回调恢复视点。
 */
class CommanderDesk {
  constructor() {
    this.section = null;        // 当前工作台（null=关闭）
    this.openFrom = null;       // 来源上下文 {via, detail}
    this.sections = {};         // {COMMS: {mount(el), unmount()?}, ...}
    this.root = null;
    this.onSectionChange = null;
  }

  mount(rootId) {
    this.root = document.getElementById(rootId);
    if (!this.root) return;
    this.root.querySelectorAll('[data-desk-tab]').forEach(btn => {
      btn.addEventListener('click', () => this.switchSection(btn.dataset.deskTab));
    });
    const closeBtn = this.root.querySelector('#desk-close');
    if (closeBtn) closeBtn.addEventListener('click', () => this.close());
  }

  registerSection(name, view) {
    this.sections[name] = view;
  }

  isOpen() {
    return this.section !== null;
  }

  open(section, from) {
    if (!this.root) return;
    this.openFrom = from || this.openFrom;
    this.root.hidden = false;
    this.switchSection(section);
  }

  switchSection(section) {
    if (!this.sections[section]) return;
    this.section = section;
    this.root.querySelectorAll('[data-desk-tab]').forEach(btn => {
      const active = btn.dataset.deskTab === section;
      btn.classList.toggle('active', active);
    });
    const body = this.root.querySelector('#desk-body');
    if (body) {
      body.innerHTML = '';
      const view = this.sections[section];
      view.mount(body);
    }
    if (this.onSectionChange) this.onSectionChange(section);
  }

  close() {
    if (!this.root) return;
    const view = this.section ? this.sections[this.section] : null;
    if (view && view.unmount) view.unmount();
    this.root.hidden = true;
    this.section = null;
    if (this.onSectionChange) this.onSectionChange(null);
  }
}

window.CommanderDesk = CommanderDesk;
