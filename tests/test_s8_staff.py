"""S8 UI.4 STAFF 静态守卫（三栏布局/名册/正式呈报/极简档案/聊天-判断分离）。"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"
DESK = ROOT / "static" / "js" / "staffDesk.js"
MAIN = ROOT / "static" / "js" / "main.js"
CSS = ROOT / "static" / "css" / "style.css"


def test_staff_desk_three_columns_wired():
    html = INDEX.read_text()
    assert "staffDesk.js?v=" in html
    main = MAIN.read_text()
    assert "registerSection('STAFF'" in main
    desk = DESK.read_text()
    for cls in ("staff-roster", "staff-center", "staff-dossier"):
        assert cls in desk, f"STAFF 缺三栏之一 {cls}"


def test_staff_chat_and_judgment_separated():
    """普通交谈与正式呈报清楚区分：聊天不触发 /judgment；正式入口独立。"""
    desk = DESK.read_text()
    assert "chatPane" in desk and "judgmentPane" in desk
    assert "/chat" in desk                       # 对话走 /chat
    assert "/judgment/tasks" in desk             # 正式判断走 S3 任务
    assert "普通交谈不构成正式命令" in desk
    # 对话路径不得调用正式命令端点
    chat_seg = desk[desk.index("chatPane("):desk.index("judgmentPane(")]
    for banned in ("/judgment", "/suggestion", "/plan-strike"):
        assert banned not in chat_seg


def test_judgment_result_display_fields():
    desk = DESK.read_text()
    for token in ("confidence_band", "change_my_mind", "recommendation",
                  "error_type", "refusal_reason", "assumptions", "report"):
        assert token in desk, f"判断卡缺字段 {token}"
    assert "/npcs/" in desk and "/judgments" in desk   # 判断历史


def test_dossier_minimal_four_lines_only():
    """极简档案：身份/状态/关注/最近互动；无好感度、信任、雷达图、内部数值。"""
    desk = DESK.read_text()
    for token in ("当前状态", "当前关注", "最近互动"):
        assert token in desk
    for banned in ("好感", "信任值", "radar", "favor", "competence",
                   "risk_tolerance", "attributes"):
        assert banned not in desk, f"档案渲染不得出现 {banned}"


def test_s4_hooks_reserved():
    """S4 主动来访/转述预留（v0 契约适配器，不实现引擎）。"""
    adapter = (ROOT / "static" / "js" / "s4Adapter.js").read_text()
    for shape in ("fetchVisitEvents", "fetchRelayRecords", "fetchDossierSummaries",
                  "sanitizeVisitEvent", "sanitizeDossierSummary"):
        assert shape in adapter


def test_staff_css_tokens():
    css = CSS.read_text()
    for token in (".staff-wrap", ".staff-roster", ".staff-dossier",
                  ".staff-judgment-card", ".conf-high", ".conf-medium", ".conf-low",
                  ".dossier-name", ".dossier-line"):
        assert token in css, f"style.css 缺少 {token}"


def test_cache_bumped_for_staff():
    versions = set(re.findall(r"\?v=(\d+)", INDEX.read_text()))
    assert int(min(versions)) >= 1780998023, f"缓存号不得回退: {versions}"
