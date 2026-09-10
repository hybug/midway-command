"""UI 设计图复刻守卫测试。

校验 docs/plans/ui-replication-plan.md 定义的资产文件、设计 token、
页面结构与渲染器常量的静态一致性。前端无 JS 测试运行器，
本文件是 UI 复刻的自动化回归防线。
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

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


@pytest.mark.skip(reason="前瞻守卫：Phase 9 落地时摘除")
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
                  "20nm", "40nm", "60nm"]:
        assert label in js, f"chartRenderer.js 缺少标注 {label}"


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
    assert "url('/static/assets/ui/intel_card_light.svg')" in css, \
        "style.css 缺少 .msg 亮色情报卡背景"
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
