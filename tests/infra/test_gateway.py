"""Gateway: rutas, healthchecks y continuidad con réplicas de availability.

Requiere el stack arriba con `make up-dev` (o `make test`, que lo levanta).
"""

import concurrent.futures
import datetime as dt
import os
import pathlib
import subprocess
import time
import uuid

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.dev.yaml"]
PUBLIC = os.getenv("GATEWAY_URL", "http://127.0.0.1:8088").rstrip("/")
ADMIN = os.getenv("GATEWAY_ADMIN_URL", "http://127.0.0.1:8081").rstrip("/")


def _replicas(service: str) -> list[str]:
    r = subprocess.run(
        [*COMPOSE, "ps", "-q", service], cwd=str(ROOT), capture_output=True, text=True
    )
    return [line for line in r.stdout.split() if line]


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
    raise AssertionError(f"contenedor {cid} no volvió a healthy")


def _get(path: str, admin: bool = False, **kwargs) -> httpx.Response:
    base = ADMIN if admin else PUBLIC
    return httpx.get(f"{base}{path}", timeout=10, **kwargs)


def _assert(response: httpx.Response, expected, url: str) -> None:
    codes = expected if isinstance(expected, tuple) else (expected,)
    assert response.status_code in codes, (
        f"{url} -> {response.status_code} (esperado {codes}): {response.text[:200]}"
    )


def _inventory(room_id: str, hotel_id: str, day: dt.date, total: int) -> httpx.Response:
    return httpx.put(
        f"{ADMIN}/svc/availability/inventory/{room_id}",
        json={
            "hotel_id": hotel_id,
            "from": day.isoformat(),
            "to": (day + dt.timedelta(days=1)).isoformat(),
            "total": total,
        },
        timeout=10,
    )


def test_admin_publicado_solo_en_loopback():
    result = subprocess.run(
        [*COMPOSE, "port", "gateway", "8081"], cwd=str(ROOT), capture_output=True, text=True
    )
    mapping = result.stdout.strip()
    assert mapping.startswith("127.0.0.1:"), (
        f"admin publicado en {mapping!r}; se esperaba solo loopback"
    )


def test_rutas_publicas_y_administrativas():
    _assert(_get("/healthz"), 200, f"{PUBLIC}/healthz")
    assert _get("/healthz").json() == {"status": "ok"}
    _assert(_get("/healthz", admin=True), 200, f"{ADMIN}/healthz")
    _assert(_get("/api/hotels"), 200, f"{PUBLIC}/api/hotels")
    _assert(_get("/api/availability"), (200, 422), f"{PUBLIC}/api/availability")
    _assert(_get("/api/reservations"), (200, 422), f"{PUBLIC}/api/reservations")
    _assert(
        _get("/api/notifications?reservation_id=" + str(uuid.uuid4())),
        200,
        f"{PUBLIC}/api/notifications",
    )
    for service in ("notification", "payment", "reservation"):
        _assert(
            _get(f"/svc/{service}/health", admin=True),
            200,
            f"{ADMIN}/svc/{service}/health",
        )
    # Rutas no publicadas no se filtran.
    _assert(_get("/api/payments"), 404, f"{PUBLIC}/api/payments")
    _assert(_get("/"), 404, f"{PUBLIC}/")
    # Notifications es de solo lectura en el puerto publico.
    _assert(
        httpx.post(f"{PUBLIC}/api/notifications", json={}, timeout=10),
        403,
        f"POST {PUBLIC}/api/notifications",
    )


def test_tres_replicas_comparten_inventario_y_siguen_sirviendo_al_caer():
    replicas = _replicas("availability")
    assert len(replicas) == 3, f"se esperaban 3 réplicas de availability: {replicas}"
    for cid in replicas:
        assert _health(cid) == "healthy"

    room, hotel = str(uuid.uuid4()), str(uuid.uuid4())
    day = dt.date.today() + dt.timedelta(days=90)
    assert _inventory(room, hotel, day, 2).status_code == 200

    query = {
        "hotel_id": hotel,
        "check_in": day.isoformat(),
        "check_out": (day + dt.timedelta(days=1)).isoformat(),
    }

    def available() -> int:
        response = _get("/api/availability", params=query)
        assert response.status_code == 200, response.text
        rooms = {r["room_id"]: r["available"] for r in response.json()["rooms"]}
        return rooms[room]

    def wait_available(expected: int) -> None:
        # El resolver de nginx tarda hasta 2 s en olvidar un contenedor caido;
        # durante esa ventana una peticion puede fallar. La continuidad se
        # demuestra cuando el balanceador converge, no en el primer intento.
        deadline = time.time() + 30
        last = ""
        while time.time() < deadline:
            try:
                if available() == expected:
                    return
            except (httpx.HTTPError, AssertionError) as exc:
                last = str(exc)
            time.sleep(1)
        raise AssertionError(f"availability no llego a {expected}: {last}")

    def wait_inventory(units: int) -> None:
        # El PUT fija el inventario absoluto, asi que reintentarlo es seguro.
        deadline = time.time() + 30
        last = None
        while time.time() < deadline:
            last = _inventory(room, hotel, day, units)
            if last.status_code == 200:
                return
            time.sleep(1)
        raise AssertionError(f"inventario no llego a {units}: {last.status_code} {last.text}")

    try:
        wait_available(2)
        # Con dos réplicas caídas, la tercera sigue sirviendo y el inventario
        # es el mismo porque vive en PostgreSQL, no en memoria local.
        for cid in replicas[:2]:
            subprocess.run(["docker", "stop", cid], check=True, capture_output=True)
        wait_available(2)
        wait_inventory(1)
        wait_available(1)
        # Carrera por la última unidad a través del balanceador: las tres
        # réplicas comparten la fila de PostgreSQL, así que solo una gana.
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results = list(
                pool.map(
                    lambda _: httpx.post(
                        f"{ADMIN}/svc/availability/holds",
                        json={
                            "hold_id": str(uuid.uuid4()),
                            "room_id": room,
                            "check_in": day.isoformat(),
                            "check_out": (day + dt.timedelta(days=1)).isoformat(),
                            "units": 1,
                        },
                        timeout=10,
                    ).status_code,
                    range(3),
                )
            )
        assert results.count(201) == 1, results
        assert not any(status >= 500 for status in results), results
        wait_available(0)
    finally:
        for cid in replicas:
            subprocess.run(["docker", "start", cid], check=False, capture_output=True)
        for cid in replicas:
            _wait_healthy(cid)
