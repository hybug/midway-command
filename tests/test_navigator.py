"""航海参谋 NPC 与航线提案审批流（N.3）。

Fake LLM client 沿既有 NPC 测试桩模式，不打真实 API。
全链：propose_route → state.pending_routes → approve → state.routes active。
"""
from datetime import datetime, timezone
from pathlib import Path

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
from src.routes import (
    PendingRoute,
    PendingRouteStatus,
    fleet_short_name,
    full_fleet_name,
    known_fleet_short_names,
)
from src.theater import load_theater
from src.theater.context import TheaterContext


# ── Fake LLM client（沿既有 NPC 测试桩模式）──

class FakeLLMClient:
    """模拟 LLM：每轮 chat 消费一个预定工具调用（队列语义）后返回固定文本。"""

    def __init__(self, planned_calls=None, final_text="航线提案已呈报，请长官审定。"):
        self._planned = list(planned_calls or [])
        self.final_text = final_text
        self.system_prompts = []

    def chat(self, messages, system_prompt=None, tools=None,
             tool_handlers=None, **kwargs):
        self.system_prompts.append(system_prompt or "")
        result = ChatResult()
        planned = self._planned[:1]  # 每轮只执行下一个预定调用
        self._planned = self._planned[1:]
        for name, args in planned:
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

    def test_query_own_fleet_southern_lat_no_double_sign(self):
        """南纬不带双负号（纬度 abs() 修复回归）。"""
        state = _make_state()
        lead = state.task_forces[0].carriers[0]
        lead.position.lat = -33.9
        lead.position.lon = 25.0
        out = handle_query_own_fleet(state)
        assert "33.9S" in out
        assert "25.0E" in out
        assert "-33.9S" not in out
        assert "-25.0E" not in out


# ── TheaterContext 注入（战区解耦：禁止硬编码路径直读）──

def _fake_theater() -> TheaterContext:
    """注入用假战区上下文：字段结构与真实包一致，值带可识别标记。"""
    return TheaterContext(
        id="test-theater",
        name="测试战区",
        view={"center": {"lat": 10.0, "lon": -170.0}},
        bases=[
            {"id": "fake_base", "name": "假想基地",
             "lat": 10.5, "lon": -170.5, "type": "airfield"},
        ],
        sectors=[],
        graticule={},
        range_rings={},
        scenario={},
        theater_raw={"name_en": "Testwood"},
        geography={},
        pack_dir=Path("."),
    )


