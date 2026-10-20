import uuid

from fakes import FakeProvider, FakeRepo
from fastapi.testclient import TestClient

from app.api.deps import get_service
from app.application.use_cases import PaymentService
from app.main import app


def _client(simulation_enabled=True, provider=None):
    service = PaymentService(
        FakeRepo(), provider or FakeProvider(), simulation_enabled=simulation_enabled
    )
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app), service


def _body(reservation=None, simulate="ok", amount=30000):
    return {
        "reservation_id": str(reservation or uuid.uuid4()),
        "amount_cents": amount,
        "currency": "USD",
        "method": "card",
        "token": "tok_demo",
        "simulate": simulate,
    }


def test_health():
    client, _ = _client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready():
    client, _ = _client()
    assert client.get("/ready").status_code == 200


def test_x_request_id_se_genera_y_propaga():
    client, _ = _client()
    assert client.get("/health").headers.get("X-Request-ID")
    r = client.get("/health", headers={"X-Request-ID": "req-1"})
    assert r.headers["X-Request-ID"] == "req-1"


def test_idempotency_key_obligatoria():
    client, _ = _client()
    r = client.post("/payments", json=_body())
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_replay():
    client, _ = _client()
    reservation = uuid.uuid4()
    body = _body(reservation)
    headers = {"Idempotency-Key": str(reservation)}
    r1 = client.post("/payments", json=body, headers=headers)
    assert r1.status_code == 201
    assert r1.json()["status"] == "SUCCEEDED"
    assert r1.json()["reservation_id"] == str(reservation)

    r2 = client.post("/payments", json=body, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"]


def test_decline_status():
    client, _ = _client(provider=FakeProvider(outcome="DECLINED"))
    reservation = uuid.uuid4()
    r = client.post(
        "/payments",
        json=_body(reservation, simulate="decline"),
        headers={"Idempotency-Key": str(reservation)},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "DECLINED"


def test_refund_invalid_state():
    client, _ = _client(provider=FakeProvider(outcome="DECLINED"))
    reservation = uuid.uuid4()
    r = client.post(
        "/payments",
        json=_body(reservation, simulate="decline"),
        headers={"Idempotency-Key": str(reservation)},
    )
    payment_id = r.json()["id"]
    refund = client.post(f"/payments/{payment_id}/refund")
    assert refund.status_code == 409
    assert refund.json()["error"]["code"] == "INVALID_STATE"


def test_simulacion_deshabilitada():
    client, _ = _client(simulation_enabled=False)
    reservation = uuid.uuid4()
    r = client.post(
        "/payments",
        json=_body(reservation, simulate="decline"),
        headers={"Idempotency-Key": str(reservation)},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SIMULATION_DISABLED"


def test_pago_inexistente_404():
    client, _ = _client()
    r = client.get(f"/payments/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    r = client.get(f"/payments?reservation_id={uuid.uuid4()}")
    assert r.status_code == 404


def test_clave_distinta_rechaza_422():
    client, _ = _client()
    reservation = uuid.uuid4()
    r = client.post(
        "/payments", json=_body(reservation), headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
