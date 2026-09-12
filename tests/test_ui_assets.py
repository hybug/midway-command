"""UI 设计图复刻守卫测试。

校验 docs/plans/ui-replication-plan.md 定义的资产文件、设计 token、
页面结构与渲染器常量的静态一致性。前端无 JS 测试运行器，
本文件是 UI 复刻的自动化回归防线。
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
UI = BASE / "static" / "assets" / "ui"

# 设计图 15 项资产 → (文件名, 必含内容关键字)
# A1 地图主图为 chartRenderer.js 程序化绘制，由 test_chart_renderer_* 单独守卫。
ASSET_MANIFEST = {
    "A2_paper_base":     ("paper_base.svg",     ["feTurbulence", "#f5edd6"]),
    "A3_vignette":       ("vignette.svg",       ["radialGradient"]),
    "A4_noise":          ("noise.svg",          ["feTurbulence", "fractalNoise"]),
    "A5_enemy_marker":   ("enemy_marker.svg",   ["#8b2500", "ENEMY"]),
    "A6_compass":        ("compass.svg",        [">N<", ">E<", ">S<", ">W<"]),
    "A7_secret_stamp":   ("secret_stamp.svg",   ["#c0392b", "SECRET"]),
    "A8_paper_note":     ("paper_note.svg",     ["feTurbulence"]),
    "A9_tab_bg":         ("tab_bg.svg",         ["viewBox"]),
    "A10_intel_card_l":  ("intel_card_light.svg", ["viewBox"]),
    "A10_intel_card_d":  ("intel_card_dark.svg",  ["viewBox"]),
    "A11_topbar_bg":     ("topbar_bg.svg",      ["viewBox", "#f5edd6"]),
    "A12_light_falloff": ("light_falloff.svg",  ["radialGradient"]),
    "A13_scratches":     ("scratches.svg",      ["stroke"]),
    "A14_ruler":         ("ruler.svg",          ["viewBox"]),
    "A15_pencil":        ("pencil.svg",         ["viewBox"]),
    "EX_flag48":         ("flag48.svg",         ["viewBox"]),
    "B1_gear":           ("gear.svg",           ["viewBox"]),  # 成品图复现 E4：顶栏齿轮（8 齿，ink 色）
}

CSS_TOKENS = {
    "--color-desk": "#3a2518",
    "--color-desk-light": "#4a3528",
    "--color-paper-base": "#f5edd6",
    "--color-paper-dark": "#e8dcc8",
    "--color-paper-edge": "#d4c8a8",
    "--color-ink-main": "#2a2218",
    "--color-ink-fade": "#6b5d4a",
    "--color-ink-faint": "#a89878",
    "--color-enemy-red": "#8b2500",
    "--color-secret-red": "#c0392b",
    "--color-grid-line": "rgba(160,140,110,0.35)",
    "--color-lagoon": "#b8d4c8",
    "--color-reef": "#8aaa98",
    "--color-sand": "#d4c4a0",
    "--color-eastern": "#c8b890",
    # 成品图复现 E1：chrome token 组（底栏深棕黑底 / 底栏浅字 / 损伤橙红，采样成品图底栏）
    "--color-bar-dark": "#332a20",
    "--color-bar-text": "#d8cbb2",
    "--color-damage": "#c25b3a",
    "--font-handwriting": "'Caveat', cursive",
    "--font-typewriter": "'Special Elite', monospace",
}


def test_asset_manifest_complete():
    missing = [name for name, (f, _) in ASSET_MANIFEST.items() if not (UI / f).exists()]
    assert missing == [], f"缺少资产文件: {missing}"


def test_assets_are_valid_svg_with_required_content():
    for name, (fname, keywords) in ASSET_MANIFEST.items():
        path = UI / fname
        if not path.exists():
            continue  # 缺失由 test_asset_manifest_complete 报告
        ET.parse(path)  # XML 必须合法
        for kw in keywords:
            assert kw in path.read_text(), f"{name}: {fname} 缺少关键字 {kw}"


def test_style_css_has_exact_design_tokens():
    css = (BASE / "static" / "css" / "style.css").read_text()
    for token, value in CSS_TOKENS.items():
        assert f"{token}: {value};" in css, f"token {token} 必须精确为 {value}"
    # 成品图复现 E8：概念图 INTERFACE LAYOUT GUIDE——TOP BAR 100%W x 60pxH / RIGHT SIDEBAR 320pxW
    assert "grid-template-rows: 60px 1fr 56px;" in css, "#app 顶栏行高必须为 60px（概念图 TOP BAR 60pxH）"
    assert "grid-template-columns: 1fr 320px;" in css, "#app 右栏列宽必须为 320px（概念图 RIGHT SIDEBAR 320pxW）"


def test_index_html_structure():
    html = (BASE / "static" / "index.html").read_text()
    for el_id in ["topbar", "chart-area", "tacticalMap", "bottom", "dashboard",
                  "sidebar", "npc-tabs", "chat-log", "suggestions", "input-bar",
                  "vignette-overlay", "noise-overlay"]:
        assert f'id="{el_id}"' in html, f"index.html 缺少 #{el_id}"
    assert 'http-equiv="Cache-Control"' in html, "meta 缓存标签未修复"


# 批准色板：设计 token + 批准衍生色（登记时注明用于哪个资产什么部位）
SVG_PALETTE = {
    # 设计 token（docs/design/UI_DESIGN.md）
    "#f5edd6", "#e8dcc8", "#d4c8a8", "#2a2218", "#6b5d4a", "#a89878",
    "#8b2500", "#c0392b", "#b8d4c8", "#8aaa98", "#d4c4a0", "#c8b890", "#3a2518",
    # 批准衍生色
    "#1e120a",  # vignette 最外圈暗角
    "#efe6cd",  # paper_note 第二层叠纸
    "#4a3f30",  # intel_card_dark 卡底
    "#fff4d6", "#ffedc4",  # light_falloff 光晕端点
    "#c9a76a", "#b08d52", "#8a6b3a", "#4a3820",  # ruler 木尺
    "#e8a33d", "#c8871f", "#b8b8c0", "#8f8f9a", "#d88a7c", "#d4b890", "#3a3228",  # pencil
    "#b22234", "#3c3b6e",  # flag48 旗
    "#2b2118",  # chart-area 海图厚画框（style.css #chart-area border，成品图复现 D3）
    "#241c14",  # sidebar 右栏深底（style.css #sidebar background，成品图复现 E2）
}

SVG_COLOR_RE = re.compile(r'(?:fill|stroke|stop-color)="(#[0-9a-fA-F]{6})"')


def test_svg_colors_within_approved_palette():
    """SVG 色板纯度：只允许批准色值，防止凭空造色偏离设计。"""
    for name, (fname, _) in ASSET_MANIFEST.items():
        p = UI / fname
        if not p.exists():
            continue
        for color in SVG_COLOR_RE.findall(p.read_text()):
            assert color.lower() in SVG_PALETTE, f"{fname} 使用了未批准色值 {color}"


def test_chart_renderer_constants_match_css():
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    for value in ["#f5edd6", "#2a2218", "#b8d4c8", "#8aaa98", "#d4c4a0", "#c8b890",
                  "#8b2500", "#6b5d4a", "#a89878", "#e8dcc8", "#d4c8a8"]:
        assert value in js, f"chartRenderer.js 缺少色值 {value}"
    for label in ["MIDWAY ATOLL", "28°12'N 177°21'W", "SAND ISLAND", "EASTERN ISLAND",
                  "20nm", "25nm", "40nm", "60nm"]:
        assert label in js, f"chartRenderer.js 缺少标注 {label}"
    # 保真度修正 B1：海图底改 AI 纸纹 createPattern 平铺（SVG drawImage 回退）
    assert "createPattern" in js, "chartRenderer.js 缺少 createPattern 纸纹平铺"


def test_chart_renderer_has_ne_hatch_block():
    """成品图复现 D4：NE 角斜线 hatch 块锚点（绘制块命名）。"""
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "hatchNE" in js, "chartRenderer.js 缺少 NE hatch 块（hatchNE 锚点）"


def test_npc_tab_labels():
    js = (BASE / "static" / "js" / "uiController.js").read_text()
    for label in ["COS", "TF16 CAPT", "HOR CAPT", "COMM", "INTEL"]:
        assert label in js, f"uiController.js 缺少标签缩写 {label}"


def test_ui_controller_design_copy():
    js = (BASE / "static" / "js" / "uiController.js").read_text()
    for kw in ["EXECUTE ORDER", "REVISE PLAN", "COMMANDER SIGNATURE", "SECRET", "MISSION", "EXECUTION"]:
        assert kw in js, f"uiController.js 缺少军令纸文案 {kw}"


# ── Phase 8d · Task 8.6：聊天消息 → A10 情报卡 + SECRET 印章 ──

def test_msg_intel_card_styles():
    """聊天卡复刻：.msg 亮色情报卡背景、.msg-classified 暗色卡 + 暗色正文、.msg-stamp 印章。"""
    css = (BASE / "static" / "css" / "style.css").read_text()
    # fix Loop2-F3: B1 后 .msg 亮卡实为 paper_tex 平铺（intel_card_light.svg 仅存于回退注释，
    # 原断言空转）——断言收紧到 .msg 规则块内，且要求 background-repeat: repeat。
    msg_seg = css[css.rindex(".msg {"):]
    assert "url('/static/assets/textures/paper_tex.jpg') repeat" in msg_seg, \
        ".msg 规则缺少 paper_tex.jpg 亮色卡背景（repeat 平铺）"
    assert "url('/static/assets/ui/intel_card_dark.svg')" in css, \
        "style.css 缺少 .msg-classified 暗色情报卡背景"
    assert ".msg-classified .msg-text" in css, "style.css 缺少暗色卡正文覆盖规则"
    assert ".msg-stamp" in css, "style.css 缺少 SECRET 印章样式"
    assert "mix-blend-mode: multiply" in css, "印章需做旧正片叠底混合"
    assert "rotate(-8deg)" in css, "印章需 -8° 倾斜"


def test_ui_controller_classified_message_stamp():
    """机密消息判定（内容含「机密/SECRET/密级」→ msg-classified + secret_stamp 印章 img）。"""
    js = (BASE / "static" / "js" / "uiController.js").read_text()
    for kw in ["msg-classified", "msg-stamp", "/static/assets/ui/secret_stamp.svg"]:
        assert kw in js, f"uiController.js 缺少 {kw}"
    for kw in ["机密", "密级", "secret"]:
        assert kw.lower() in js.lower(), f"uiController.js 缺少机密判定关键词 {kw}"


# ── Phase 8d · Task 8.7：输入区与按钮交互态打磨 ──

def test_input_bar_and_button_focus_styles():
    """输入区纸色墨线 + 打字机红光标 + 按钮键盘焦点虚线描边。"""
    css = (BASE / "static" / "css" / "style.css").read_text()
    assert "caret-color: var(--color-secret-red)" in css, \
        "#chat-input 缺少 secret-red 打字机光标"
    assert ".btn:focus-visible" in css, "缺少 .btn 键盘焦点态"
    assert "outline: 2px dashed var(--color-ink-fade)" in css, \
        ".btn:focus-visible 应为 ink-fade 虚线描边"


def test_index_html_cache_version_consistent():
    """index.html 所有 ?v= 缓存号必须一致且随 CSS 变更递增（保真度修正 T4 → 1780997990，B1 → 1780997991，B3 → 1780997992，C4 → 1780997993，loop1 L4 → 1780997994，loop2 L4 → 1780997995，loop3 F1-F5 → 1780997996，终审修复 → 1780997997，成品图复现 D1/D2 → 1780997998，D4 → 1780997999，E1/E2 → 1780998000，EB2（E3 标签/E4 齿轮/E7 按钮三态）→ 1780998001，EB3（E6 占位卡/E8 布局 60px/320px）→ 1780998002，G1（舰队标记空心圆圈+双虚线矢量）→ 1780998003，GB 批次（G2 侦察机剪影/G3 敌标勘误/G4 SECRET 章+字幕移除）→ 1780998004，GC 批次（G5 圆规道具/G6 尺铅笔移位/G7 东岛近景/顺修 midAngle）→ 1780998005，成品图基准 Loop1 F1-F8（胶囊/罗盘/标注群/敌标位/扇区/细网格/纸签/内阴影）→ 1780998006，F8 重做（纸面晕影改 #chart-area::after 覆层 22px，设计师验收 REJECT 返工）→ 1780998007，Loop2 L4（F1 舰队对位/F3 纸面暖黄/F4 扇区标签外推/F5 细网格提存在感/F6 罗盘避让经度标注）→ 1780998008）。"""
    html = (BASE / "static" / "index.html").read_text()
    versions = set(re.findall(r'\?v=(\d+)', html))
    assert len(versions) == 1, f"index.html 缓存号不一致: {versions}"
    assert versions == {"1780998008"}, f"index.html 缓存号未递增到 1780998008: {versions}"
    # 防再漂移：svgLoader.js 内全部带 ?v= 的资源 URL，版本号必须与 index.html 现值一致
    # （历史漂移：paper_tex ?v=1780997995 与 index.html 1780997996 脱钩，见终审修复项 1）
    loader = (BASE / "static" / "js" / "svgLoader.js").read_text()
    loader_versions = set(re.findall(r'\?v=(\d+)', loader))
    assert loader_versions, "svgLoader.js 未找到带 ?v= 的资源 URL"
    assert loader_versions == versions, \
        f"svgLoader.js 资源版本 {loader_versions} 与 index.html 缓存号 {versions} 不一致（漂移）"


