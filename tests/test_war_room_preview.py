from pathlib import Path

from fastapi.testclient import TestClient

import server


def test_preview_serves_independently_of_active_game():
    client = TestClient(server.app)
    active_game = server.game_state
    response = client.get("/war-room-preview")
    assert response.status_code == 200
    assert 'id="telegram"' in response.text
    assert 'id="staff"' in response.text
    assert 'id="order"' in response.text
    assert server.game_state is active_game
    assert 'war-room-preview.js' not in client.get("/").text


def test_preview_geography_uses_coral_sea_without_switching_theater():
    client = TestClient(server.app)
    active_theater = server.theater_ctx
    response = client.get("/war-room-preview/geography")
    assert response.status_code == 200
    assert response.content == (
        Path(server.__file__).parent / "theaters" / "coral-sea" / "geography.geojson"
    ).read_bytes()
    assert server.theater_ctx is active_theater