class TestTheaterContextInjection:

    def test_query_theater_with_injected_real_context(self):
        """注入真实 TheaterContext（load_theater(midway)）→ 输出关键地理事实。"""
        pack_dir = Path(__file__).resolve().parents[1] / "theaters" / "midway"
        ctx = load_theater(pack_dir)
        out = handle_query_theater(_make_state(), theater=ctx)
        assert "中途岛" in out
        assert "Midway" in out
        assert "28.2" in out and "-177.4" in out
        assert "中途岛机场" in out  # bases 来自注入实例

    def test_query_theater_with_fake_context(self):
        """注入 fake TheaterContext → 只读注入实例，不混入真实缺省战区。"""
        out = handle_query_theater(_make_state(), theater=_fake_theater())
        assert "测试战区" in out
        assert "Testwood" in out
        assert "假想基地" in out
        assert "10.0" in out and "-170.5" in out
        assert "中途岛" not in out

    def test_navigator_handlers_bind_injected_theater(self):
        """构造注入 theater → tool_handlers 的 query_theater 绑定该实例。"""
        nav = NavigatorNPC(client=FakeLLMClient(), theater=_fake_theater())
        handler = nav.tool_handlers["query_theater"]
        out = handler(_make_state())
        assert "假想基地" in out
        assert "中途岛" not in out

    def test_navigator_lazy_default_theater_from_load_theater(self):
        """缺省 theater=None → 延迟经 src.theater.context.load_theater 加载并缓存。"""
        nav = NavigatorNPC(client=FakeLLMClient())
        assert isinstance(nav.theater, TheaterContext)
        assert nav.theater.id == "midway"
        assert nav.theater.bases  # 结构化字段可用
        # 二次访问命中实例缓存（同一对象，不重复加载）
        assert nav.theater is nav._theater

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
        """短名映射（O.4 函数化，战区驱动）：midway 全名 → 短名；反查全名。"""
        assert fleet_short_name("Task Force 16", "midway") == "TF16"
        assert fleet_short_name("Task Force 17", "midway") == "TF17"
        assert sorted(known_fleet_short_names("midway")) == ["TF16", "TF17"]
        assert full_fleet_name("TF16") == "Task Force 16"
        assert full_fleet_name("TF17") == "Task Force 17"
        assert full_fleet_name("NOPE") is None

    def test_fleet_short_name_coral_sea(self):
        """珊瑚海战区短名（O.4 战区解耦）：TG 后缀剧本名前缀命中 + MO 机动部队。"""
        assert fleet_short_name("Task Force 17", "coral-sea") == "TF17"
        # scenario.json 实际剧本名带战役番号后缀——前缀命中同一舰队
        assert fleet_short_name("Task Force 17 (TG 17.5)", "coral-sea") == "TF17"
        assert fleet_short_name("Task Force 11 (TG 17.8)", "coral-sea") == "TF11"
        assert fleet_short_name("Task Force 44", "coral-sea") == "TF44"
        assert fleet_short_name("MO 机动部队", "coral-sea") == "MO"
        assert sorted(known_fleet_short_names("coral-sea")) == \
            ["MO", "TF11", "TF17", "TF44"]

    def test_fleet_short_name_unknown_falls_back_to_prefix(self):
        """未匹配回退全名前 12 字符（短名直传经回退天然透传）。"""
        assert fleet_short_name("Task Force 99", "midway") == "Task Force 9"
        assert fleet_short_name("TF16", "midway") == "TF16"     # 短名直传
        assert fleet_short_name("TF17", "coral-sea") == "TF17"
        # 无映射表战区同样回退（不抛错）
        assert fleet_short_name("Enemy Fleet Alpha", "unknown-theater") == "Enemy Fleet "

    def test_propose_route_coral_sea_theater(self):
        """注入 fake theater（id=coral-sea）→ TG 后缀剧本名归一化 TF17 收单。"""
        state = _make_state()
        coral = TheaterContext(
            id="coral-sea", name="珊瑚海",
            view={"center": {"lat": -15.2, "lon": 155.5}},
            bases=[], sectors=[], graticule={}, range_rings={}, scenario={},
            theater_raw={"name_en": "Coral Sea"}, geography={},
            pack_dir=Path("."),
        )
        args = dict(PROPOSE_ARGS, owner="Task Force 17 (TG 17.5)")
        out = handle_propose_route(state, theater=coral, **args)
        assert "已提交" in out
        assert state.pending_routes[0].owner == "TF17"  # 前缀命中归一化

    def test_propose_route_coral_sea_whitelist_rejects_midway_fleet(self):
        """注入 fake theater（id=coral-sea）→ midway 专属 TF16 不在白名单，拒绝。"""
        state = _make_state()
        coral = TheaterContext(
            id="coral-sea", name="珊瑚海",
            view={"center": {"lat": -15.2, "lon": 155.5}},
            bases=[], sectors=[], graticule={}, range_rings={}, scenario={},
            theater_raw={"name_en": "Coral Sea"}, geography={},
            pack_dir=Path("."),
        )
        out = handle_propose_route(state, theater=coral, **PROPOSE_ARGS)
        assert "Error" in out
        assert "TF17, TF11, TF44, MO" in out
        assert state.pending_routes == []

    def test_navigator_coral_sea_handlers_propose(self):
        """注入 coral-sea theater → tool_handlers 的 propose_route 按战区映射归一化。"""
        nav = NavigatorNPC(
            client=FakeLLMClient(),
            theater=TheaterContext(
                id="coral-sea", name="珊瑚海",
                view={"center": {"lat": -15.2, "lon": 155.5}},
                bases=[], sectors=[], graticule={}, range_rings={}, scenario={},
                theater_raw={"name_en": "Coral Sea"}, geography={},
                pack_dir=Path("."),
            ),
        )
        handler = nav.tool_handlers["propose_route"]
        state = _make_state()
        out = handler(
            state,
            owner="Task Force 11 (TG 17.8)",
            rationale="列克星敦西撤掩护航路，27 节。",
            waypoints=[{"lat": -15.7, "lon": 154.9}],
        )
        assert "已提交" in out
        assert state.pending_routes[0].owner == "TF11"

    def test_query_own_fleet_coral_sea_real_pack(self):
        """真实珊瑚海包：query_own_fleet 短名展示 TF17/TF11（战区驱动）。"""
        pack_dir = Path(__file__).resolve().parents[1] / "theaters" / "coral-sea"
        ctx = load_theater(pack_dir)
        state = build_initial_state(pack_dir / "scenario.json")
        out = handle_query_own_fleet(state, theater=ctx)
        assert "Task Force 17 (TG 17.5)（TF17）" in out
        assert "Task Force 11 (TG 17.8)（TF11）" in out


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


# ── comment 修订回路（POST /routes/{id}/comment：提意见→参谋修订→再审批）──

REVISED_ARGS = dict(
    PROPOSE_ARGS,
    rationale="依指挥官意见修订：第二航路点南移至 28.8N 以南，"
              "全程 92 海里，25 节约 3 小时 40 分。",
)

FEEDBACK_1 = "第二航路点太靠北，改到 28.8N 以南。"