# ── 保真度修正 · B2：木纹接入木尺（data-URI 内嵌） ──

def test_ruler_wood_embeds_wood_texture():
    """ruler_wood.svg 必须以 data-URI 内嵌木纹（<img> 引用的 SVG 禁外部资源，必须内嵌）。"""
    svg = (BASE / "static" / "assets" / "ui" / "ruler_wood.svg").read_text()
    assert "data:image/png;base64" in svg, "ruler_wood.svg 缺少 data-URI 木纹内嵌"


# ── Phase 9 · Task 9.2：电传打字 + 盖章动效 ──

def test_stamp_and_paper_animations():
    """盖章砸落动画应用于机密卡印章与军令纸 SECRET 字样；军令纸首次出现滑入。"""
    css = (BASE / "static" / "css" / "style.css").read_text()
    assert "@keyframes stampThunk" in css, "缺少 stampThunk 砸落动画"
    assert ".msg-stamp, .order-note .order-stamp-word" in css, \
        "stampThunk 应同时作用于情报卡印章与军令纸 SECRET 手写字"
    assert "stampThunk 0.35s ease-out both" in css, "盖章动画参数应为 0.35s ease-out both"
    assert "@keyframes paperIn" in css, "缺少 paperIn 滑入动画"
    assert "paperIn 0.25s ease-out both" in css, "军令纸应为 paperIn 0.25s ease-out both 滑入"


