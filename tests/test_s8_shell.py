"""S8 UI.1 Shell 静态守卫（五工作台/Commander Desk/值班栏/通知中心/ISSUE ORDER）。

计划验收：
- 原聊天、推进时间和建议流程不回归（/chat、/advance、建议卡入口保留）
- 海图和案卷台切换稳定（CHART=关闭案卷台；ESC 返回）
- FLASH 和 STAFF_VISIT 可正确定位（toast + 工作台路由）
- 全局聊天输入移除；ISSUE ORDER 为全局唯一正式命令入口
- 案卷台打开/切换/关闭不推进游戏时间（commandDesk 不含 /advance 调用）
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"
MAIN = ROOT / "static" / "js" / "main.js"
UI = ROOT / "static" / "js" / "uiController.js"
DESK = ROOT / "static" / "js" / "commandDesk.js"
NOTIF = ROOT / "static" / "js" / "notificationCenter.js"
S4 = ROOT / "static" / "js" / "s4Adapter.js"
CSS = ROOT / "static" / "css" / "style.css"


def test_five_workbench_nav_replaces_npc_tabs_as_global_nav():
    html = INDEX.read_text()
    assert 'id="workbench-nav"' in html
    assert 'id="npc-tabs"' not in html            # 旧 NPC 页签退役
    ui = UI.read_text()
    for wb in ("CHART", "COMMS", "INTEL", "STAFF", "LOG"):
        assert wb in ui
    assert "renderWorkbenchNav" in ui and "renderWorkbenchNav" in MAIN.read_text()


def test_commander_desk_shell_wired_and_never_advances_time():
    html = INDEX.read_text()
    assert 'id="commander-desk"' in html
    assert "commandDesk.js?v=" in html
    desk = DESK.read_text()
    for token in ("switchSection", "close", "openFrom", "data-desk-tab"):
        assert token in desk
    assert "/advance" not in desk                 # 案卷台不推进时间
    main = MAIN.read_text()
    assert "desk.close()" in main                 # CHART / ESC 关闭路径
    assert "switchWorkbench" in main


def test_notification_center_levels_and_interrupt_policy():
    notif = NOTIF.read_text()
    for level in ("INFO", "ROUTINE", "URGENT", "FLASH", "STAFF_VISIT", "CONFLICT"):
        assert f"'{level}'" in notif, f"通知中心缺少 {level}"
    # 只有 FLASH/STAFF_VISIT 主动打断
    assert "level === 'FLASH'" in notif and "level === 'STAFF_VISIT'" in notif
    assert "interrupt" in notif and "onToast" in notif
    assert 'id="notification-toasts"' in INDEX.read_text()
    assert "notificationCenter.js?v=" in INDEX.read_text()


def test_issue_order_is_only_formal_command_entry():
    html = INDEX.read_text()
    assert 'id="btn-issue-order"' in html
    assert 'id="issue-order-modal"' in html
    main = MAIN.read_text()
    assert "btn-issue-order" in main
    # 建议卡（正式命令物）只渲染在 ISSUE ORDER 弹层内
    assert 'id="suggestions"' in html
    io_seg = html[html.index('id="issue-order-modal"'):]
    assert 'id="suggestions"' in io_seg


def test_duty_summary_in_sidebar():
    html = INDEX.read_text()
    assert 'id="duty-summary"' in html
    ui = UI.read_text()
    for token in ("renderDutySummary", "topPriority", "打开案卷台"):
        assert token in ui


def test_s4_adapter_contract_shapes_only():
    s4 = S4.read_text()
    for shape in ("StaffVisitEvent", "RelayRecord", "DossierSummary",
                  "ConflictDossier", "fetchVisitEvents", "fetchConflictDossiers"):
        assert shape in s4
    # S4 引擎未实施：适配器不得实现关系数值
    for banned in ("favor", "affinity", "trust_value", "radar"):
        assert banned not in s4.lower().replace("s4adapter", "")


def test_shell_css_tokens():
    css = CSS.read_text()
    for token in ("#workbench-nav", ".wb-tab", ".wb-badge", "#duty-summary",
                  "#notification-toasts", ".toast-flash", "#issue-order-modal",
                  "#commander-desk", ".desk-tab", ".desk-placeholder"):
        assert token in css, f"style.css 缺少 {token}"
    # 案卷台层级：低于 campaign-select(50) 的语义保留；desk=60 在氛围层(90)之下
    m = re.search(r"#commander-desk\s*\{[^}]*z-index:\s*(\d+)", css)
    assert m and int(m.group(1)) == 60


def test_main_no_longer_binds_global_chat_input():
    main = MAIN.read_text()
    assert "getElementById('chat-input')" not in main
    assert "getElementById('btn-send')" not in main
    # 聊天能力保留（STAFF 工作台复用）
    assert "/chat" in main
    # 推进时间与建议流程不回归
    assert "/advance" in main
    assert "approveSuggestion" in main
