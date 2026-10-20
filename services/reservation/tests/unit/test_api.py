import datetime as dt
import uuid

from fastapi.testclient import TestClient

from app.domain.errors import InvalidState, ReservationNotFound
from app.domain.reservation import Reservation
from app.domain.state_machine import CANCELLED, CONFIRMED, RECEIVED
from app.main import create_app

BODY = {
    "customer_id": str(uuid.uuid4()),
    "hotel_id": str(uuid.uuid4()),
    "room_id": str(uuid.uuid4()),
    "check_in": "2026-11-10",
    "check_out": "2026-11-13",
    "payment": {"method": "card", "token": "tok_demo", "simulate": "ok"},
}


def _reservation(status=CONFIRMED, reason=None) -> Reservation:
    now = dt.datetime.now(dt.UTC)
    return Reservation(
        id=uuid.uuid4(),
        idempotency_key="key",
        request_hash="hash",
        customer_id=uuid.UUID(BODY["customer_id"]),
        hotel_id=uuid.UUID(BODY["hotel_id"]),
        room_id=uuid.UUID(BODY["room_id"]),
        check_in=dt.date(2026, 11, 10),
        check_out=dt.date(2026, 11, 13),
        nights=3,
        amount_cents=30000,
        currency="USD",
        payment_method="card",
        payment_token="tok_demo",
        payment_simulate="ok",
        status=status,
        status_reason=reason,
        payment_id=uuid.uuid4(),
        payment_status="SUCCEEDED",
        attempts=0,
        next_attempt_at=now,
        phase_started_at=now,
        version=1,
        created_at=now,
        updated_at=now,
    )


class FakeService:
    def __init__(self, reservation=None, replayed=False, cancel_error=None):
        self.reservation = reservation or _reservation()
        self.replayed = replayed
        self.cancel_error = cancel_error
        self.last_key = None
        self.last_command = None

    def create_reservation(self, key, command):
        self.last_key = key
        self.last_command = command
        return self.reservation, self.replayed

    def get_reservation(self, _id):
        if self.reservation is None:
            raise ReservationNotFound()
        return self.reservation

    def list_by_customer(self, _customer_id):
        return [self.reservation]

    def cancel_reservation(self, _id):
        if self.cancel_error:
            raise self.cancel_error
        return self.reservation

    def events(self, _id):
        now = dt.datetime.now(dt.UTC)
        return [
            {
                "reservation_id": self.reservation.id,
                "from_status": None,
                "to_status": RECEIVED,
                "reason": None,
                "at": now,
            }
        ]

    def ping(self):
        return None


def _client(service) -> TestClient:
    return TestClient(create_app(service))


def test_created_201_y_representacion():
    service = FakeService()
    response = _client(service).post(
        "/reservations", json=BODY, headers={"Idempotency-Key": "key-1"}
    )
    assert response.status_code == 201
    assert response.headers.get("Idempotent-Replayed") is None
    body = response.json()
    assert body["status"] == CONFIRMED
    assert body["payment"]["status"] == "SUCCEEDED"
    assert service.last_key == "key-1"
    assert str(service.last_command.check_in) == "2026-11-10"


def test_en_proceso_202_con_location():
    response = _client(FakeService(_reservation(RECEIVED))).post(
        "/reservations", json=BODY, headers={"Idempotency-Key": "key-2"}
    )
    assert response.status_code == 202
    assert response.headers["Location"] == f"/reservations/{response.json()['id']}"


def test_replay_200_con_cabecera():
    response = _client(FakeService(replayed=True)).post(
        "/reservations", json=BODY, headers={"Idempotency-Key": "key-3"}
    )
    assert response.status_code == 200
    assert response.headers["Idempotent-Replayed"] == "true"


def test_sin_idempotency_key_422_con_formato():
    response = _client(FakeService()).post("/reservations", json=BODY)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["request_id"]


def test_cuerpo_invalido_422_con_formato():
    invalid = dict(BODY, check_in="no-es-fecha")
    response = _client(FakeService()).post(
        "/reservations", json=invalid, headers={"Idempotency-Key": "key-4"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]


def test_request_id_se_propaga():
    response = _client(FakeService()).get("/health", headers={"X-Request-ID": "req-9"})
    assert response.headers["X-Request-ID"] == "req-9"


def test_get_inexistente_404():
    service = FakeService()
    service.reservation = None
    response = _client(service).get(f"/reservations/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_cancelar_desde_estado_invalido_409():
    service = FakeService(cancel_error=InvalidState("no se puede cancelar"))
    response = _client(service).post(f"/reservations/{uuid.uuid4()}/cancel")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"


def test_cancelado_200_y_eventos_mapeados():
    service = FakeService(_reservation(CANCELLED))
    client = _client(service)
    reservation_id = service.reservation.id
    assert client.post(f"/reservations/{reservation_id}/cancel").status_code == 200

    events = client.get(f"/reservations/{reservation_id}/events").json()
    assert events[0]["from"] is None
    assert events[0]["to"] == RECEIVED
    assert events[0]["at"]