def test_ui_controller_typewriter():
    """NPC 新消息走 typewrite 逐字显示；仅 appendMessage 追加路径接入，renderChat 直接赋值。"""
    js = (BASE / "static" / "js" / "uiController.js").read_text()
    assert "function typewrite(el, text, cps = 40" in js, "缺少 typewrite 打字机函数"
    assert js.count("typewrite(textEl") == 1, "typewrite 只应在 appendMessage 调用一次"
    assert js.index("appendMessage(") < js.index("typewrite(textEl") < js.index("showNotification("), \
        "typewrite 调用点应在 appendMessage 内"
    render_body = js[js.index("renderChat("):js.index("appendMessage(")]
    assert "typewrite" not in render_body, "renderChat 重绘路径不应触发打字机"


# ── Phase 9 · Task 9.3：交互态打磨 ──

def test_tab_hover_lift_style():
    """NPC 标签 hover 上浮 1px，且不覆盖 active 态既有的 -6px 上浮（保真度修正 T4 由 -3px 增强）。"""
    css = (BASE / "static" / "css" / "style.css").read_text()
    assert ".npc-tab:hover:not(.active) { transform: translateY(-1px); }" in css, \
        "标签 hover 应上浮 1px（:not(.active) 防 -6px 被覆盖）"
    assert "transform: translateY(-6px);" in css, "active 态 -6px 上浮必须保留（T4 凸起增强）"


