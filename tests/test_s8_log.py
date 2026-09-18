"""S8 UI.5 LOG 静态守卫（三视图/时间线跳转/命令链/认知-事实分离/缓存号）。"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"
DESK = ROOT / "static" / "js" / "logDesk.js"
MAIN = ROOT / "static" / "js" / "main.js"
CSS = ROOT / "static" / "css" / "style.css"


def test_log_desk_three_views_wired():
    html = INDEX.read_text()
    assert "logDesk.js?v=" in html
    assert "registerSection('LOG'" in MAIN.read_text()
    desk = DESK.read_text()
    for view in ("TIMELINE", "ORDERS", "AFTER ACTION"):
        assert view in desk, f"LOG 缺视图 {view}"


def test_log_jumps_back_to_source_workbench():
    desk = DESK.read_text()
    assert "data-jump-wb" in desk
    assert "switchSection" in desk                   # 事件 → 来源工作台


def test_log_orders_chain_sources():
    desk = DESK.read_text()
    for ep in ("/log/after-action", "/comms/channels"):
        assert ep in desk, f"ORDERS 缺数据源 {ep}"
    assert "外发电报" in desk and "otc_change" in desk


def test_log_after_action_separates_errors():
    """认知错误 vs 事实误差 分离呈现（D12），并保留工具/骰子审计。"""
    desk = DESK.read_text()
    assert "认知错误" in desk and "事实误差" in desk
    assert "error_report" in desk
    assert "tool_calls" in desk and "check_records" in desk


def test_log_css_tokens():
    css = CSS.read_text()
    for token in (".log-head", ".log-tab", ".log-timeline", ".log-event",
                  ".log-error-table", ".log-jump"):
        assert token in css, f"style.css 缺少 {token}"


def test_cache_bumped_for_log():
    versions = set(re.findall(r"\?v=(\d+)", INDEX.read_text()))
    assert int(min(versions)) >= 1780998024, f"缓存号不得回退: {versions}"
