"""S8 UI.3 INTEL 静态守卫（四视图案卷台/审图模式/版本比较/证据判断跳转/缓存号）。"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"
BOARD = ROOT / "static" / "js" / "intelBoard.js"
MAIN = ROOT / "static" / "js" / "main.js"
CSS = ROOT / "static" / "css" / "style.css"


def test_intel_board_four_views_mounted_in_desk():
    board = BOARD.read_text()
    for view in ("SITREP", "BRIEFS", "PLOTS", "EVIDENCE"):
        assert view in board, f"INTEL 缺视图 {view}"
    assert "mountDesk" in board
    main = MAIN.read_text()
    assert "registerSection('INTEL'" in main


def test_intel_approval_actions_preserved():
    """S2 审批操作不回归：四动作 + 批注 + APPROVED 印记 + 一键反查。"""
    board = BOARD.read_text()
    for act in ("approve", "reject", "defer", "request-revision"):
        assert act in board
    for cls in ("claim-fact", "claim-judgment", "claim-hyp"):
        assert cls in board
    assert "APPROVED" in board
    assert "showPlotChain" in board


def test_intel_review_mode_is_desk_not_chart():
    """默认海图只显示已批准标图（D13 不回归）；审图动作只在工作台。"""
    board = BOARD.read_text()
    assert "审图模式" in board                       # PLOTS 审图呈现在案卷台
    assert "批准不等于确认事实" in board
    assert "版本比较" in board and "compareVersions" in board
    assert "/intel/plots/" in board                  # 版本链历史端点


def test_intel_evidence_judgment_cross_jump():
    board = BOARD.read_text()
    assert "data-goto-evidence" in board             # 简报 → 证据
    assert "data-goto-brief" in board                # 证据 → 判断


def test_intel_css_tokens():
    css = CSS.read_text()
    for token in (".intel-desk-head", ".intel-sit-grid", ".intel-sit-val",
                  ".intel-compare-table", ".intel-kw", ".intel-brief-narrative",
                  ".intel-mini-brief"):
        assert token in css, f"style.css 缺少 {token}"
    # 案卷正文可读字号（M8.8：≥13px）
    assert "13px" in css


def test_cache_bumped_for_intel():
    """INTEL 阶段为 822；后续阶段全链继续递增（不回退即可）。"""
    versions = set(re.findall(r"\?v=(\d+)", INDEX.read_text()))
    assert int(min(versions)) >= 1780998022, f"缓存号不得回退: {versions}"