def test_map_renderer_hover_scale_redraw():
    """敌情标记悬停：复用既有 _hoverTarget 命中机制，命中时 1.1 倍缩放重绘。"""
    js = (BASE / "static" / "js" / "mapRenderer.js").read_text()
    assert "scale(1.1, 1.1)" in js, "悬停命中时应以 1.1 倍缩放重绘标记"
    assert "this._hoverTarget.type === 'enemy'" in js, "放大重绘应挂在既有 _hoverTarget enemy 分支内"


# ── 保真度修正 · T1：环礁绘制三连修（岛体避让/SW 海面斜线/沙环投影）──

def test_chart_atoll_fix_markers():
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "ry * 0.32" in js, "沙岛未下移避让坐标行"
    assert "rect(c.x - rx * 1.5" in js, "SW 海面斜线未铺开"
    assert "translate(2, 3)" in js, "沙环投影缺失"


# ── 保真度修正 · T3：舰队引导线指向环礁 + 箭头 ──

def test_task_force_leader_arrow():
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "atollCenter(w, h)" in js and "closePath" in js, "引导线未指向环礁或缺箭头"
    assert "(tf.x - 60, tf.y + 18)" not in js, "写死方向未移除"
    # fix round 1：atollCenter 是屏幕系坐标，调用点 ctx 处于舰队本地平移系——
    # 签名须带 ox/oy，且引导线方向须先换算到本地系（防坐标系回退）
    assert "drawTaskForceMarker(ctx, tf, w, h, ox = 0, oy = 0)" in js, \
        "签名缺 ox/oy 本地系换算参数"
    assert "atollCenter(w, h).x - ox" in js and "atollCenter(w, h).y - oy" in js, \
        "引导线未做屏幕系→舰队本地系换算（atollCenter - 平移量）"
    map_js = (BASE / "static" / "js" / "mapRenderer.js").read_text()
    assert "this.width, this.height, ox, oy)" in map_js, \
        "mapRenderer 调用点未传 ox/oy 舰队居中平移量"


