import re

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_render_origin_supports_a_complete_message_request(engine, monkeypatch):
    origin = "https://example-reception.onrender.com"
    monkeypatch.setenv("RENDER_EXTERNAL_URL", origin)
    client = TestClient(create_app(engine))
    session = client.post("/api/sessions", json={}, headers={"Origin": origin}).json()
    response = client.post(f"/api/sessions/{session['id']}/messages", headers={"Origin": origin},
                           json={"message": "What are your opening hours?", "request_id": "hosted-example-1"})
    assert response.status_code == 200
    assert response.json()['messages'][-1]['decision']['action'] == 'get_clinic_hours'
    assert client.post("/api/sessions", headers={"Origin": "https://other.onrender.com"}).status_code == 403


def test_custom_origin_and_local_development_can_coexist(engine, monkeypatch):
    monkeypatch.setenv("PUBLIC_ORIGIN", "https://reception.example/")
    client = TestClient(create_app(engine))
    for origin in ("https://reception.example", "http://127.0.0.1:5173"):
        assert client.post("/api/sessions", json={}, headers={"Origin": origin}).status_code == 200


@pytest.mark.parametrize("value", ["*", "https://reception.example/path", "https://user:password@example.com"])
def test_hosted_origin_configuration_fails_closed(engine, monkeypatch, value):
    monkeypatch.setenv("PUBLIC_ORIGIN", value)
    with pytest.raises(RuntimeError, match="PUBLIC_ORIGIN"):
        create_app(engine)


def test_built_frontend_and_api_share_one_server(engine):
    client = TestClient(create_app(engine))
    page = client.get("/")
    if page.status_code == 404:
        pytest.skip("Run npm --prefix frontend run build to validate the built UI.")
    assert page.status_code == 200
    assert '<title>Reception' in page.text
    script = re.search(r'src="(/assets/[^\"]+\.js)"', page.text)
    assert script is not None
    assert client.get(script[1]).status_code == 200
    assert client.get("/api/health").json()['status'] == 'ok'
    report = client.get("/attendance/")
    assert report.status_code == 200
    assert 'Appointment attendance' in report.text and 'results-data' in report.text
    assert client.get("/.env").status_code == 404
    assert client.get("/backend/app/main.py").status_code == 404
