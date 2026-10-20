import uuid

from fastapi.testclient import TestClient


def test_fail_closed_puerto_cerrado(monkeypatch):
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", "59999")
    monkeypatch.setenv("DB_USER", "payment")
    monkeypatch.setenv("DB_PASSWORD", "x")
    monkeypatch.setenv("DB_NAME", "payment_db")
    monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)

    from app.main import create_app

    client = TestClient(create_app())

    r = client.get("/ready")
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "1"

    reservation = uuid.uuid4()
    body = {
        "reservation_id": str(reservation),
        "amount_cents": 30000,
        "currency": "USD",
        "method": "card",
        "token": "tok_demo",
        "simulate": "ok",
    }
    r = client.post("/payments", json=body, headers={"Idempotency-Key": str(reservation)})
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "1"
    assert r.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
