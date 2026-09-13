"""O.1 战役选择（正式玩法）— GET /theaters 列表 + POST /game/new 开新局。

用例：
- /theaters 扫 theaters/ 包摘要（midway 在列，含 scenario 双方兵力名）；
- /game/new 按 scenario 重建 GameState——脏状态（时钟/敌情/AP/航线/NPC 会话）
  全部重置为 scenario 初始态（ENT 28.2/-178.251012 等）；
- 未知战区 404 且全局状态不动。
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import server
from src.state import EnemyKnown, Position


def test_theaters_lists_midway():
    """GET /theaters 列出 theaters/ 全包摘要（O.2 珊瑚海包已入库，id 序）。"""
    client = TestClient(server.app)
    resp = client.get("/theaters")
    assert resp.status_code == 200
    theaters = resp.json()["theaters"]
    assert [t["id"] for t in theaters] == ["coral-sea", "midway"]

    coral = theaters[0]
    assert coral["name"] == "珊瑚海"
    assert coral["date"] == "1942-05-07"
    assert coral["view"]["lat"] == pytest.approx(-15.2)
    assert coral["view_nm"] == 800

    # scenario 摘要：双方兵力名（不含坐标军情）
    coral_scen = coral["scenario"]
    coral_enemy = coral_scen["enemy_force"]
    assert coral_enemy["name"] == "MO 机动部队"
    assert set(coral_enemy["carriers"]) == {"Shokaku", "Zuikaku"}
    coral_friendly = coral_scen["friendly_forces"]
    assert {tf["callsign"] for tf in coral_friendly} == {"YOR", "LEX"}
    yor = next(tf for tf in coral_friendly if tf["callsign"] == "YOR")
    assert yor["name"] == "Task Force 17 (TG 17.5)"
    assert any("Yorktown" in c for c in yor["carriers"])

    midway = theaters[1]
    assert midway["name"] == "中途岛"
    assert midway["date"] == "1942-06-04"
    assert midway["view"]["lat"] == pytest.approx(28.2)
    assert midway["view_nm"] == 45

    # scenario 摘要：双方兵力名（不含坐标军情）
    scen = midway["scenario"]
    enemy = scen["enemy_force"]
    assert enemy["name"] == "Kido Butai"
    assert set(enemy["carriers"]) == {"Akagi", "Kaga", "Soryu", "Hiryu"}
    friendly = scen["friendly_forces"]
    assert {tf["callsign"] for tf in friendly} == {"ENT", "HOR"}
    ent = next(tf for tf in friendly if tf["callsign"] == "ENT")
    assert ent["name"] == "Task Force 16"
    assert any("Enterprise" in c for c in ent["carriers"])


def test_game_new_rebuilds_state_from_scenario():
    """POST /game/new midway：脏状态重建为 scenario 初始态（时钟/AP/敌情/航线/NPC 全重置）。"""
    client = TestClient(server.app)

    # 弄脏全局状态：推进时钟、挂敌情、耗 AP、建航线、NPC 会话留言
    server.game_state.clock.game_time = datetime(1942, 6, 5, 18, 0, tzinfo=timezone.utc)
    server.game_state.known_enemy.append(EnemyKnown(
        position=Position(lat=30.0, lon=-179.0),
        description="敌航母约 4 艘",
        source="PBY",
        reported_at=datetime(1942, 6, 5, 10, 0, tzinfo=timezone.utc),
    ))
    server.game_state.action_points = 0
    resp_route = client.post("/routes", json={
        "kind": "planned", "owner": "TF16",
        "waypoints": [{"lat": 28.2, "lon": -177.4}],
    })
    assert resp_route.status_code == 200
    server.npcs["browning"].messages.append({"role": "user", "content": "stale"})

    resp = client.post("/game/new", json={"theater_id": "midway"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["state"]["theater_id"] == "midway"

    # /state 与 scenario 一致（ENT 28.2/-178.251012、04:00、course 270、AP 3/3、敌情清空）
    state = client.get("/state").json()
    assert state["clock"]["game_time"].startswith("1942-06-04T04:00")
    tf = state["task_forces"][0]
    assert tf["course"] == 270
    ent = tf["carriers"][0]
    assert ent["name"] == "USS Enterprise (CV-6)"
    assert ent["position"]["lat"] == pytest.approx(28.2)
    assert ent["position"]["lon"] == pytest.approx(-178.251012, abs=1e-6)
    hor = tf["carriers"][1]
    assert hor["position"]["lon"] == pytest.approx(-177.929519, abs=1e-6)
    assert state["known_enemy"] == []
    assert state["ap"]["current"] == 3
    assert state["ap"]["max"] == 3

    # 航线重置
    assert client.get("/routes").json()["routes"] == []

    # NPC 会话清空 + 航海参谋战区上下文热替换
    assert all(npc.messages == [] for npc in server.npcs.values())
    assert server.npcs["navigator"].theater.id == "midway"


def test_game_new_unknown_theater_404():
    """POST /game/new 未知战区 → 404，全局状态不动（珊瑚海包属 O.2）。"""
    client = TestClient(server.app)
    before = server.game_state.clock.game_time
    resp = client.post("/game/new", json={"theater_id": "coral_sea"})
    assert resp.status_code == 404
    assert server.game_state.clock.game_time == before


def test_game_new_coral_sea_rebuilds_state_from_scenario():
    """POST /game/new coral-sea：状态重建为珊瑚海包 scenario 初始态（O.3）。

    断言：时钟=clock_start（1942-05-06T21:00Z = 当地 UTC+10 五月七日 07:00，
    即 date=1942-05-07 的时区语义）、双盟军舰队 YOR/LEX 位置=scenario 值、
    敌舰队=MO 机动部队（翔鹤/瑞鹤，日军，位置=scenario 值）、
    known_enemy 初始为空（可视性分层：actual_enemy 不经玩家态下发）。
    """
    client = TestClient(server.app)
    resp = client.post("/game/new", json={"theater_id": "coral-sea"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["state"]["theater_id"] == "coral-sea"

    # /state：时钟 = scenario.clock_start（当地 5 月 7 日黎明，UTC+10）
    state = client.get("/state").json()
    assert state["clock"]["game_time"].startswith("1942-05-06T21:00")
    assert server.game_state.clock.game_time.astimezone(
        timezone(timedelta(hours=10))
    ).strftime("%Y-%m-%dT%H:%M") == "1942-05-07T07:00"

    # /state：双盟军舰队（YOR=TF17 约克城 / LEX=TF11 列克星敦），位置=scenario 值
    tfs = {tf["name"]: tf for tf in state["task_forces"]}
    assert set(tfs) == {"Task Force 17 (TG 17.5)", "Task Force 11 (TG 17.8)"}
    yor = tfs["Task Force 17 (TG 17.5)"]
    assert yor["course"] == 315 and yor["speed"] == 27
    assert yor["carriers"][0]["name"] == "USS Yorktown (CV-5)"
    assert yor["carriers"][0]["position"]["lat"] == pytest.approx(-15.5)
    assert yor["carriers"][0]["position"]["lon"] == pytest.approx(155.6)
    lex = tfs["Task Force 11 (TG 17.8)"]
    assert lex["carriers"][0]["name"] == "USS Lexington (CV-2)"
    assert lex["carriers"][0]["position"]["lat"] == pytest.approx(-15.7)
    assert lex["carriers"][0]["position"]["lon"] == pytest.approx(155.4)

    # /state：known_enemy 初始为空（敌情经侦察产生，actual 不漏玩家态）
    assert state["known_enemy"] == []

    # 敌舰队（结构化实体）= MO 机动部队：日军、翔鹤/瑞鹤、位置=scenario 值
    enemy = server.game_state.enemy_fleet
    assert enemy.name == "MO 机动部队"
    assert enemy.faction == "japan"
    assert {c.name for c in enemy.carriers} == {"Shokaku", "Zuikaku"}
    assert enemy.position.lat == pytest.approx(-12.0)
    assert enemy.position.lon == pytest.approx(157.0)
    assert enemy.course == 210 and enemy.speed == 20

    # 实际敌情（god-view）含 MO 机动部队条目；状态对象不含中途岛旧态
    assert any("MO" in e["name"] for e in server.game_state.actual_enemy)
    assert server.game_state.task_forces[0].name != "Task Force 16"

    # 切回中途岛：战区可重入切换（全局状态/战区上下文还原，下游测试不污染）
    resp = client.post("/game/new", json={"theater_id": "midway"})
    assert resp.status_code == 200
    state = client.get("/state").json()
    assert state["clock"]["game_time"].startswith("1942-06-04T04:00")
    assert server.npcs["navigator"].theater.id == "midway"


def test_build_initial_state_midway_default_unchanged():
    """build_initial_state 缺省路径（中途岛）行为不变——参数化不回归旧包。"""
    from src.initial_state import build_initial_state
    s = build_initial_state()
    assert s.clock.game_time == datetime(1942, 6, 4, 4, 0, tzinfo=timezone.utc)
    assert s.task_forces[0].name == "Task Force 16"
    assert s.enemy_fleet.name == "Kido Butai"
