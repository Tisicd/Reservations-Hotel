"""Crea el hotel y habitaciones dedicados a las pruebas de carga (idempotente).

Solo biblioteca estandar. Escribe `tests/perf/state.json` con los IDs
deterministas y la ventana de fechas reservada para perf.
"""

import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
STATE = ROOT / "tests/perf" / "state.json"
ADMIN_URL = os.getenv("GATEWAY_ADMIN_URL", "http://127.0.0.1:8081").rstrip("/")
HOTEL_URL = f"{ADMIN_URL}/svc/hotel"
AVAILABILITY_URL = f"{ADMIN_URL}/svc/availability"

HOTEL_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "reservas:perf:hotel"))
ROOMS = int(os.getenv("PERF_ROOMS", "60"))
BASE_OFFSET_DAYS = 2000
WINDOW_DAYS = 120
TOTAL = 1000


def _request(method: str, url: str, body: dict | None = None) -> tuple[int, dict | None]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json",
                 "X-Request-ID": f"perf-setup-{uuid.uuid4()}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw) if raw else None
    except urllib.error.URLError as exc:
        raise SystemExit(f"No se pudo conectar a {url}: {exc}") from exc


def _check(status: int, allowed: tuple[int, ...], url: str, body) -> None:
    if status not in allowed:
        raise SystemExit(f"setup fallo: {url} respondio {status}: {body}")


def main() -> None:
    today = dt.date.today()
    start = today + dt.timedelta(days=BASE_OFFSET_DAYS)
    end = start + dt.timedelta(days=WINDOW_DAYS)

    status, body = _request("POST", f"{HOTEL_URL}/hotels", {
        "id": HOTEL_ID, "name": "Perf Hotel", "city": "Perf"})
    _check(status, (200, 201), f"{HOTEL_URL}/hotels", body)

    rooms = []
    for index in range(ROOMS):
        room_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"reservas:perf:room:{index}"))
        status, body = _request(
            "POST", f"{HOTEL_URL}/hotels/{HOTEL_ID}/rooms",
            {"id": room_id, "name": f"Perf {index:03d}", "capacity": 2,
             "price_per_night_cents": 5000, "currency": "USD"})
        _check(status, (200, 201), f"{HOTEL_URL}/hotels/{HOTEL_ID}/rooms", body)
        # El servicio limita a 30 noches por PUT: trocear la ventana.
        cursor = start
        while cursor < end:
            chunk_end = min(cursor + dt.timedelta(days=30), end)
            status, body = _request(
                "PUT", f"{AVAILABILITY_URL}/inventory/{room_id}",
                {"hotel_id": HOTEL_ID, "from": cursor.isoformat(),
                 "to": chunk_end.isoformat(), "total": TOTAL})
            _check(status, (200,), f"{AVAILABILITY_URL}/inventory/{room_id}", body)
            cursor = chunk_end
        rooms.append(room_id)

    state = {
        "hotel_id": HOTEL_ID,
        "rooms": rooms,
        "base_day": start.isoformat(),
        "window_days": WINDOW_DAYS,
        "total": TOTAL,
    }
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"setup OK: hotel={HOTEL_ID} rooms={ROOMS} base={start} total={TOTAL}")


if __name__ == "__main__":
    main()
