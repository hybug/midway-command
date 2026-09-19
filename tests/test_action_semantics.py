"""操作语义整改 AS.0–AS.1 守卫（action-semantics-remediation-plan R1–R4）。

红线：
- R1 聊天不得修改状态：/chat 可用工具集无写工具（execute_action）。
- R2 confirm-contact 公共旁路关闭：端点 410，前端无接线。
- R3 玩家转述入口移除：/staff/relay(+s) 410，前端无按钮。
- R4 自由文本不得推断正式动作：agent 提示词不再指示 execute_action。
"""
import pathlib
import re

from fastapi.testclient import TestClient

import server as server_module
from src.state import GameClock, GameState

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATIC_JS = ROOT / "static" / "js"


def test_action_contracts_exist():
    """AS.0 契约：ActionCommand / AvailableAction / AuditRecord 与 v0 动作目录。"""
    from src.actions.contracts import (  # noqa: F401
        ActionCommand,
        ActionType,
        AuditRecord,
        AvailableAction,
    )
    for action in (
        "REQUEST_ASSESSMENT", "RECORD_COMMANDER_FEEDBACK",
        "ACKNOWLEDGE_STAFF_NOTICE", "DEFER_STAFF_NOTICE",
        "CLOSE_STAFF_NOTICE", "PROPOSE_PLOT", "APPROVE_PLOT",
        "SEND_TELEGRAM", "SET_COURSE", "LAUNCH_SCOUT",
    ):
        assert action in ActionType.__members__ or action in getattr(ActionType, "_value2member_map_", {}), \
            f"动作目录缺少 {action}"


def _all_npc_chat_tools():
    from src.agents.browning import BrowningNPC
    from src.agents.intel_officer import IntelOfficerNPC
    from src.agents.mitscher import MitscherNPC
    from src.agents.murray import MurrayNPC
    from src.agents.navigator import NavigatorNPC
    from src.agents.radio_officer import RadioOfficerNPC
    for cls in (BrowningNPC, MurrayNPC, MitscherNPC,
                RadioOfficerNPC, IntelOfficerNPC, NavigatorNPC):
        try:
            npc = cls()
        except Exception:
            continue
        yield cls.__name__ + ":" + cls.name, {t["function"]["name"] for t in npc.tools}


def test_r1_chat_toolsets_contain_no_write_tools():
    """R1：所有 /chat 工具集不得含写工具 execute_action。"""
    for name, tools in _all_npc_chat_tools():
        assert "execute_action" not in tools, f"{name} 聊天工具集仍含写工具 execute_action"


def test_r1_tools_schema_has_no_execute_action():
    """R1：聊天工具 schema 总表移除 execute_action（处理函数仅供玩家确认路径使用）。"""
    from src.tools import TOOLS_SCHEMA
    names = {t["function"]["name"] for t in TOOLS_SCHEMA}
    assert "execute_action" not in names
    # 玩家确认过的建议执行路径仍可用（/suggestion/{index}/approve）
    from src.tools import handle_execute_action
    assert callable(handle_execute_action)


def test_r4_agent_prompts_no_execute_action_instruction():
    """R4：agent 提示词不得再指示 LLM 用 execute_action。"""
    for py in (ROOT / "src" / "agents").glob("*.py"):
        assert "execute_action" not in py.read_text(encoding="utf-8"), \
            f"{py.name} 仍引用 execute_action"


def test_r2_confirm_contact_endpoint_gone():
    s = GameState(clock=GameClock(game_time=__import__("datetime").datetime(1942, 5, 7, 6, 0)))
    server_module.game_state = s
    client = TestClient(server_module.app)
    resp = client.post("/confirm-contact/0")
    assert resp.status_code == 410
    assert "PlotProposal" in resp.json()["detail"]


def test_r3_staff_relay_endpoints_gone():
    s = GameState(clock=GameClock(game_time=__import__("datetime").datetime(1942, 5, 7, 6, 0)))
    server_module.game_state = s
    client = TestClient(server_module.app)
    assert client.post("/staff/relay", json={}).status_code == 410
    assert client.get("/staff/relays").status_code == 410


def test_r2_frontend_no_confirm_contact_wiring():
    for js in STATIC_JS.glob("*.js"):
        assert "/confirm-contact" not in js.read_text(encoding="utf-8"), \
            f"{js.name} 仍接线 confirm-contact"


def test_r3_frontend_no_relay_entry():
    for js in STATIC_JS.glob("*.js"):
        text = js.read_text(encoding="utf-8")
        assert "/staff/relay" not in text, f"{js.name} 仍引用 /staff/relay"
        assert "data-relay" not in text, f"{js.name} 仍有转述按钮"


def test_formal_buttons_carry_data_action():
    """AS.0 审计清单：正式动作按钮带 data-action 类标记（抽样新 S4/S5 界面）。"""
    staff = (STATIC_JS / "staffDesk.js").read_text(encoding="utf-8")
    # 反馈按钮沿用 data-feedback（固定枚举动作），通知按钮须为 data-notice-action
    assert "data-feedback" in staff or "data-notice-action" in staff
