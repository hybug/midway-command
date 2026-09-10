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


@pytest.mark.skip(reason="前瞻守卫：Phase 5 落地时摘除")
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


@pytest.mark.skip(reason="前瞻守卫：Phase 1 落地时摘除")
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
