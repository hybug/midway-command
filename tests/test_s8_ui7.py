"""S8 UI.7 静态守卫（可读性/键盘/增量渲染/响应式断点/缓存号）。"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"
MAIN = ROOT / "static" / "js" / "main.js"
LOG = ROOT / "static" / "js" / "logDesk.js"
CSS = ROOT / "static" / "css" / "style.css"


def test_readability_floor_tokens():
    """案卷正文 ≥13px；紧凑右栏 ≥11px（M8.8）。"""
    css = CSS.read_text()
    assert ".intel-brief-narrative { font-size: 13px" in css
    assert ".staff-msg p { font-size: 12px" in css      # 对话 12px（历史遗留一致性）
    assert ".staff-chosen { font-size: 13px" in css     # 判断正文可读


def test_keyboard_full_flow():
    main = MAIN.read_text()
    assert "Escape" in main                              # ESC 关闭
    assert "altKey" in main and "'CHART', 'COMMS', 'INTEL', 'STAFF', 'LOG'" in main
    css = CSS.read_text()
    assert ".desk-tab:focus-visible" in css              # 键盘焦点可见


def test_scroll_containment_and_render_cap():
    css = CSS.read_text()
    assert "overscroll-behavior: contain" in css         # 滚轮不劫持页面
    log = LOG.read_text()
    assert "RENDER_CAP" in log and "slice(-RENDER_CAP)" in log


def test_responsive_breakpoints():
    css = CSS.read_text()
    assert "@media (max-width: 1280px)" in css
    assert "grid-template-columns: 1fr 280px" in css     # 1280 右栏收窄
    assert "@media (max-width: 1360px)" in css


def test_cache_bumped_for_ui7():
    versions = set(re.findall(r"\?v=(\d+)", INDEX.read_text()))
    assert int(min(versions)) >= 1780998026, f"缓存号不得回退: {versions}"
