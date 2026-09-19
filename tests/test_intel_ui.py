"""S2.8 情报 UI 静态守卫（收报室/简报/审图/复盘/标图印记/缓存号）。"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"
BOARD = ROOT / "static" / "js" / "intelBoard.js"
MAIN = ROOT / "static" / "js" / "main.js"
MAP = ROOT / "static" / "js" / "mapRenderer.js"
CSS = ROOT / "static" / "css" / "style.css"


def test_index_has_intel_containers():
    html = INDEX.read_text()
    assert 'id="intel-board"' in html          # 情报板容器
    assert 'id="after-action"' in html         # 战后复盘弹层
    assert 'id="aa-body"' in html
    assert "intelBoard.js?v=" in html          # 情报板脚本接线


def test_index_cache_version_bumped_and_consistent():
    html = INDEX.read_text()
    versions = set(re.findall(r"\?v=(\d+)", html))
    assert versions == {"1780998031"}, f"index.html 缓存号应为 1780998031: {versions}"


def test_intel_board_consumes_whitelist_endpoints():
    """S8 UI.3 起：INTEL 案卷台四视图（INBOX 迁 COMMS 工作台 /comms/channels）。"""
    js = BOARD.read_text()
    for ep in ("/intel/sitrep", "/intel/briefs", "/intel/plots",
               "/intel/evidence", "/intel/after-action"):
        assert ep in js, f"intelBoard 未接入 {ep}"
    for view in ("renderSitrep", "renderBriefs", "renderPlots", "renderEvidence",
                 "mountDesk", "compareVersions"):
        assert view in js, f"intelBoard 缺 {view}"
    # 审批四动作
    for act in ("approve", "reject", "defer", "request-revision"):
        assert act in js
    # 事实/判断/推测 视觉语义（S8.5）
    for cls in ("claim-fact", "claim-judgment", "claim-hyp"):
        assert cls in js
    # 未批准/已批准视觉区分（D13：PENDING 金色虚线圈 / APPROVED 印记）
    assert 'pending"' in js.replace("'", '"') or "pending" in js
    assert "APPROVED" in js
    # 一键反查（海图敌标 → 标图链）
    assert "showPlotChain" in js


def test_main_wires_intel_board():
    js = MAIN.read_text()
    assert "IntelBoard" in js
    assert "intelBoard.mount('intel-board')" in js
    assert "onEnemyContact" in js


def test_map_renderer_approved_tag_and_click():
    js = MAP.read_text()
    assert "APPROVED v" in js                      # 正式标图印记
    assert "onEnemyContact" in js                  # 敌标反查回调
    assert "plot:" in js or "startsWith" in js


def test_css_intel_tokens():
    css = CSS.read_text()
    for token in ("#intel-board", ".intel-card", ".claim-fact", ".claim-judgment",
                  ".claim-hyp", "#after-action", ".aa-panel", ".plot-card.pending",
                  ".intel-stamp-word.approved"):
        assert token in css, f"style.css 缺少 {token}"


def test_intel_fixture_page_marked_and_wired():
    """定妆页必须带 FIXTURE 标识（HANDOFF 纪律），且走真实 intelBoard.js。"""
    fx = (ROOT / "static" / "dev" / "intel-fixture.html").read_text()
    assert "FIXTURE — 非游戏画面" in fx
    assert "intelBoard.js?v=1780998031" in fx
    assert "window.fetch = " in fx      # 数据为桩，不触真实接口


def test_intel_ui_colors_consistent_with_tokens():
    css = CSS.read_text()
    # 情报域色值沿用既有 token：墨 #2a2218 / 敌红 #8b2500 / 纸 #f5edd6 / 淡墨 #6b5d4a
    for color in ("#2a2218", "#8b2500", "#f5edd6", "#6b5d4a"):
        assert color in css