# ── 成品图复现 · G1：ENT/HOR 空心圆圈标记 + 双虚线箭头矢量（计数牌退役）──

def test_task_force_circle_outline_marker():
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "circle-outline" in js, "舰队标记缺 circle-outline 锚点（空心圆圈形态）"


# ── 保真度修正 · fix round 1：25nm 标注错开（右上 45°） ──

def test_range_ring_25nm_label_offset():
    """20/25nm 环间距过近，25nm 标注移到右上 45° 防重叠（设计图位）。"""
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "ctx.fillText(label, c.x + r * 0.71, c.y - r * 0.71)" in js, \
        "25nm 标注未移到右上 45°"
    assert "ctx.fillText(label, c.x + r + 4, c.y - 4)" in js, \
        "其余环标注水平位应保留"


# ── 保真度修正 · T4：标签激活凸起增强 ──

def test_npc_tab_active_lift_enhanced():
    """.npc-tab 段 isolation: isolate——底色移交 ::before 伪元素，激活凸起增强。
    成品图复现 Loop1-F7：页签回归纸签隐喻（成品图基准整排米色纸签）——非激活米色纸签
    #e8dcc3 + ink 深棕墨字，激活 paper-base 加高（padding-bottom）+ 底边无缝连面板。"""
    css = (BASE / "static" / "css" / "style.css").read_text()
    # fix Loop2-F7: 文件尾新增 @media 断点也含 ".npc-tab {"，锚点改钉 Phase 8a 块签名
    npc_seg = css[css.rindex(".npc-tab { position: relative"):]
    assert "isolation: isolate" in npc_seg, ".npc-tab 段缺 isolation: isolate（::before 双底色隔离）"
    # Loop1-F7：非激活米色纸签 + 深棕墨字
    before_seg = css[css.rindex(".npc-tab::before"):]
    assert "background: #e8dcc3;" in before_seg, "非激活纸签应为米色纸底 #e8dcc3（Loop1-F7 推翻 E3 深舌）"
    base_seg = css[css.index(".npc-tab {"):css.index(".npc-tab:hover")]
    assert "color: var(--color-ink-main);" in base_seg, "非激活纸签字应为 ink 深棕墨字（Loop1-F7）"
    active_seg = css[css.rindex(".npc-tab.active {"):]
    assert "color: var(--color-ink-main);" in active_seg, "激活标签须显式回 ink 墨字（防基础色回退）"
    assert "padding-bottom: 6px;" in active_seg, "激活纸签加高缺失（padding-bottom 补 -6px 上浮底缝，无缝连面板）"
    # 成品图复现 E3 → Loop1-F7：hover 底为深色系遗留弱化值（被不透明 ::before 覆盖，保留不动）
    hover_seg = css[css.index(".npc-tab:hover"):css.index(".npc-tab.active")]
    assert "rgba(216, 203, 178, 0.12)" in hover_seg, "hover 底应为深色系提亮 rgba(216,203,178,0.12)"


# ── 保真度修正 · Loop2 L4：F1–F9 修复守卫 ──

