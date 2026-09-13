"""TheaterContext 加载与 GET /theater 下发端点（CHART_SYSTEM.md §三/§四/§九决议6）。"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.theater import load_theater

BASE = Path(__file__).resolve().parent.parent
PACK = BASE / "theaters" / "midway"


def test_load_theater_success():
    """加载 midway 战区包成功，核心字段就位。"""
    ctx = load_theater(PACK)
    assert ctx.id == "midway"
    assert ctx.name == "中途岛"
    assert ctx.view["center"] == {"lat": 28.2, "lon": -177.4}
    assert ctx.view["view_nm"] == 45


def test_theater_context_fields():
    """结构化字段 / scenario 摘要 / 原始 dict 保留（/theater 原样下发用）。"""
    ctx = load_theater(PACK)
    assert ctx.bases and ctx.bases[0]["id"] == "midway"
    assert ctx.sectors and ctx.sectors[0]["id"] == "east-quad"
    assert ctx.graticule["minor_step"] == 0.25 and ctx.graticule["major_step"] == 0.5  # R-M1 对齐渲染现状
    assert ctx.range_rings["rings_nm"] == [20, 25, 40, 60]
    # scenario 摘要（战区剧本）
    assert ctx.scenario["id"] == "midway"
    assert len(ctx.scenario["task_forces"]) == 2
    # 原始 dict 原样保留
    assert ctx.theater_raw == json.loads((PACK / "theater.json").read_text())
    assert ctx.geography["type"] == "FeatureCollection"


def test_get_theater_endpoint():
    """GET /theater 返回战区包合并 JSON（前端 ChartEngine 唯一来源）。"""
    import server

    client = TestClient(server.app)
    resp = client.get("/theater")
    assert resp.status_code == 200
    data = resp.json()
    assert data["theater"] == server.theater_ctx.theater_raw
    assert data["geography"] == server.theater_ctx.geography
    assert data["theater"]["id"] == "midway"
    assert data["geography"]["features"], "geography 应含 features"


def test_initial_state_deployment_matches_scenario():
    """M.4 scenario 布兵守卫：initial_state ENT/HOR 初始位与 scenario.json 同源。

    实体层投影唯一化（与底图同投影）后，舰队按 scenario 真实位直接落成品图构图
    （ENT 图左外缘/HOR 环礁西缘）——此后端守卫与 route_display.test.mjs 的前端
    BUILTIN 一致性守卫配对，双向防字面量静默分叉。
    """
    from src.initial_state import build_initial_state

    scenario = json.loads((PACK / "scenario.json").read_text())
    deploy = {tf["callsign"]: tf for tf in scenario["task_forces"]}

    state = build_initial_state()
    assert len(state.task_forces) == 1  # 兵力结构不变：双航母同编 TF16
    ent, hor = state.task_forces[0].carriers
    assert ent.name == "USS Enterprise (CV-6)"
    assert hor.name == "USS Hornet (CV-8)"
    assert (ent.position.lat, ent.position.lon) == (deploy["ENT"]["lat"], deploy["ENT"]["lon"])
    assert (hor.position.lat, hor.position.lon) == (deploy["HOR"]["lat"], deploy["HOR"]["lon"])
    assert state.task_forces[0].course == deploy["ENT"]["course"]
    assert state.task_forces[0].speed == deploy["ENT"]["speed"]
