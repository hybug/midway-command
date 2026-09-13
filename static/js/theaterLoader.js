/**
 * theaterLoader.js — 战区包加载器（CHART_SYSTEM.md §三：后端单一下发）
 *
 * TheaterLoader.load() → fetch('/theater')，返回 payload.theater 数据对象
 * （theaters/midway/theater.json 原样：view/graticule/range_rings/atoll/labels…）。
 *
 * 容错约定：网络失败 / 非 200 / 载荷缺 view → resolve(null)，不 reject——
 * chartRenderer 收到 null 时保持内置默认战区对象渲染（离线/后端不可达不白屏，
 * 内置默认与战区包同值，test_ui_assets.py 断言锚点）。
 */
(function () {
  'use strict';

  const TheaterLoader = {
    async load() {
      try {
        const res = await fetch('/theater', { headers: { 'Content-Type': 'application/json' } });
        if (!res.ok) return null;
        const payload = await res.json();
        const theater = payload && payload.theater;
        // O.3：地理层（GeoJSON FeatureCollection）随包附加在战区对象上——
        // chartRenderer drawGeography 消费；离线兜底（无 geography）行为不变
        if (theater && theater.view && payload.geography) {
          theater.geography = payload.geography;
        }
        return theater && theater.view ? theater : null;
      } catch (err) {
        return null; // 离线/后端不可达：交由 chartRenderer 内置默认兜底
      }
    },
  };

  window.TheaterLoader = TheaterLoader;
})();
