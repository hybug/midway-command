"""Route 模型与航线 API（CHART_SYSTEM.md §5.1 三类航线）。

用例：建（POST /routes → draft）/ 批（approve → active）/
撤（cancel → cancelled）/ 列（GET /routes）；
N.1 补齐：非法状态转换（approve 非 draft、cancel 终态）→ 400。
"""
import pytest
from fastapi.testclient import TestClient

import server
from src.routes import RouteStatus

WAYPOINTS = [
    {"lat": 28.2, "lon": -177.4},
    {"lat": 28.4, "lon": -177.0, "eta": "1942-06-04T06:00:00"},
]


def _create_planned(client: TestClient, owner: str = "TF16") -> dict:
    resp = client.post("/routes", json={
        "kind": "planned",
        "owner": owner,
        "waypoints": WAYPOINTS,
    })
    assert resp.status_code == 200
    return resp.json()


def test_create_route_makes_draft():
    """POST /routes 建草案航线（draft）并入库 GameState。"""
    client = TestClient(server.app)
    route = _create_planned(client)

    assert route["id"]
    assert route["kind"] == "planned"
    assert route["owner"] == "TF16"
    assert route["status"] == "draft"
    assert route["waypoints"][0]["lat"] == 28.2
    assert route["waypoints"][0]["eta"] is None
    assert route["waypoints"][1]["eta"] == "1942-06-04T06:00:00"
    assert any(r.id == route["id"] for r in server.game_state.routes)


def test_approve_route_activates():
    """POST /routes/{id}/approve：draft → active；未知 id 返回 404。"""
    client = TestClient(server.app)
    route = _create_planned(client)

    resp = client.post(f"/routes/{route['id']}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    stored = next(r for r in server.game_state.routes if r.id == route["id"])
    assert stored.status == "active"

    assert client.post("/routes/nonexistent/approve").status_code == 404


def test_cancel_route():
    """POST /routes/{id}/cancel：draft → cancelled；未知 id 返回 404。"""
    client = TestClient(server.app)
    route = _create_planned(client)

    resp = client.post(f"/routes/{route['id']}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    stored = next(r for r in server.game_state.routes if r.id == route["id"])
    assert stored.status == "cancelled"

    assert client.post("/routes/nonexistent/cancel").status_code == 404


def test_list_routes():
    """GET /routes 列出全部已建航线。"""
    client = TestClient(server.app)
    route_a = _create_planned(client, owner="TF16")
    route_b = _create_planned(client, owner="ENT")

    resp = client.get("/routes")
    assert resp.status_code == 200
    listed = {r["id"]: r for r in resp.json()["routes"]}
    assert listed[route_a["id"]]["owner"] == "TF16"
    assert listed[route_b["id"]]["owner"] == "ENT"
    assert listed[route_b["id"]]["status"] == "draft"


# ── N.1 遗留：非法状态转换防护用例 ──

def _to_status(client: TestClient, route_id: str, status: str) -> None:
    """把指定 route 推到目标状态（done 由 N.4 航行完成置位，直接注入）。"""
    if status == "active":
        assert client.post(f"/routes/{route_id}/approve").status_code == 200
    elif status == "cancelled":
        assert client.post(f"/routes/{route_id}/cancel").status_code == 200
    elif status == "done":
        stored = next(r for r in server.game_state.routes if r.id == route_id)
        stored.status = RouteStatus.DONE


@pytest.mark.parametrize("status", ["active", "done", "cancelled"])
def test_approve_non_draft_route_returns_400(status):
    """approve 仅接受 draft：active/done/cancelled 一律 400 且状态不变。"""
    client = TestClient(server.app)
    route = _create_planned(client)
    _to_status(client, route["id"], status)

    resp = client.post(f"/routes/{route['id']}/approve")
    assert resp.status_code == 400
    stored = next(r for r in server.game_state.routes if r.id == route["id"])
    assert stored.status == RouteStatus(status)  # 未被非法批准改动


@pytest.mark.parametrize("status", ["done", "cancelled"])
def test_cancel_terminal_route_returns_400(status):
    """cancel 仅接受 draft/active：终态 done/cancelled 一律 400 且状态不变。"""
    client = TestClient(server.app)
    route = _create_planned(client)
    _to_status(client, route["id"], status)

    resp = client.post(f"/routes/{route['id']}/cancel")
    assert resp.status_code == 400
    stored = next(r for r in server.game_state.routes if r.id == route["id"])
    assert stored.status == RouteStatus(status)  # 未被非法撤销改动
