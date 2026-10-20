"""E2E de notification: entrega, dedupe y caída sin afectar la reserva."""

import datetime as dt
import pathlib
import subprocess
import time
import uuid

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.dev.yaml"]
BASE = dt.date.today() + dt.timedelta(days=1)


def _unique_day() -> dt.date:
    # Rango disjunto del de test_flows: repetir `make e2e` no choca con
    # inventario ni reservas de una corrida anterior.
    return BASE + dt.timedelta(days=4000 + uuid.uuid4().int % 1000)


def _container(service: str) -> str:
    r = subprocess.run(
        [*COMPOSE, "ps", "-q", service], cwd=str(ROOT), capture_output=True, text=True
    )
    lines = [line for line in r.stdout.split() if line]
    assert lines, f"{service} no está arriba"
    return lines[0]


def _health(cid: str) -> str:
    r = subprocess.run(
        ["docker", "inspect", cid, "--format", "{{.State.Health.Status}}"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


def _wait_healthy(cid: str, timeout: int = 90) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _health(cid) == "healthy":
            return
        time.sleep(1)
    raise AssertionError("notification no volvió a healthy")


def _wait_notifications(stack, reservation_id: str, timeout: float = 90) -> list[dict]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            items = stack.notifications(reservation_id)
        except httpx.HTTPStatusError:  # 502 transitorio mientras arranca notification
            items = []
        if items and all(item["status"] == "SENT" for item in items):
            return items
        time.sleep(1)
    raise AssertionError(f"no se entregó la notificación de {reservation_id}")


def _confirmed(stack, day, key: str) -> dict:
    customer = stack.create_customer(f"e2e-{stack.run_id}-{key}@example.com")
    room = stack.room["id"]
    stack.put_inventory(day, 1, room)
    response = stack.create_reservation(
        f"e2e-{stack.run_id}-{key}", day, customer["id"], room_id=room
    )
    assert response.status_code in (200, 201), response.text
    reservation = response.json()
    assert reservation["status"] == "CONFIRMED"
    return reservation


def test_confirmacion_entrega_notificacion(stack, invariants):
    reservation = _confirmed(stack, _unique_day(), "notif")
    items = _wait_notifications(stack, reservation["id"])
    assert items[0]["type"] == "reservation.confirmed"
    assert items[0]["attempts"] >= 1
    assert items[0]["sent_at"] is not None
    invariants()


def test_entrega_duplicada_es_idempotente(stack):
    body = {
        "event_id": str(uuid.uuid4()),
        "type": "reservation.confirmed",
        "reservation_id": str(uuid.uuid4()),
        "customer_id": str(uuid.uuid4()),
        "payload": {"origen": "e2e"},
    }
    first = stack.post_notification(body)
    second = stack.post_notification(body)
    assert first.status_code == 202, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert len(stack.notifications(body["reservation_id"])) == 1


def test_caida_de_notification_no_bloquea_y_recupera(stack, invariants):
    cid = _container("notification")
    subprocess.run([*COMPOSE, "stop", "notification"], cwd=str(ROOT), check=True)
    try:
        reservation = _confirmed(stack, _unique_day(), "caida")
        time.sleep(3)  # el relay acumula reintentos con backoff
    finally:
        subprocess.run([*COMPOSE, "start", "notification"], cwd=str(ROOT), check=True)
        _wait_healthy(cid)
    items = _wait_notifications(stack, reservation["id"])
    assert items[0]["type"] == "reservation.confirmed"
    invariants()