class TestCommentRevisionLoop:

    @staticmethod
    def _swap_nav(client: TestClient, nav: NavigatorNPC) -> NavigatorNPC:
        """替换 server 的 navigator 为指定 fake 实例，返回原实例备用。"""
        saved = server.npcs["navigator"]
        server.npcs["navigator"] = nav
        return saved

    def test_comment_revises_then_approve_full_chain(self, client):
        """comment → 旧 revised/新 proposed → approve 新条目 → routes active 全链。"""
        _propose_via_npc(client)
        p1 = server.game_state.pending_routes[0]
        routes_before = len(server.game_state.routes)

        nav = NavigatorNPC(
            client=FakeLLMClient(planned_calls=[("propose_route", dict(REVISED_ARGS))])
        )
        saved = self._swap_nav(client, nav)
        server.game_state.action_points = server.game_state.max_action_points
        try:
            resp = client.post(
                f"/routes/{p1.route_id}/comment", json={"feedback": FEEDBACK_1}
            )
        finally:
            server.npcs["navigator"] = saved
        assert resp.status_code == 200
        assert resp.json()["revised_pending_id"]

        # feedback 已作为玩家消息追加进航海参谋会话
        assert any(
            m["role"] == "user" and "28.8N" in m["content"] for m in nav.messages
        )

        # 旧条目置 revised；新条目 proposed 且关联同一 route_id
        assert p1.status == PendingRouteStatus.REVISED
        created = [p for p in server.game_state.pending_routes if p.id != p1.id]
        assert len(created) == 1
        p2 = created[0]
        assert p2.status == PendingRouteStatus.PROPOSED
        assert p2.route_id == p1.route_id
        assert p2.feedback_history == [FEEDBACK_1]
        assert len(server.game_state.routes) == routes_before  # 尚未产生 Route

        # approve 新条目 → Route 落 state.routes（active），id 沿用链 route_id
        resp = client.post(f"/pending-routes/{p2.id}/approve")
        assert resp.status_code == 200
        assert resp.json()["route"]["status"] == "active"
        stored = next(
            r for r in server.game_state.routes if r.id == p2.route_id
        )
        assert stored.status == "active"
        assert stored.owner == "TF16"
        assert len(stored.waypoints) == 2

    def test_comment_multi_round_accumulates_feedback_history(self, client):
        """多轮修订：同链旧条目逐轮 revised，最新条目累积全量 feedback_history。"""
        nav = NavigatorNPC(client=FakeLLMClient(planned_calls=[
            ("propose_route", dict(PROPOSE_ARGS)),
            ("propose_route", dict(REVISED_ARGS)),
            ("propose_route", dict(REVISED_ARGS, rationale="二次修订：再南移 0.2°。")),
        ]))
        saved = self._swap_nav(client, nav)
        try:
            server.game_state.action_points = server.game_state.max_action_points
            assert client.post(
                "/navigator/propose", json={"message": "拟一条 TF16 航线。"}
            ).status_code == 200
            p1 = server.game_state.pending_routes[-1]
            rid = p1.route_id
            for fb in ("反馈一：航路点偏北。", "反馈二：再南移一点。"):
                server.game_state.action_points = server.game_state.max_action_points
                assert client.post(
                    f"/routes/{rid}/comment", json={"feedback": fb}
                ).status_code == 200
        finally:
            server.npcs["navigator"] = saved

        chain = [p for p in server.game_state.pending_routes if p.route_id == rid]
        assert [p.status for p in chain].count("revised") == 2
        latest = next(p for p in chain if p.status == "proposed")
        assert latest.feedback_history == ["反馈一：航路点偏北。", "反馈二：再南移一点。"]

    def test_comment_consumes_one_ap(self, client):
        """comment 消耗 1 AP（对齐 propose）。"""
        _propose_via_npc(client)
        p1 = server.game_state.pending_routes[0]
        ap_before = server.game_state.action_points

        nav = NavigatorNPC(
            client=FakeLLMClient(planned_calls=[("propose_route", dict(REVISED_ARGS))])
        )
        saved = self._swap_nav(client, nav)
        try:
            resp = client.post(
                f"/routes/{p1.route_id}/comment", json={"feedback": FEEDBACK_1}
            )
        finally:
            server.npcs["navigator"] = saved
        assert resp.status_code == 200
        assert resp.json()["ap"]["current"] == ap_before - 1

    def test_comment_without_ap_returns_400(self, client):
        """AP 不足返回 400（对齐 propose 端点既有模式）。"""
        _propose_via_npc(client)
        p1 = server.game_state.pending_routes[0]
        server.game_state.action_points = 0
        resp = client.post(
            f"/routes/{p1.route_id}/comment", json={"feedback": "再改改。"}
        )
        assert resp.status_code == 400

    def test_comment_unknown_route_404(self, client):
        """无关联提案的 route id 返回 404，不消耗 AP。"""
        ap_before = server.game_state.action_points
        resp = client.post(
            "/routes/nonexistent/comment", json={"feedback": "改。"}
        )
        assert resp.status_code == 404
        assert server.game_state.action_points == ap_before

    def test_comment_without_proposed_pending_404(self, client):
        """关联提案已不处于 proposed（如已批准）→ 404。"""
        _propose_via_npc(client)
        p1 = server.game_state.pending_routes[0]
        p1.status = PendingRouteStatus.APPROVED
        resp = client.post(
            f"/routes/{p1.route_id}/comment", json={"feedback": "改。"}
        )
        assert resp.status_code == 404
