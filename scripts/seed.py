"""Siembra determinista de hoteles, habitaciones, clientes e inventario."""

import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "secrets" / "seed.json"

ADMIN_URL = os.getenv("GATEWAY_ADMIN_URL", "http://127.0.0.1:8081").rstrip("/")
HOTEL_URL = os.getenv("HOTEL_URL", f"{ADMIN_URL}/svc/hotel").rstrip("/")
CUSTOMER_URL = os.getenv("CUSTOMER_URL", f"{ADMIN_URL}/svc/customer").rstrip("/")
AVAILABILITY_URL = os.getenv("AVAILABILITY_URL", f"{ADMIN_URL}/svc/availability").rstrip("/")

DAYS = 60
UNITS_PER_NIGHT = 5

HOTELS = [
    ("Hotel Quito Centro", "Quito"),
    ("Hotel Guayaquil Malecón", "Guayaquil"),
    ("Hotel Cuenca Histórico", "Cuenca"),
]
ROOMS = [
    ("Simple", 1, 3900),
    ("Doble", 2, 5200),
    ("Matrimonial", 2, 6100),
    ("Suite", 3, 9400),
    ("Familiar", 4, 12500),
]
CUSTOMERS = [
    ("Cliente Demo Uno", "demo1@example.com"),
    ("Cliente Demo Dos", "demo2@example.com"),
]
DEMO_ACCOUNT = ("Cuenta Demo UCE", "demo@reservas-uce.test")


def _id(kind: str, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"reservas:{kind}:{key}"))


def _request(method: str, url: str, body: dict | None = None) -> tuple[int, dict | None]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-Request-ID": f"seed-{uuid.uuid4()}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw) if raw else None
    except urllib.error.URLError as exc:
        raise SystemExit(f"No se pudo conectar a {url}: {exc}") from exc


def _fail(message: str) -> None:
    raise SystemExit(f"siembra falló: {message}")


def _load_previous() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def _check(status: int, allowed: tuple[int, ...], url: str, payload: dict | None) -> None:
    if status not in allowed:
        _fail(f"{url} respondió {status}: {payload}")


def _seed_hotels(today: dt.date) -> list[dict]:
    hotels = []
    for hotel_name, city in HOTELS:
        hotel_id = _id("hotel", city)
        status, payload = _request(
            "POST",
            f"{HOTEL_URL}/hotels",
            {"id": hotel_id, "name": hotel_name, "city": city},
        )
        _check(status, (200, 201), f"{HOTEL_URL}/hotels", payload)
        rooms = []
        for index, (room_name, capacity, price) in enumerate(ROOMS, start=1):
            room_id = _id("room", f"{city}:{index}")
            body = {
                "id": room_id,
                "name": room_name,
                "capacity": capacity,
                "price_per_night_cents": price,
                "currency": "USD",
            }
            status, payload = _request(
                "POST", f"{HOTEL_URL}/hotels/{hotel_id}/rooms", body
            )
            _check(status, (200, 201), f"{HOTEL_URL}/hotels/{hotel_id}/rooms", payload)
            rooms.append(
                {
                    "id": room_id,
                    "name": room_name,
                    "capacity": capacity,
                    "price_per_night_cents": price,
                }
            )
            for offset in range(DAYS):
                night = today + dt.timedelta(days=offset)
                status, payload = _request(
                    "PUT",
                    f"{AVAILABILITY_URL}/inventory/{room_id}",
                    {
                        "hotel_id": hotel_id,
                        "from": night.isoformat(),
                        "to": (night + dt.timedelta(days=1)).isoformat(),
                        "total": UNITS_PER_NIGHT,
                    },
                )
                _check(status, (200,), f"{AVAILABILITY_URL}/inventory/{room_id}", payload)
        hotels.append({"id": hotel_id, "name": hotel_name, "city": city, "rooms": rooms})
        print(f"  hotel {hotel_name} ({city}): {len(rooms)} habitaciones")
    return hotels


def _seed_customers(previous: dict) -> list[dict]:
    known = {item["email"]: item["id"] for item in previous.get("customers", [])}
    customers = []
    for name, email in CUSTOMERS:
        status, payload = _request(
            "POST", f"{CUSTOMER_URL}/customers", {"name": name, "email": email}
        )
        if status == 201:
            customer_id = payload["id"]
        elif status == 409:
            customer_id = known.get(email)
            if customer_id is None:
                _fail(
                    f"el cliente {email} ya existe con otro id; "
                    "ejecuta `make clean-all` y vuelve a sembrar"
                )
        else:
            _check(status, (201,), f"{CUSTOMER_URL}/customers", payload)
        customers.append({"id": customer_id, "name": name, "email": email})
        print(f"  cliente {email}")
    return customers


def _demo_password() -> str | None:
    value = os.getenv("DEMO_USER_PASSWORD")
    if value:
        return value
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DEMO_USER_PASSWORD="):
                return line.split("=", 1)[1].strip() or None
    return None


def _seed_demo_account() -> dict | None:
    password = _demo_password()
    if not password:
        print("  aviso: DEMO_USER_PASSWORD no definida; cuenta demo omitida")
        return None
    name, email = DEMO_ACCOUNT
    status, payload = _request(
        "POST", f"{CUSTOMER_URL}/auth/register",
        {"name": name, "email": email, "password": password},
    )
    if status in (200, 201):
        print(f"  cuenta demo {email}")
        return {"id": payload["id"], "name": name, "email": email}
    if status == 409:
        status, payload = _request(
            "POST", f"{CUSTOMER_URL}/auth/login",
            {"email": email, "password": password},
        )
        if status == 200:
            customer = payload["customer"]
            print(f"  cuenta demo {email} (existente)")
            return {"id": customer["id"], "name": customer["name"],
                    "email": customer["email"]}
        _fail("la cuenta demo existe pero la contrase?a no coincide; "
              "define DEMO_USER_PASSWORD o ejecuta `make clean-all`")
    _check(status, (200, 201, 409), f"{CUSTOMER_URL}/auth/register", payload)
    return None


def main() -> None:
    today = dt.date.today()
    previous = _load_previous()
    print("sembrando hoteles e inventario")
    hotels = _seed_hotels(today)
    print("sembrando clientes")
    customers = _seed_customers(previous)
    demo_account = _seed_demo_account()
    manifest = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inventory": {
            "start": today.isoformat(),
            "days": DAYS,
            "units_per_night": UNITS_PER_NIGHT,
        },
        "hotels": hotels,
        "customers": customers,
        "demo_account": demo_account,
    }
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"manifiesto escrito en {MANIFEST}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"error inesperado: {exc}", file=sys.stderr)
        raise
