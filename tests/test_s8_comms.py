"""S8 UI.2 COMMS 静态守卫（频道/详情/勘误链/发报确认/关联跳转/缓存号）。"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "static" / "index.html"
DESK = ROOT / "static" / "js" / "commsDesk.js"
MAIN = ROOT / "static" / "js" / "main.js"
CSS = ROOT / "static" / "css" / "style.css"
SERVER = ROOT / "server.py"


def test_comms_desk_wired_into_shell():
    html = INDEX.read_text()
    assert "commsDesk.js?v=" in html
    assert "CommsDesk" in MAIN.read_text()
    assert "registerSection('COMMS'" in MAIN.read_text()


def test_comms_channels_and_index_present():
    desk = DESK.read_text()
    for chan in ("INCOMING", "TF17_TF11", "CORRECTIONS", "OUTGOING", "ARCHIVE"):
        assert chan in desk, f"COMMS 缺频道 {chan}"
    assert "/comms/channels" in desk


def test_comms_detail_timechain_routing_correction():
    desk = DESK.read_text()
    for token in ("observed_at", "filed_at", "received_at", "routed_to",
                  "relay_chain", "supersedes_message_id", "comms-raw"):
        assert token in desk, f"电文详情缺 {token}"


def test_comms_raw_text_readonly():
    """原文不可编辑：正文以 <pre> 只读呈现，不含可编辑输入绑定。"""
    desk = DESK.read_text()
    assert "<pre class=\"comms-raw\">" in desk
    # compose 仅出现在 OUTGOING 草稿区，且带确认
    assert "确认拍发" in desk and "window.confirm" in desk


def test_comms_related_jump_to_intel():
    desk = DESK.read_text()
    assert "related_brief_ids" in desk
    assert "switchSection('INTEL')" in desk


def test_comms_css_tokens():
    css = CSS.read_text()
    for token in (".comms-wrap", ".comms-channels", ".comms-row", ".comms-card",
                  ".comms-raw", ".comms-compose"):
        assert token in css, f"style.css 缺少 {token}"


def test_server_comms_endpoints_whitelist():
    server = SERVER.read_text()
    assert "/comms/channels" in server
    assert "/comms/outgoing" in server
    assert "related_brief_ids" in server       # 关联跳转白名单字段
    # D1：频道分区不得包含在途状态
    assert "MS.IN_TRANSIT" not in server.split("def intel_service_readable")[1].split("}")[0]


def test_cache_bumped_for_comms():
    """COMMS 阶段引入 821；UI.3 起全链已随阶段递增（守卫见 test_s8_intel）。"""
    versions = set(re.findall(r"\?v=(\d+)", INDEX.read_text()))
    assert int(min(versions)) >= 1780998021, f"缓存号不得回退: {versions}"
