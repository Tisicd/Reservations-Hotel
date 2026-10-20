import uuid

from fastapi.testclient import TestClient


def test_fail_closed_puerto_cerrado(monkeypatch):
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", "59999")
    monkeypatch.setenv("DB_USER", "availability")
    monkeypatch.setenv("DB_PASSWORD", "x")
    monkeypatch.setenv("DB_NAME", "availability_db")
    monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)

    from app.main import create_app

    app = create_app()
    client = TestClient(app)

    r = client.get("/ready")
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "1"

    body = {
        "hold_id": str(uuid.uuid4()),
        "room_id": str(uuid.uuid4()),
        "check_in": "2026-11-10",
        "check_out": "2026-11-12",
        "units": 1,
    }
    r = client.post("/holds", json=body)
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "1"
    assert r.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
