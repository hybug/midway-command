"""航海参谋 NPC 与航线提案审批流（N.3）。

Fake LLM client 沿既有 NPC 测试桩模式，不打真实 API。
全链：propose_route → state.pending_routes → approve → state.routes active。
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import server
from src.agents.navigator import (
    NAVIGATOR_TOOLS_SCHEMA,
    NavigatorNPC,
    handle_propose_route,
    handle_query_distance_bearing,
    handle_query_own_fleet,
    handle_query_theater,
)
from src.initial_state import build_initial_state
from src.llm import ChatResult, ToolCall
from src.npc_config import NPC_REGISTRY
from src.routes import FLEET_SHORT, PendingRoute, full_fleet_name


# ── Fake LLM client（沿既有 NPC 测试桩模式）──

class FakeLLMClient:
    """模拟 LLM：依次执行预定工具调用后返回固定文本。"""

    def __init__(self, planned_calls=None, final_text="航线提案已呈报，请长官审定。"):
        self._planned = list(planned_calls or [])
        self.final_text = final_text
        self.system_prompts = []

    def chat(self, messages, system_prompt=None, tools=None,
             tool_handlers=None, **kwargs):
        self.system_prompts.append(system_prompt or "")
        result = ChatResult()
        for name, args in self._planned:
            handler = (tool_handlers or {}).get(name)
            if handler:
                call_result = str(handler(**args))
            else:
                call_result = f"Error: No handler for tool '{name}'"
            result.tool_calls.append(
                ToolCall(name=name, input=args, result=call_result)
            )
        result.text = self.final_text
        return result


PROPOSE_ARGS = {
    "owner": "TF16",
    "rationale": "TF16 现位于 28.0N 177.0W，向西北机动至伏击阵位；"
                 "25 节航速下第一航路点约 1 小时后到达。",
    "waypoints": [
        {"lat": 28.4, "lon": -177.4, "eta": "1942-06-04T05:00:00"},
        {"lat": 29.0, "lon": -178.0},
    ],
}


def _make_state():
    return build_initial_state()


# ── 注册与工具面 ──

class TestNavigatorRegistry:

    def test_navigator_registered(self):
        """navigator 在 NPC_REGISTRY 中，四个工具全部注册。"""
        cfg = NPC_REGISTRY["navigator"]
        assert cfg.role == "航海参谋"
        for tool in ("query_own_fleet", "query_theater",
                     "query_distance_bearing", "propose_route"):
            assert tool in cfg.allowed_tools

    def test_navigator_tools_exposed(self):
        """NavigatorNPC 暴露四个工具 schema 与同名 handler。"""
        nav = NavigatorNPC(client=FakeLLMClient())
        names = [t["function"]["name"] for t in nav.tools]
        assert sorted(names) == sorted(
            ["query_own_fleet", "query_theater",
             "query_distance_bearing", "propose_route"]
        )
        for name in names:
            assert name in nav.tool_handlers

    def test_system_prompt_persona(self):
        """system prompt 是严谨航海参谋人设：rationale/坐标/ETA 要求。"""
        state = _make_state()
        nav = NavigatorNPC(client=FakeLLMClient())
        prompt = nav.build_system_prompt(state)
        assert "航海参谋" in prompt
        assert "rationale" in prompt or "理由" in prompt or "依据" in prompt
        assert "坐标" in prompt
        assert "ETA" in prompt
        # 不能泄露 god-view 真相
        assert "Kido Butai" not in prompt
        assert "Akagi" not in prompt


# ── 只读工具（GameState 墙内）──

class TestReadTools:

    def test_query_own_fleet(self):
        state = _make_state()
        out = handle_query_own_fleet(state)
        assert "TF16" in out or "Task Force 16" in out
        assert "28.2" in out  # 引用真实坐标
        # 不泄露 actual_enemy
        assert "Kido Butai" not in out
        assert "Akagi" not in out

    def test_query_theater(self):
        """读 theater.json 关键字段：bases + 环礁中心。"""
        out = handle_query_theater(_make_state())
        assert "中途岛" in out
        assert "28.2" in out and "-177.4" in out

    def test_query_distance_bearing_delegates_to_scouting(self):
        """委托 scouting.calculate_bearing / calculate_distance_nm。"""
        from src.scouting import calculate_bearing, calculate_distance_nm
        a = {"lat": 28.0, "lon": -177.0}
        b = {"lat": 28.5, "lon": -177.0}
        out = handle_query_distance_bearing(_make_state(), a=a, b=b)
        assert str(round(calculate_bearing((28.0, -177.0), (28.5, -177.0)))) in out
        assert f"{calculate_distance_nm((28.0, -177.0), (28.5, -177.0)):.1f}" in out


# ── propose_route → 独立 pending_routes 列表 ──

class TestProposeRoute:

    def test_propose_route_creates_pending_route(self):
        """propose_route 产 PendingRoute，入 state.pending_routes（独立列表）。"""
        state = _make_state()
        out = handle_propose_route(state, **PROPOSE_ARGS)
        assert "已提交" in out
        assert len(state.pending_routes) == 1
        pr = state.pending_routes[0]
        assert isinstance(pr, PendingRoute)
        assert pr.owner == "TF16"           # 短名约定
        assert pr.rationale == PROPOSE_ARGS["rationale"]
        assert len(pr.waypoints) == 2
        assert pr.waypoints[0].lat == 28.4
        assert pr.waypoints[0].eta == datetime(1942, 6, 4, 5, 0)
        assert pr.status == "proposed"
        # 不与 pending_suggestions 混
        assert state.pending_suggestions == []

    def test_propose_route_accepts_full_name(self):
        """owner 传全名时归一化为短名。"""
        state = _make_state()
        args = dict(PROPOSE_ARGS, owner="Task Force 17")
        handle_propose_route(state, **args)
        assert state.pending_routes[0].owner == "TF17"

    def test_propose_route_rejects_unknown_fleet(self):
        """未知舰队拒绝入列（GameState 墙）。"""
        state = _make_state()
        args = dict(PROPOSE_ARGS, owner="TF99")
        out = handle_propose_route(state, **args)
        assert "Error" in out
        assert state.pending_routes == []

    def test_fake_client_full_chain_to_pending(self):
        """fake client 驱动 navigator.chat → 工具真实写入 pending_routes。"""
        state = _make_state()
        client = FakeLLMClient(planned_calls=[("propose_route", dict(PROPOSE_ARGS))])
        nav = NavigatorNPC(client=client)

        def wrap(handler):
            def wrapped(**kwargs):
                return handler(state, **kwargs)
            return wrapped

        response = nav.chat(
            player_input="参谋，给 TF16 拟一条向西北的伏击航线。",
            state=state,
            tools=nav.tools,
            tool_handlers={n: wrap(h) for n, h in nav.tool_handlers.items()},
        )
        assert "呈报" in response.text
        assert len(client.system_prompts) == 1
        assert len(state.pending_routes) == 1
        assert state.pending_routes[0].status == "proposed"

    def test_fleet_short_mapping(self):
        """短名映射：全名 ↔ 短名（scenario.json 的 name 字段）。"""
        assert FLEET_SHORT == {"Task Force 16": "TF16", "Task Force 17": "TF17"}
        assert full_fleet_name("TF16") == "Task Force 16"
        assert full_fleet_name("TF17") == "Task Force 17"
        assert full_fleet_name("NOPE") is None


# ── 审批流端点（无 LLM 参与）──

@pytest.fixture()
def client():
    """TestClient + 共享状态的卫生保护。"""
    tc = TestClient(server.app)
    saved_pr = list(server.game_state.pending_routes)
    saved_routes = list(server.game_state.routes)
    saved_ap = server.game_state.action_points
    yield tc
    server.game_state.pending_routes[:] = saved_pr
    server.game_state.routes[:] = saved_routes
    server.game_state.action_points = saved_ap


def _propose_via_npc(client: TestClient) -> dict:
    """fake client 注入 server 的 navigator，走真实端点提案。"""
    saved = server.npcs["navigator"]
    server.npcs["navigator"] = NavigatorNPC(
        client=FakeLLMClient(planned_calls=[("propose_route", dict(PROPOSE_ARGS))])
    )
    server.game_state.action_points = server.game_state.max_action_points
    try:
        resp = client.post("/navigator/propose",
                           json={"message": "拟一条 TF16 巡航线。"})
        assert resp.status_code == 200
        return resp.json()
    finally:
        server.npcs["navigator"] = saved


class TestPendingRouteEndpoints:

    def test_propose_endpoint_full_chain_to_active_route(self, client):
        """propose → pending_routes → approve → state.routes active 全链。"""
        body = _propose_via_npc(client)
        assert "pending_routes" in body
        assert len(server.game_state.pending_routes) == 1
        pr = server.game_state.pending_routes[0]
        assert pr.owner == "TF16"

        # GET /pending-routes 可见提案
        resp = client.get("/pending-routes")
        assert resp.status_code == 200
        listed = {p["id"]: p for p in resp.json()["pending_routes"]}
        assert listed[pr.id]["status"] == "proposed"
        assert listed[pr.id]["rationale"]

        # 批准 → 转 Route 落 state.routes，status=active
        resp = client.post(f"/pending-routes/{pr.id}/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["route"]["status"] == "active"
        assert data["route"]["owner"] == "TF16"
        assert len(data["route"]["waypoints"]) == 2

        stored = next(r for r in server.game_state.routes if r.id == data["route"]["id"])
        assert stored.status == "active"
        assert stored.owner == "TF16"
        assert server.game_state.pending_routes[0].status == "approved"

    def test_reject_pending_route(self, client):
        """驳回：pending route 置 rejected，不产生 Route。"""
        _propose_via_npc(client)
        pr = server.game_state.pending_routes[0]
        routes_before = len(server.game_state.routes)

        resp = client.post(f"/pending-routes/{pr.id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        assert server.game_state.pending_routes[0].status == "rejected"
        assert len(server.game_state.routes) == routes_before

    def test_double_approve_rejected_state(self, client):
        """非 proposed 状态不可再批。"""
        _propose_via_npc(client)
        pr = server.game_state.pending_routes[0]
        assert client.post(f"/pending-routes/{pr.id}/approve").status_code == 200
        assert client.post(f"/pending-routes/{pr.id}/approve").status_code == 400

    def test_unknown_pending_route_404(self, client):
        assert client.post("/pending-routes/nonexistent/approve").status_code == 404
        assert client.post("/pending-routes/nonexistent/reject").status_code == 404