def test_loop2_fidelity_fix_markers():
    """Loop2 L4 静态守卫：标记对角错开/岛标签胶囊/细网/纸舌造型/空态纸卡/底栏层次/窄屏断点。"""
    chart = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    # F2 → Loop1-F1 演进: SAND ISLAND 胶囊 measureText 定宽（文字实宽+16，下限 62px）
    assert "Math.max(sandLblW + 16, 62)" in chart, "沙岛胶囊未按 measureText 定宽"
    assert "ctx.font = `7px ${CHART_STYLE.fontTypewriter}`" in chart, "EASTERN ISLAND 黄底标注 7px 字号缺失"
    # F8: 0.25° 细网用 gridLineFaint，0.5° 主网 gridLine 原色保留
    assert "gridLineFaint: 'rgba(160,140,110,0.18)'" in chart, "缺 gridLineFaint 细网色"
    assert "gridLine: 'rgba(160,140,110,0.35)'" in chart, "0.5° 主网原色不得改动"
    assert "lat += 0.25" in chart and "lon += 0.25" in chart, "经纬网未加 0.25° 细网"
    assert "lat += 0.5" in chart and "lon += 0.5" in chart, "0.5° 主网须保留"
    map_js = (BASE / "static" / "js" / "mapRenderer.js").read_text()
    # F1: 舰队标记错开防重叠（成品图复现 G1：计数牌让位 hack 已删，恢复 F2 对角错开
    # i=0: x-14/y-28、i=1: x+14/y+0——圆圈 r=10 小标记，28px 中心距仍有效）
    assert "px - 14 : px + 14" in map_js and "py - 28 : py" in map_js, "舰队标记未按 F2 对角错开"
    ui = (BASE / "static" / "js" / "uiController.js").read_text()
    # F5: 空态包 intel_card 纸卡；F6: 空态读数 dash-empty
    assert 'class="empty-card"' in ui, "空态未包 intel_card 纸卡"
    assert "_setDashEmpty('d-scout'" in ui and "_setDashEmpty('d-enemy'" in ui, \
        "底栏空态读数未接 dash-empty 弱化"
    css = (BASE / "static" / "css" / "style.css").read_text()
    # F4: 纸舌圆角造型 + 非激活压暗下沉（clip-path 切角移除）
    assert "border-radius: 4px 4px 0 0;" in css, "纸舌未改圆角造型"
    assert "clip-path: polygon(0 100%" not in css, "纸舌 clip-path 切角未移除"
    before_seg = css[css.rindex(".npc-tab::before"):]
    assert "transform: translateY(2px)" in before_seg, "非激活纸舌未下沉 2px"
    assert ".npc-tab.active::before { background: var(--color-paper-base); transform: none; }" in css, \
        "激活纸舌未复位（压暗下沉不得影响 active）"
    # F5: 空态纸卡样式（intel_card_light + 宽 88% + SECRET 章移卡右上）
    empty_seg = css[css.rindex(".empty-card {"):]
    assert "intel_card_light.svg" in empty_seg and "width: 88%" in empty_seg, "空态纸卡样式缺失"
    idle_seg = css[css.rindex(".idle-stamp {"):]
    assert "position: absolute" in idle_seg and "right: 8px" in idle_seg, "SECRET 章未移纸卡右上角"
    # F6 → 成品图复现 E1：底栏深色化后标签改 bar-text（叠加 opacity .65 弱化，层次保留）
    assert "color: var(--color-bar-text)" in css[css.rindex(".dash-label {"):], \
        ".dash-label 未随底栏深色化改为 bar-text"
    # F7: ≤1360px 断点
    assert "@media (max-width: 1360px)" in css, "缺 ≤1360px 窄屏断点"


# ── 成品图复现 · D1：45nm 近景取景重构 ──

# ── 成品图复现 · E7：按钮三态（对齐概念图 BUTTON STATES） ──

def test_button_three_states():
    """全局 .btn 三态：Normal 现状 / Hover 提亮一阶 / Pressed 下压 1px + 再暗一档；
    .btn-execute/.btn-revise/#btn-advance 经共享 .btn 类各自适用（Pressed 用 brightness 在各自配色上叠加）。"""
    css = (BASE / "static" / "css" / "style.css").read_text()
    btn_seg = css[css.rindex(".btn {"):css.rindex("::-webkit-scrollbar")]
    assert ".btn:hover" in btn_seg, "缺少 Hover 态"
    assert "background: var(--color-paper-edge);" in btn_seg, "Hover 应在现有配色上提亮一阶（paper-edge）"
    active_seg = css[css.rindex(".btn:active"):]
    assert "transform: translateY(1px);" in active_seg, "Pressed 应下压 1px（translateY，原斜向 translate 废弃）"
    assert "filter: brightness(0.9);" in active_seg, "Pressed 应再暗一档（brightness 叠加各自现有配色）"
    for anchor in [".btn-execute:hover", ".btn-revise:hover", "#btn-advance:hover"]:
        assert anchor in css, f"缺少 {anchor} 各自 hover 变体"


