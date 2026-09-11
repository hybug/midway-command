/**
 * SVG Icon Loader for Canvas rendering
 * Converts SVG files to Image objects for use in Canvas
 */

const SVG_ICONS = {
  carrier_us: `<svg viewBox="0 0 1024 559" xmlns="http://www.w3.org/2000/svg">
    <path d="M 558,142 L 558,146 L 562,146 L 562,149 L 561,147 L 558,148 L 558,154 L 563,155 L 558,156 L 560,184 L 574,183 L 575,177 L 569,175 L 570,162 L 586,162 L 586,175 L 583,175 L 586,175 L 585,172 L 580,172 L 579,179 L 582,184 L 588,185 L 572,191 L 574,198 L 580,196 L 578,192 L 584,192 L 581,194 L 581,197 L 584,198 L 573,202 L 575,226 L 577,228 L 587,228 L 588,222 L 594,222 L 593,211 L 596,211 L 598,207 L 596,204 L 595,208 L 594,205 L 603,200 L 603,205 L 598,205 L 602,211 L 606,212 L 606,218 L 603,221 L 605,223 L 616,223 L 619,217 L 619,226 L 631,229 L 629,239 L 634,240 L 634,249 L 626,250 L 626,273 L 628,275 L 635,274 L 635,262 L 640,261 L 640,251 L 652,253 L 655,256 L 669,255 L 655,258 L 656,262 L 660,262 L 660,273 L 662,275 L 669,273 L 669,265 L 702,267 L 688,269 L 690,275 L 958,275 L 966,278 L 966,280 L 946,283 L 944,285 L 943,302 L 947,304 L 949,300 L 957,300 L 959,297 L 954,296 L 953,293 L 960,291 L 963,293 L 977,292 L 966,293 L 962,299 L 978,304 L 962,331 L 956,357 L 91,357 L 75,350 L 64,338 L 59,324 L 59,317 L 65,315 L 64,311 L 50,309 L 64,310 L 71,307 L 74,309 L 74,312 L 69,315 L 80,317 L 80,288 L 78,286 L 60,286 L 45,282 L 45,278 L 50,278 L 53,275 L 376,275 L 379,271 L 378,269 L 365,267 L 380,267 L 381,265 L 398,265 L 398,274 L 403,275 L 404,269 L 407,267 L 357,227 L 354,227 L 354,244 L 356,247 L 353,248 L 356,246 L 353,242 L 355,223 L 360,226 L 380,229 L 360,227 L 395,251 L 407,265 L 409,264 L 413,239 L 411,235 L 407,235 L 414,236 L 418,267 L 423,269 L 424,275 L 430,273 L 430,262 L 434,262 L 435,258 L 421,255 L 434,256 L 448,251 L 450,251 L 450,261 L 455,262 L 455,274 L 462,275 L 463,247 L 453,242 L 453,236 L 458,236 L 458,229 L 463,227 L 464,222 L 461,223 L 461,217 L 469,222 L 469,225 L 468,222 L 466,223 L 466,227 L 471,229 L 471,236 L 482,235 L 482,213 L 476,209 L 481,209 L 482,203 L 488,201 L 488,192 L 475,179 L 488,190 L 488,165 L 489,202 L 501,203 L 503,195 L 510,195 L 512,203 L 514,201 L 514,192 L 520,191 L 521,201 L 529,203 L 531,201 L 531,181 L 531,201 L 536,202 L 537,207 L 541,208 L 537,212 L 537,227 L 542,228 L 544,226 L 541,222 L 542,216 L 551,216 L 552,222 L 549,226 L 551,228 L 557,226 L 564,198 L 559,189 L 552,186 L 554,178 L 554,183 L 557,183 L 558,156 L 553,155 L 558,154 L 558,148 L 554,148 L 554,145 L 557,147 L 558,143 Z" fill="#2a2218" fill-rule="evenodd"/>
  </svg>`,

  aircraft_topdown: `<svg viewBox="0 0 158 115" xmlns="http://www.w3.org/2000/svg">
    <path d="M 71,5 L 73,5 L 72,8 L 76,12 L 76,26 L 78,28 L 84,29 L 85,22 L 87,19 L 89,22 L 89,28 L 91,30 L 100,30 L 102,28 L 102,23 L 104,22 L 107,31 L 136,33 L 138,34 L 138,39 L 135,41 L 92,45 L 88,47 L 78,47 L 76,49 L 75,80 L 91,85 L 93,86 L 93,89 L 75,91 L 73,93 L 73,96 L 71,96 L 69,91 L 52,89 L 52,85 L 69,80 L 68,49 L 62,46 L 56,47 L 44,44 L 9,41 L 6,39 L 5,36 L 9,33 L 37,31 L 40,22 L 42,23 L 41,24 L 43,30 L 54,29 L 56,20 L 58,20 L 60,29 L 66,28 L 68,10 L 72,6 Z" fill="#2a2218" fill-rule="evenodd"/>
  </svg>`,
};

