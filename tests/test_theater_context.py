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
    assert ctx.graticule["minor_step"] == 0.25 and ctx.graticule["major_step"] == 1.0
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