def test_close_framing_constants():
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "/ 45)" in js, "取景未改 45nm 近景"
    assert "CHART_VIEW_NM = 45" in js, "视野常量未提取"


# ── 成品图复现 · E6：命令卡常驻化（设计审计 A10 最大遗漏项） ──

def test_ui_controller_placeholder_order_note():
    """E6 空态占位军令纸：renderSuggestions 空态常驻渲染 STAFF PROPOSAL 占位卡
    （复用 A8 军令纸全套样式：SECRET 头/签名行/按钮禁用态），有建议时正常渲染命令卡。"""
    js = (BASE / "static" / "js" / "uiController.js").read_text()
    assert "NO PENDING ORDERS" in js, "uiController.js 缺少空态占位卡正文 NO PENDING ORDERS"
    for kw in ["STAFF PROPOSAL", "order-note placeholder"]:
        assert kw in js, f"uiController.js 缺少占位军令纸标记 {kw}"
    css = (BASE / "static" / "css" / "style.css").read_text()
    assert ".btn:disabled" in css, "style.css 缺少按钮禁用态（降低不透明度）样式"


# ── 成品图复现 · G3：敌标勘误——红虚线圈+?+ENEMY（enemy_marker.svg 上图） ──

def test_enemy_contact_marker_uses_enemy_marker_svg():
    """设计师审计勘误：成品图敌标实为「红虚线圈+中央?+下方ENEMY红字」，原裁定红方块
    enemy_tag_q 系判读错误——改用 enemy_marker.svg（本就是该形态，质量门 PASS）；
    enemy_tag_q.png 保留为战报方框变体（svgLoader 资产在册），不再上图。"""
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "getIcon('enemy_marker')" in js, "敌情标记未使用 enemy_marker.svg（红虚线圈+?+ENEMY 形态）"
    assert "getIcon('enemy_tag_q')" not in js, "enemy_tag_q 红方块不得再上图（保留为战报方框变体）"
    # 尺寸沿用 confidence 档位映射（high 46 / medium 34 / low 26）
    assert "{ high: 46, medium: 34, low: 26 }" in js, "敌标 confidence 尺寸档位映射缺失"


# ── 成品图复现 · G4：SECRET 章上地图左上 + CHART 字幕移除（设计审计 MISSING-6） ──

def test_chart_draws_secret_stamp_top_left():
    """成品图地图左上角为横版 SECRET 大章（-10° 倾斜），drawAll 末尾（比例尺后）叠画；
    该位置原「海图（CHART）」字幕随之从 index.html 移除（字幕保留会穿帮）。"""
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "getIcon('secret_stamp')" in js, "chartRenderer 未取用 secret_stamp 章"
    assert "drawSecretStamp(ctx, w, h)" in js, "drawAll 末尾未叠画 SECRET 章"
    assert "-10 * Math.PI / 180" in js, "SECRET 章缺 -10° 倾斜（rotate 用 ctx 变换）"
    assert "drawImage(stamp, -90, -38, 180, 76)" in js, "SECRET 章未按 24,20,180,76 目标矩形绘制"


def test_index_html_chart_caption_removed():
    """「海图（CHART）」字幕 div 删除——成品图该位置是 SECRET 章，字幕保留穿帮。"""
    html = (BASE / "static" / "index.html").read_text()
    assert "chart-label" not in html, "index.html 仍残留 .chart-label 字幕 div"
    assert "海图（CHART）" not in html, "index.html 仍残留「海图（CHART）」字幕文案"


# ── 成品图复现 · G5：黄铜圆规桌面道具（button_26 分拆） ──

