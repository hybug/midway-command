"""S8 UI.6 S3/S4 联动静态守卫（反馈/转述/备选解释/来访与分歧事件桩/缓存号）。

红线：UI 不改变 S3 核心结论（正式结果只读，反馈进记忆）；
UI 不自动形成参谋共识（转述只记录，不合并判断）；
S4 关系数据只以事件和自然语言摘要展示（无数值/雷达图）。
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"
STAFF = ROOT / "static" / "js" / "staffDesk.js"
S4 = ROOT / "static" / "js" / "s4Adapter.js"
NOTIF = ROOT / "static" / "js" / "notificationCenter.js"
MAIN = ROOT / "static" / "js" / "main.js"
CSS = ROOT / "static" / "css" / "style.css"
SERVER = ROOT / "server.py"


def test_judgment_feedback_and_relay_endpoints():
    """AS.1/R3：转述端点降级为 410 拒绝；反馈端点保留。"""
    server = SERVER.read_text()
    assert "/judgment/results/{result_id}/feedback" in server
    assert '@app.post("/staff/relay")' in server and "410" in server
    assert '@app.get("/staff/relays")' in server
    # 转述不再产生 player_relay 审计动作（写路径已删，timeline 只保留旧数据渲染）
    assert 'action="player_relay"' not in server


def test_staff_ui_shows_alternatives_feedback_without_relay():
    staff = STAFF.read_text()
    assert "备选解释" in staff                        # S3 plausible 展示
    assert "/judgment/results/" in staff and "/feedback" in staff
    assert "/staff/relay" not in staff                # 转述入口已移除
    assert "采纳" in staff and "驳回" in staff and "暂缓" in staff


def test_s4_fixture_events_and_notification_path():
    s4 = S4.read_text()
    assert "installFixtures" in s4 and "clearFixtures" in s4
    assert "sanitizeVisitEvent" in s4
    # 通知分级在通知中心；适配器消费在 main.js 聚合入口
    notif = NOTIF.read_text()
    assert "STAFF_VISIT" in notif and "CONFLICT" in notif
    main = MAIN.read_text()
    assert "fetchVisitEvents" in main and "fetchConflictDossiers" in main


def test_no_consensus_or_numeric_relation_rendering():
    """UI 不合并参谋意见：无共识计算；无数值关系渲染。"""
    staff = STAFF.read_text()
    for banned in ("consensus", "共识分", "平均置信", "trust+", "favor+"):
        assert banned not in staff, f"STAFF 不得出现 {banned}"
    s4 = S4.read_text().lower()
    for banned in ("favor", "radar", "trust_value"):
        assert banned not in s4.replace("s4adapter", "")


def test_ui6_css_tokens():
    css = CSS.read_text()
    for token in (".staff-judgment-actions",):
        assert token in css


def test_cache_bumped_for_ui6():
    versions = set(re.findall(r"\?v=(\d+)", INDEX.read_text()))
    assert int(min(versions)) >= 1780998025, f"缓存号不得回退: {versions}"
