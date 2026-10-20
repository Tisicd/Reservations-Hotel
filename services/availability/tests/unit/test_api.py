import datetime as dt
import uuid

from fastapi.testclient import TestClient

from app.api.deps import get_service
from app.application.use_cases import AvailabilityService
from app.domain.errors import NoInventory
from app.main import app


class FakeStore:
    def put_inventory(self, *a, **k):
        return None

    def search(self, *a, **k):
        return []

    def create_hold(self, *a, **k):
        return (None, True)

    def extend_hold(self, *a, **k):
        return None

    def confirm_hold(self, *a, **k):
        return None

    def release_hold(self, *a, **k):
        return None

    def get_hold(self, *a, **k):
        return None

    def expire_due(self, *a, **k):
        return []

    def ping(self):
        return None


def _client(store):
    app.dependency_overrides[get_service] = lambda: AvailabilityService(store)
    return TestClient(app)


def test_health():
    r = _client(FakeStore()).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_x_request_id_se_genera_y_se_devuelve():
    r = _client(FakeStore()).get("/health")
    assert r.headers.get("X-Request-ID")


def test_x_request_id_se_propaga():
    r = _client(FakeStore()).get("/health", headers={"X-Request-ID": "req-123"})
    assert r.headers["X-Request-ID"] == "req-123"


def test_no_inventory_formato_error():
    class Store(FakeStore):
        def create_hold(self, *a, **k):
            raise NoInventory("sin cupo")

    body = {
        "hold_id": str(uuid.uuid4()),
        "room_id": str(uuid.uuid4()),
        "check_in": "2026-11-10",
        "check_out": "2026-11-12",
        "units": 1,
    }
    r = _client(Store()).post("/holds", json=body)
    assert r.status_code == 409
    payload = r.json()
    assert payload["error"]["code"] == "NO_INVENTORY"
    assert payload["error"]["request_id"] is not None
    assert "details" in payload["error"]


def test_hold_create_replay_200():
    class Store(FakeStore):
        def create_hold(self, *a, **k):
            from app.domain.hold import Hold

            hold = Hold(
                hold_id=a[0],
                room_id=a[1],
                check_in=a[2],
                check_out=a[3],
                units=a[4],
                status="HELD",
                expires_at=dt.datetime.now(dt.UTC),
                created_at=dt.datetime.now(dt.UTC),
                updated_at=dt.datetime.now(dt.UTC),
            )
            return hold, False

    body = {
        "hold_id": str(uuid.uuid4()),
        "room_id": str(uuid.uuid4()),
        "check_in": "2026-11-10",
        "check_out": "2026-11-12",
        "units": 1,
    }
    r = _client(Store()).post("/holds", json=body)
    assert r.status_code == 200
    assert r.json()["status"] == "HELD"