// 光栅图标（Phase 6 治理产物，docs/plans/ui-replication-plan.md）
// 注：内联 SVG_ICONS 已有矢量 aircraft_topdown，光栅版改名 _raster 避免覆盖
const ICON_FILES = {
  fleet_tag_ent: '/static/assets/ui/icons/fleet_tag_ent.png',
  fleet_tag_hor: '/static/assets/ui/icons/fleet_tag_hor.png',
  fleet_tag_cv: '/static/assets/ui/icons/fleet_tag_cv.png',
  fleet_tag_bb: '/static/assets/ui/icons/fleet_tag_bb.png',
  enemy_tag_q: '/static/assets/ui/icons/enemy_tag_q.png',
  aircraft_topdown_raster: '/static/assets/ui/icons/aircraft_topdown.png',
  compass_raster: '/static/assets/ui/icons/compass_raster.png',
  // 保真度修正 B3：AI 雕刻罗盘（docs/assets/cut_compass.py 亮度反转抠图，细阴线完整）
  compass_engraved: '/static/assets/ui/icons/compass_engraved.png',
  // 设计图资产文件（docs/plans/ui-replication-plan.md Phase 2–5）
  paper_base: '/static/assets/ui/paper_base.svg',
  noise: '/static/assets/ui/noise.svg',
  vignette: '/static/assets/ui/vignette.svg', // 已由 Loop1 CSS 渐变取代，保留为回退
  light_falloff: '/static/assets/ui/light_falloff.svg',
  scratches: '/static/assets/ui/scratches.svg',
  compass: '/static/assets/ui/compass.svg',
  enemy_marker: '/static/assets/ui/enemy_marker.svg',
  secret_stamp: '/static/assets/ui/secret_stamp.svg',
  // 保真度修正 B1：AI 旧纸纹理（docs/assets/normalize_texture.py 归一产物，Canvas repeat 平铺）
  paper_tex: '/static/assets/textures/paper_tex.jpg?v=1780997997',
};

let iconsLoaded = false;
const loadedIcons = {};

async function loadSVGIcons() {
  if (iconsLoaded) return;
  const jobs = [];
  const failSoft = (name, err) => {
    console.warn(`svgLoader: ${name} 加载失败`, err);
    return null; // 不写入 loadedIcons，整体不 reject
  };
  for (const [name, svgString] of Object.entries(SVG_ICONS)) {
    jobs.push(svgToImage(svgString)
      .then((img) => { loadedIcons[name] = img; })
      .catch((err) => failSoft(name, err)));
  }
  for (const [name, url] of Object.entries(ICON_FILES)) {
    jobs.push(loadIconFromUrl(name, url)
      .then((img) => { loadedIcons[name] = img; })
      .catch((err) => failSoft(name, err)));
  }
  await Promise.all(jobs);
  iconsLoaded = true;
}

function svgToImage(svgString) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgString);
  });
}

async function svgFromUrl(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`icon load failed: ${url} -> ${res.status}`);
  return svgToImage(await res.text());
}

async function loadIconFromUrl(name, url) {
  if (url.endsWith('.svg')) return svgFromUrl(url);
  // PNG：直接用 URL 作为 Image src
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}

function getIcon(name) {
  return loadedIcons[name] || null;
}

window.loadSVGIcons = loadSVGIcons;
window.getIcon = getIcon;
