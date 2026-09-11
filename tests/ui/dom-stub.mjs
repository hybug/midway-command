/** 最小 DOM/Canvas2D 桩 + 录制器（批次 C3）。
 *  ctx 的一切方法调用与属性赋值都被记录进 __calls，供断言「画在哪里、画了什么」。 */
import { readFileSync } from "node:fs";
import * as vm from "node:vm";

export function makeRecorderCtx(width = 1440, height = 900) {
  const calls = [];
  const ctx = {
    __calls: calls,
    canvas: { width, height },
    measureText: (t) => ({ width: String(t ?? " ").length * 6 }),
    createPattern: () => ({ __pattern: true }),
  };
  return new Proxy(ctx, {
    get(t, prop) {
      if (prop in t) return t[prop];
      t[prop] = (...args) => { calls.push({ name: String(prop), args }); return undefined; };
      return t[prop];
    },
    set(t, prop, value) {
      calls.push({ name: `set:${String(prop)}`, args: [value] });
      // 值同时存 t[prop]：get 陷阱 `prop in t` 命中后原样回读（ctx.fillStyle 等属性赋值可读回）；
      // 旧实现存 t[`set:${prop}`] 键名错位，回读永远 undefined。calls 记录行为不变。
      t[prop] = value;
      return true;
    },
  });
}

export function makeStubDocument() {
  const canvases = {};
  return {
    canvases,
    getElementById(id) {
      if (!canvases[id]) {
        const ctx = makeRecorderCtx();
        canvases[id] = {
          id, width: 1440, height: 900, clientWidth: 1440, clientHeight: 900,
          // 桩迭代：mapRenderer.resize() 读 parentElement.clientWidth/Height（浏览器中真实 canvas 必有父节点）
          parentElement: { clientWidth: 1440, clientHeight: 900 },
          getContext: () => ctx, __ctx: ctx, style: {},
          addEventListener: () => {},
          getBoundingClientRect: () => ({ left: 0, top: 0, width: 1440, height: 900 }),
        };
      }
      return canvases[id];
    },
    addEventListener: () => {},
  };
}

export function loadGameScripts(paths) {
  const document = makeStubDocument();
  const sandbox = {
    document, console,
    performance: { now: () => 0 },
    requestAnimationFrame: () => 0,
    setTimeout: () => 0, setInterval: () => 0, clearInterval: () => {},
  };
  sandbox.window = sandbox; sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  for (const p of paths) vm.runInContext(readFileSync(p, "utf8"), sandbox, { filename: p });
  return { sandbox, document };
}
