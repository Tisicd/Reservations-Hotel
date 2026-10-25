"""Flujo público de la UI con autenticación: registro -> login -> reservar
-> eventos/notificación -> replay -> cancelar -> logout, y negativos."""

import datetime as dt
import os
import time
import uuid

import httpx

API = os.getenv("GATEWAY_URL", "http://127.0.0.1:8088/api").rstrip("/")
ROOT = os.getenv("GATEWAY_ROOT_URL", API.rsplit("/api", 1)[0]).rstrip("/")
PASSWORD = "Reserva-E2E-2026!"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _wait(client: httpx.Client, reservation_id: str, expected: set[str],
          timeout: float = 60, token: str | None = None) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        response = client.get(f"{API}/reservations/{reservation_id}",
                              headers=_auth(token) if token else None)
        if response.status_code == 200:
            last = response.json()
            if last["status"] in expected:
                return last
        time.sleep(1)
    raise AssertionError(f"reserva {reservation_id} no llegó a {expected}: {last}")


def test_public_auth_flow() -> None:
    with httpx.Client(timeout=30) as client:
        email = f"e2e-auth-{uuid.uuid4().hex}@example.com"
        registered = client.post(f"{API}/auth/register", json={
            "name": "E2E Auth", "email": email, "password": PASSWORD})
        assert registered.status_code == 201, registered.text
        customer_id = registered.json()["id"]

        logged = client.post(f"{API}/auth/login", json={
            "email": email, "password": PASSWORD})
        assert logged.status_code == 200, logged.text
        assert "no-store" in (logged.headers.get("Cache-Control") or "").lower()
        data = logged.json()
        token = data["access_token"]
        assert data["customer"]["id"] == customer_id
        assert data["token_type"] == "Bearer"

        assert client.get(f"{API}/auth/me", headers=_auth(token)).status_code == 200

        hotels = client.get(f"{API}/hotels").json()
        assert hotels
        hotel = hotels[0]
        detail = client.get(f"{API}/hotels/{hotel['id']}").json()
        rooms = detail["rooms"]
        assert rooms
        room = rooms[0]

        day = None
        for _ in range(10):
            candidate = dt.date.today() + dt.timedelta(
                days=1 + uuid.uuid4().int % 55)
            availability = client.get(f"{API}/availability", params={
                "hotel_id": hotel["id"], "check_in": candidate.isoformat(),
                "check_out": (candidate + dt.timedelta(days=1)).isoformat()})
            assert availability.status_code == 200, availability.text
            if any(item["room_id"] == room["id"] and item["available"] > 0
                   for item in availability.json()["rooms"]):
                day = candidate
                break
        assert day is not None, "sin inventario disponible en 10 fechas"

        body = {
            "customer_id": customer_id, "hotel_id": hotel["id"],
            "room_id": room["id"], "check_in": day.isoformat(),
            "check_out": (day + dt.timedelta(days=1)).isoformat(),
            "payment": {"method": "card", "token": "tok_demo", "simulate": "ok"},
        }
        key = str(uuid.uuid4())

        # Sin sesión no se puede reservar.
        anonymous = client.post(f"{API}/reservations", json=body,
                                headers={"Idempotency-Key": key})
        assert anonymous.status_code == 401, anonymous.text
        # X-User-Id falsificado sin token tampoco.
        spoofed_anon = client.post(f"{API}/reservations", json=body, headers={
            "Idempotency-Key": key, "X-User-Id": customer_id})
        assert spoofed_anon.status_code == 401

        created = client.post(f"{API}/reservations", json=body, headers={
            **_auth(token), "Idempotency-Key": key})
        assert created.status_code in (200, 201, 202), created.text
        reservation = created.json()
        reservation_id = reservation["id"]
        assert reservation["customer_id"] == customer_id

        # X-User-Id no puede cambiar la identidad del token.
        forged = client.post(f"{API}/reservations", json={
            **body, "customer_id": str(uuid.uuid4())}, headers={
                **_auth(token), "Idempotency-Key": str(uuid.uuid4())})
        assert forged.status_code == 403, forged.text

        final = _wait(client, reservation_id, {"CONFIRMED"}, token=token)
        assert final["status"] == "CONFIRMED", final

        events = client.get(f"{API}/reservations/{reservation_id}/events",
                            headers=_auth(token))
        assert events.status_code == 200 and events.json(), events.text

        notes = []
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            response = client.get(f"{API}/notifications", params={
                "reservation_id": reservation_id}, headers=_auth(token))
            if response.status_code == 200 and response.json():
                notes = response.json()
                break
            time.sleep(1)
        assert notes, "sin notificación"
        assert notes[-1]["status"] in ("PENDING", "SENT"), notes[-1]

        replay = client.post(f"{API}/reservations", json=body, headers={
            **_auth(token), "Idempotency-Key": key})
        assert replay.status_code == 200, replay.text
        assert replay.headers.get("Idempotent-Replayed") == "true"
        assert replay.json()["id"] == reservation_id

        listed = client.get(f"{API}/reservations", params={
            "customer_id": customer_id}, headers=_auth(token))
        assert listed.status_code == 200, listed.text
        assert len(listed.json()) == 1, "la reserva se duplicó"

        cancelled = client.post(
            f"{API}/reservations/{reservation_id}/cancel", headers=_auth(token))
        assert cancelled.status_code in (200, 202), cancelled.text
        final = _wait(client, reservation_id, {"CANCELLED"}, token=token)
        assert final["status"] == "CANCELLED"

        assert client.post(f"{API}/auth/logout",
                           headers=_auth(token)).status_code == 204
        assert client.get(f"{API}/auth/me", headers=_auth(token)).status_code == 401

        # Rutas internas y de cuentas cerradas.
        internal = [
            ("GET", "/svc/customer/health", {}),
            ("POST", "/api/holds", {"json": {}}),
            ("GET", "/api/payments", {}),
            ("GET", "/api/customers", {}),
            ("GET", "/api/auth/validate", {}),
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

        # Límite de login (zona auth) -> 429. Se hace al final.
        limited = []
        for _ in range(15):
            limited.append(client.post(f"{API}/auth/login", json={
                "email": f"nadie-{uuid.uuid4().hex}@example.com",
                "password": "No-Existe-2026!"}).status_code)
        assert 429 in limited, limited
