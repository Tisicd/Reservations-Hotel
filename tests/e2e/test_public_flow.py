"""Flujo público de la UI: buscar -> cliente -> reservar -> eventos ->
notificación -> replay idempotente -> cancelar (solo listener público)."""

import datetime as dt
import os
import time
import uuid

import httpx

API = os.getenv("GATEWAY_URL", "http://127.0.0.1:8088/api").rstrip("/")
ROOT = os.getenv("GATEWAY_ROOT_URL", API.rsplit("/api", 1)[0]).rstrip("/")


def _reserve(client: httpx.Client, body: dict, key: str,
             tries: int = 4) -> httpx.Response:
    response = None
    for _ in range(tries):
        response = client.post(
            f"{API}/reservations", json=body,
            headers={"Idempotency-Key": key},
        )
        if response.status_code not in (429, 503):
            return response
        time.sleep(int(response.headers.get("Retry-After", "2")))
    return response


def _wait(client: httpx.Client, reservation_id: str, expected: set[str],
          timeout: float = 60) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        response = client.get(f"{API}/reservations/{reservation_id}")
        if response.status_code == 200:
            last = response.json()
            if last["status"] in expected:
                return last
        time.sleep(1)
    raise AssertionError(f"reserva {reservation_id} no llegó a {expected}: {last}")


def test_public_flow() -> None:
    with httpx.Client(timeout=30) as client:
        email = f"ui-{uuid.uuid4().hex}@example.com"
        created = client.post(
            f"{API}/customers", json={"name": "UI Test", "email": email})
        assert created.status_code == 201, created.text
        customer = created.json()["id"]

        hotels = client.get(f"{API}/hotels").json()
        assert hotels, "sin hoteles"
        hotel = hotels[0]
        detail = client.get(f"{API}/hotels/{hotel['id']}").json()
        rooms = detail["rooms"]
        assert rooms, "sin habitaciones"
        room = rooms[0]

        day = None
        for _ in range(10):
            candidate = dt.date.today() + dt.timedelta(
                days=1 + uuid.uuid4().int % 55)
            availability = client.get(
                f"{API}/availability",
                params={"hotel_id": hotel["id"],
                        "check_in": candidate.isoformat(),
                        "check_out": (candidate + dt.timedelta(days=1)).isoformat()},
            )
            assert availability.status_code == 200, availability.text
            if any(item["room_id"] == room["id"] and item["available"] > 0
                   for item in availability.json()["rooms"]):
                day = candidate
                break
        assert day is not None, "sin inventario disponible en 10 fechas"

        body = {
            "customer_id": customer, "hotel_id": hotel["id"],
            "room_id": room["id"], "check_in": day.isoformat(),
            "check_out": (day + dt.timedelta(days=1)).isoformat(),
            "payment": {"method": "card", "token": "tok_demo", "simulate": "ok"},
        }
        key = str(uuid.uuid4())
        response = _reserve(client, body, key)
        assert response.status_code in (200, 201, 202), response.text
        assert response.headers.get("X-Request-ID"), "sin X-Request-ID"
        reservation = response.json()
        reservation_id = reservation["id"]

        final = _wait(client, reservation_id, {"CONFIRMED"})
        assert final["status"] == "CONFIRMED", final

        events = client.get(f"{API}/reservations/{reservation_id}/events")
        assert events.status_code == 200 and events.json(), events.text
        for event in events.json():
            assert {"from", "to", "at"} <= set(event)

        notes = []
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            response = client.get(
                f"{API}/notifications", params={"reservation_id": reservation_id})
            if response.status_code == 200 and response.json():
                notes = response.json()
                break
            time.sleep(1)
        assert notes, "sin notificación"
        assert notes[-1]["status"] in ("PENDING", "SENT"), notes[-1]

        replay = _reserve(client, body, key)
        assert replay.status_code == 200, replay.text
        assert replay.headers.get("Idempotent-Replayed") == "true"
        assert replay.json()["id"] == reservation_id

        listed = client.get(
            f"{API}/reservations", params={"customer_id": customer})
        assert listed.status_code == 200, listed.text
        assert len(listed.json()) == 1, "la reserva se duplicó"

        cancelled = client.post(f"{API}/reservations/{reservation_id}/cancel")
        assert cancelled.status_code in (200, 202), cancelled.text
        final = _wait(client, reservation_id, {"CANCELLED"})
        assert final["status"] == "CANCELLED"

        internal = [
            ("GET", "/svc/customer/health", {}),
            ("POST", "/api/holds", {"json": {}}),
            ("GET", "/api/payments", {}),
            ("PUT", f"/api/availability/inventory/{room['id']}",
             {"json": {"hotel_id": hotel["id"], "from": day.isoformat(),
                       "to": (day + dt.timedelta(days=1)).isoformat(),
                       "total": 0}}),
            ("POST", "/api/hotels", {"json": {"name": "x", "city": "y"}}),
        ]
        for method, path, kwargs in internal:
            response = client.request(method, f"{ROOT}{path}", **kwargs)
            assert response.status_code in (403, 404), (
                f"{method} {path} devolvió {response.status_code}")
