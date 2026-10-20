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

RESERVATION_URL = os.getenv("RESERVATION_URL", "http://127.0.0.1:8103")
AVAILABILITY_URL = os.getenv("AVAILABILITY_URL", "http://127.0.0.1:8101")
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://127.0.0.1:8102")
CUSTOMER_URL = os.getenv("CUSTOMER_URL", "http://127.0.0.1:8104")
HOTEL_URL = os.getenv("HOTEL_URL", "http://127.0.0.1:8105")


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

    def available(self, day) -> int:
        body = self._json(
            self.client.get(
                f"{AVAILABILITY_URL}/availability",
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
            f"{AVAILABILITY_URL}/inventory/{room_id or self.room['id']}",
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
        self, key: str, day, customer_id: str, simulate: str = "ok", **kwargs
    ) -> httpx.Response:
        body = {
            "customer_id": customer_id,
            "hotel_id": kwargs.get("hotel_id", self.hotel["id"]),
            "room_id": kwargs.get("room_id", self.room["id"]),
            "check_in": day.isoformat(),
            "check_out": (day + dt.timedelta(days=kwargs.get("nights", 1))).isoformat(),
            "payment": {"method": "card", "token": "tok_demo", "simulate": simulate},
        }
        return self.client.post(
            f"{RESERVATION_URL}/reservations",
            json=body,
            headers={"Idempotency-Key": key, "X-Request-ID": f"e2e-{key}"},
        )

    def list_reservations(self, customer_id: str) -> list[dict]:
        return self._json(
            self.client.get(
                f"{RESERVATION_URL}/reservations", params={"customer_id": customer_id}
            )
        )

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


@pytest.fixture(scope="session")
def manifest() -> dict:
    path = ROOT / "secrets" / "seed.json"
    if not path.exists():
        pytest.fail("falta secrets/seed.json; ejecuta `make up-dev && make seed`", pytrace=False)
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def stack(manifest) -> Stack:
    with httpx.Client(timeout=40) as client:
        yield Stack(manifest, client)


@pytest.fixture()
def invariants():
    def _check() -> None:
        violations = check_all(grace_seconds=60)
        assert not violations, "invariantes violados:\n" + "\n".join(
            str(violation) for violation in violations
        )

    return _check