def test_compass_brass_desk_prop():
    """G5 桌面道具：compass_brass.png（button_26 圆规段分拆，RGBA ~120px 高）在册，
    index.html 接入 .desk-compass，style.css 左下 rotate(15°)（drop-shadow 由 .desk-prop 同族提供）。"""
    p = BASE / "static" / "assets" / "ui" / "icons" / "compass_brass.png"
    assert p.exists(), "缺少 compass_brass.png（button_26 分拆产物）"
    im = Image.open(p)
    assert im.mode == "RGBA", "compass_brass.png 必须为 RGBA 透明底"
    assert 110 <= im.size[1] <= 130, f"compass_brass.png 高度应约 120px: {im.size}"
    html = (BASE / "static" / "index.html").read_text()
    assert 'src="/static/assets/ui/icons/compass_brass.png"' in html, "index.html 未接入圆规桌面道具"
    css = (BASE / "static" / "css" / "style.css").read_text()
    assert ".desk-compass" in css and "rotate(15deg)" in css, "style.css 缺 .desk-compass 左下布局"


# ── 成品图复现 · G6：尺与铅笔按成品图布局移位 ──

def test_desk_ruler_pencil_product_layout():
    """G6 勘测修正：木尺横放左下（压海图左缘，与圆规同侧）、铅笔竖放右缘（笔尖朝下）。
    原布局尺/铅笔均横放底部中央，与成品图不符。
    铅笔 SVG 为横向（420×36、笔尖朝左），rotate(-90°) 转竖后笔尖朝下（裁定 rotate(180deg)
    对横图几何不成立，按裁定预留的「目检调优」修正）。"""
    css = (BASE / "static" / "css" / "style.css").read_text()
    ruler_seg = css[css.rindex(".desk-ruler"):]
    ruler_seg = ruler_seg[:ruler_seg.index("\n")]
    for token in ["left: 6px", "right: auto", "bottom: 54px", "rotate(-3deg)"]:
        assert token in ruler_seg, f".desk-ruler 缺成品图布局 {token}"
    pencil_seg = css[css.rindex(".desk-pencil"):]
    pencil_seg = pencil_seg[:pencil_seg.index("\n")]
    for token in ["right: 14px", "left: auto", "bottom: 120px", "rotate(-90deg)", "width: 200px"]:
        assert token in pencil_seg, f".desk-pencil 缺成品图布局 {token}"


# ── 成品图复现 · H1：设计态 fixture 页面（像素比对专用） ──

def test_design_fixture_present_and_offline():
    """H 批 fixture：static/dev/ 下设计态渲染页 + canned state 存在，
    加载真实渲染器三件套与主样式表，且不依赖后端接口（离线可渲染，仅用于像素比对）。"""
    dev = BASE / "static" / "dev"
    assert (dev / "design-fixture.html").exists(), "缺少 static/dev/design-fixture.html"
    assert (dev / "design-state.js").exists(), "缺少 static/dev/design-state.js"
    assert (dev / "README.md").exists(), "缺少 static/dev/README.md"
    html = (dev / "design-fixture.html").read_text()
    assert "FIXTURE" in html and "非游戏画面" in html, "fixture 页缺防误认横幅"
    for src in ["svgLoader.js", "chartRenderer.js", "mapRenderer.js", "design-state.js"]:
        assert src in html, f"fixture 页未加载 {src}"
    assert "/static/css/style.css" in html, "fixture 页未接主样式表"
    assert "fetch(" not in html, "fixture 页不得含 fetch 调用（离线可渲染）"
    js = (dev / "design-state.js").read_text()
    assert "DESIGN_STATE" in js, "design-state.js 缺 DESIGN_STATE canned state"
    assert "render(" in js, "design-state.js 缺 render(state) 调用"


# ── 成品图复现 · G7：东岛近景细节（黄底标注块/跑道横带/停机剪影） ──

def test_chart_eastern_island_closeup_details():
    """G7 东岛近景三件：①EASTERN ISLAND 黄底墨字标注块（labelYellow 锚点）
    ②SAND ISLAND 侧浅色跑道横带+中线（runwayBand 锚点）
    ③停机剪影 drawParkingRamp——复用 aircraft_topdown 图标缩小 60% 深灰排列。"""
    js = (BASE / "static" / "js" / "chartRenderer.js").read_text()
    assert "EASTERN ISLAND" in js, "黄底标注块文字缺失"
    assert "labelYellow" in js, "缺 EASTERN ISLAND 黄底标注块（labelYellow 锚点）"
    assert "runwayBand" in js, "缺 SAND ISLAND 侧跑道横带（runwayBand 锚点）"
    assert "drawParkingRamp" in js, "缺停机剪影绘制函数（drawParkingRamp 锚点）"
    assert "aircraft_topdown" in js, "停机剪影未复用 aircraft_topdown 图标"
