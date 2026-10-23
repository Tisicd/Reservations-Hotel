import datetime as dt
import json
import os
import pathlib
import sys
import time
import uuid

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "invariants"))

from checker import check_all  # noqa: E402

PUBLIC_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8088/api").rstrip("/")
ADMIN_URL = os.getenv("GATEWAY_ADMIN_URL", "http://127.0.0.1:8081/svc").rstrip("/")
RESERVATION_URL = os.getenv("RESERVATION_URL", PUBLIC_URL)
RESERVATION_ADMIN_URL = os.getenv("RESERVATION_ADMIN_URL", f"{ADMIN_URL}/reservation")
AVAILABILITY_URL = os.getenv("AVAILABILITY_URL", PUBLIC_URL)
AVAILABILITY_ADMIN_URL = os.getenv("AVAILABILITY_ADMIN_URL", f"{ADMIN_URL}/availability")
INVENTORY_URL = os.getenv("INVENTORY_URL", f"{ADMIN_URL}/availability")
PAYMENT_URL = os.getenv("PAYMENT_URL", f"{ADMIN_URL}/payment")
CUSTOMER_URL = os.getenv("CUSTOMER_URL", PUBLIC_URL)
HOTEL_URL = os.getenv("HOTEL_URL", PUBLIC_URL)
HOTEL_ADMIN_URL = os.getenv("HOTEL_ADMIN_URL", f"{ADMIN_URL}/hotel")


class Stack:
    def __init__(self, manifest: dict, client: httpx.Client):
        self.manifest = manifest
        self.client = client
        self.run_id = uuid.uuid4().hex[:8]
        self.hotel = manifest["hotels"][0]
        self.room = self.hotel["rooms"][0]
        self.customers = manifest["customers"]

    def _json(self, response: httpx.Response) -> dict:
        response.raise_for_status()
        return response.json()

    def ensure_room(self) -> None:
        """Habitación dedicada por ejecución: no colisiona con corridas previas."""
        room_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"e2e:{self.run_id}:room"))
        response = self.client.post(
            f"{HOTEL_ADMIN_URL}/hotels/{self.hotel['id']}/rooms",
            json={"id": room_id, "name": f"E2E {self.run_id}", "capacity": 2,
                  "price_per_night_cents": 5000, "currency": "USD"},
        )
        response.raise_for_status()
        self.room = response.json()

    def available(self, day, admin: bool = False) -> int:
        base = AVAILABILITY_ADMIN_URL if admin else AVAILABILITY_URL
        body = self._json(
            self.client.get(
                f"{base}/availability",
                params={
                    "hotel_id": self.hotel["id"],
                    "check_in": day.isoformat(),
                    "check_out": (day + dt.timedelta(days=1)).isoformat(),
                },
            )
        )
        for room in body["rooms"]:
            if room["room_id"] == self.room["id"]:
                return room["available"]
        raise AssertionError("la habitación sembrada no aparece en la disponibilidad")

    def put_inventory(self, day, total: int, room_id: str | None = None) -> None:
        response = self.client.put(
            f"{INVENTORY_URL}/inventory/{room_id or self.room['id']}",
            json={
                "hotel_id": self.hotel["id"],
                "from": day.isoformat(),
                "to": (day + dt.timedelta(days=1)).isoformat(),
                "total": total,
            },
        )
        response.raise_for_status()

    def create_customer(self, email: str) -> dict:
        response = self.client.post(
            f"{CUSTOMER_URL}/customers", json={"name": "E2E", "email": email}
        )
        response.raise_for_status()
        return response.json()

    def create_reservation(
        self, key: str, day, customer_id: str, simulate: str = "ok",
        admin: bool = False, **kwargs
    ) -> httpx.Response:
        base = RESERVATION_ADMIN_URL if admin else RESERVATION_URL
        body = {
            "customer_id": customer_id,
            "hotel_id": kwargs.get("hotel_id", self.hotel["id"]),
            "room_id": kwargs.get("room_id", self.room["id"]),
            "check_in": day.isoformat(),
            "check_out": (day + dt.timedelta(days=kwargs.get("nights", 1))).isoformat(),
            "payment": {"method": "card", "token": "tok_demo", "simulate": simulate},
        }
        return self.client.post(
            f"{base}/reservations",
            json=body,
            headers={"Idempotency-Key": key, "X-Request-ID": f"e2e-{key}"},
        )

    def list_reservations(self, customer_id: str, admin: bool = False) -> list[dict]:
        base = RESERVATION_ADMIN_URL if admin else RESERVATION_URL
        return self._json(
            self.client.get(
                f"{base}/reservations", params={"customer_id": customer_id}
            )
        )

    def confirmed_on(self, customers: list[dict], day) -> list[dict]:
        """Reservas CONFIRMED de esos clientes en ese día (estado final)."""
        out = []
        for customer in customers:
            for item in self.list_reservations(customer["id"], admin=True):
                if item["check_in"] == day.isoformat() and \
                        item["status"] == "CONFIRMED":
                    out.append(item)
        return out

    def reservation(self, reservation_id: str) -> dict:
        return self._json(
            self.client.get(f"{RESERVATION_URL}/reservations/{reservation_id}")
        )

    def wait_status(self, reservation_id: str, expected, timeout: float = 90) -> dict:
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            last = self.reservation(reservation_id)
            if last["status"] in expected:
                return last
            time.sleep(0.5)
        raise AssertionError(
            f"reserva {reservation_id} no llegó a {expected}; último estado {last}"
        )

    def events(self, reservation_id: str) -> list[dict]:
        return self._json(
            self.client.get(f"{RESERVATION_URL}/reservations/{reservation_id}/events")
        )

    def payment_of(self, reservation_id: str) -> dict | None:
        response = self.client.get(
            f"{PAYMENT_URL}/payments", params={"reservation_id": reservation_id}
        )
        if response.status_code == 404:
            return None
        return self._json(response)

    def cancel(self, reservation_id: str) -> httpx.Response:
        return self.client.post(f"{RESERVATION_URL}/reservations/{reservation_id}/cancel")

    def notifications(self, reservation_id: str) -> list[dict]:
        return self._json(
            self.client.get(
                f"{PUBLIC_URL}/notifications",
                params={"reservation_id": reservation_id},
            )
        )

    def post_notification(self, body: dict) -> httpx.Response:
        return self.client.post(f"{ADMIN_URL}/notification/notifications", json=body)


@pytest.fixture(scope="session")
def manifest() -> dict:
    path = ROOT / "secrets" / "seed.json"
    if not path.exists():
        pytest.fail("falta secrets/seed.json; ejecuta `make up-dev && make seed`", pytrace=False)
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def stack(manifest) -> Stack:
    with httpx.Client(timeout=40) as client:
        stack = Stack(manifest, client)
        stack.ensure_room()
        yield stack


@pytest.fixture()
def invariants():
    def _check() -> None:
        violations = check_all(grace_seconds=60)
        assert not violations, "invariantes violados:\n" + "\n".join(
            str(violation) for violation in violations
        )

    return _check
