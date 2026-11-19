"""指挥室产品界面：真实 JS 行为与页面接线回归。

历史像素复刻 fixture 保留原样；正式页面另用产品层样式。
"""
import subprocess
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_product_page_loads_readability_layer_and_labels_dialog():
    page = Page((ROOT / "static/index.html").read_text())
    styles = [attrs["href"].split("?")[0] for tag, attrs in page.elements
              if tag == "link" and attrs.get("rel") == "stylesheet"]
    assert styles[-1] == "/static/css/command-room.css"
    by_id = {attrs["id"]: attrs for _, attrs in page.elements if "id" in attrs}
    assert by_id["issue-order-modal"]["role"] == "dialog"
    assert by_id["issue-order-modal"]["aria-labelledby"] == "issue-order-title"
    assert "issue-order-title" in by_id
    assert by_id["workbench-nav"]["aria-label"] == "工作台导航"


def test_navigation_is_named_and_empty_state_does_not_claim_safety():
    script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const nodes = {
  'workbench-nav': {innerHTML: '', children: [], appendChild(b) {this.children.push(b)}},
  'duty-summary': {innerHTML: '', querySelector() {return null}}
};
const document = {
  getElementById: id => nodes[id] || null,
  createElement: () => ({
    dataset: {}, attrs: {}, listeners: {},
    setAttribute(k,v) {this.attrs[k]=String(v)},
    addEventListener(k,v) {this.listeners[k]=v}
  })
};
const ctx = {document, window: {}, console};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('static/js/uiController.js','utf8'),ctx);
vm.runInContext(`
  const ui = new UIController();
  ui.renderWorkbenchNav('INTEL', {INTEL: 2}, id => window.chosen = id);
  ui.renderDutySummary({section:'CHART', notifications:null, latest:null,
                       onOpenDesk:()=>{}});
`, ctx);
const buttons=nodes['workbench-nav'].children;
assert.equal(buttons.length,5);
assert(buttons[2].innerHTML.includes('情报'));
assert.equal(buttons[2].attrs['aria-current'],'page');
assert.equal(buttons[2].attrs['aria-label'],'情报工作台，2 条未读');
buttons[3].listeners.click();
assert.equal(ctx.window.chosen,'STAFF');
const empty=nodes['duty-summary'].innerHTML;
assert(!empty.includes('ALL CLEAR'),'没有待办不等于战场安全');
assert(empty.includes('尚无已呈报情报'));
vm.runInContext(`
 ui.renderDutySummary({section:'CHART', notifications:null,
   latest:{kind:'REPORT',text:'<img src=x onerror=alert(1)>'}, onOpenDesk:()=>{}});
`,ctx);
assert(!nodes['duty-summary'].innerHTML.includes('<img src=x'));
assert(nodes['duty-summary'].innerHTML.includes('&lt;img'));
console.log('COMMAND ROOM PASS');
"""
    _run_node(script)


def test_time_advance_has_pending_feedback_and_ignores_duplicate_clicks():
    script = r"""
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const button={disabled:false,textContent:'推进时间 +15 分钟',attrs:{},
 setAttribute(k,v){this.attrs[k]=String(v)},removeAttribute(k){delete this.attrs[k]}};
const ctx={console,window:{},document:{
 addEventListener(){},getElementById(id){return id==='btn-advance'?button:null}
}};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('static/js/main.js','utf8'),ctx);
(async()=>{
 let finish,calls=0;
 ctx.testApi=()=>{calls++;return new Promise(resolve=>{finish=resolve})};
 ctx.window.testApi=ctx.testApi;
 vm.runInContext(`
  api=window.testApi; gameState={ap:{}};
  ui={renderDashboard(){},showNotification(){}};
  loadState=async()=>{};
 `,ctx);
 const first=vm.runInContext('advance()',ctx);
 assert(button.disabled);
 assert.equal(button.attrs['aria-busy'],'true');
 assert(button.textContent.includes('推进中'));
 await vm.runInContext('advance()',ctx);
 assert.equal(calls,1);
 finish({ap:{},notifications:[],game_over:false});
 await first;
 assert.equal(button.disabled,false);
 assert.equal(button.textContent,'推进时间 +15 分钟');
 assert(!('aria-busy' in button.attrs));
 console.log('COMMAND ROOM PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    _run_node(script)


def _run_node(script: str) -> None:
    result = subprocess.run(["node", "-e", script], cwd=ROOT, text=True,
                            capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "COMMAND ROOM PASS" in result.stdout
