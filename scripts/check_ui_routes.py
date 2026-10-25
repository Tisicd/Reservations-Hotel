"""Comprueba que la UI solo use rutas públicas y que no estén bloqueadas."""

import datetime as dt
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = os.getenv("GATEWAY_URL", "http://127.0.0.1:8088").rstrip("/")
JS_FILES = sorted((ROOT / "gateway" / "html").rglob("*.js"))
CALL = re.compile(
    r"request\(\s*['\"](GET|POST)['\"]\s*,\s*([`'\"][^`'\"]+[`'\"])")
ALLOWED = {
    ("GET", "/api/hotels"),
    ("GET", "/api/hotels/{id}"),
    ("GET", "/api/availability"),
    ("GET", "/api/reservations"),
    ("GET", "/api/reservations/{id}"),
    ("GET", "/api/reservations/{id}/events"),
    ("GET", "/api/notifications"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/reservations"),
    ("POST", "/api/reservations/{id}/cancel"),
}
FORBIDDEN = ("/svc", "/holds", "/payments", "/inventory", "/api/customers")


def normalize(raw: str) -> str:
    path = raw.strip("`'\"")
    path = path.split("?", 1)[0]
    path = re.sub(r"\$\{[^}]+\}", "{id}", path)
    if not path.startswith("/api"):
        path = "/api" + path
    return path


def http(method: str, path: str, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise SystemExit(f"no se pudo conectar a {BASE}: {exc}") from exc


def main() -> None:
    used = set()
    for path in JS_FILES:
        text = path.read_text(encoding="utf-8")
        for match in CALL.finditer(text):
            method, raw = match.group(1), match.group(2)
            used.add((method, normalize(raw)))
        for token in FORBIDDEN:
            if token in text:
                raise SystemExit(f"ruta interna {token} encontrada en {path.name}")
        if re.search(r"\.innerHTML\s*=", text):
            raise SystemExit(f"innerHTML con datos encontrado en {path.name}")

    unknown = sorted(used - ALLOWED)
    if unknown:
        print("Rutas usadas no permitidas:")
        for method, path in unknown:
            print(f"  {method} {path}")
        sys.exit(1)
    print(f"  OK  {len(used)} rutas usadas, todas públicas/permitidas")

    api_js = (ROOT / "gateway" / "html" / "js" / "api.js").read_text(encoding="utf-8")
    if "Authorization" not in api_js or "getToken" not in api_js:
        raise SystemExit("api.js no adjunta Authorization a las llamadas protegidas")
    print("  OK  api.js adjunta Authorization (token de sesion)")
    status, body = http("GET", "/api/hotels")
    if status != 200:
        raise SystemExit(f"GET /api/hotels => {status}")
    hotels = json.loads(body)
    if not hotels:
        raise SystemExit("sin hoteles para probar")
    hotel_id = hotels[0]["id"]
    status, body = http("GET", f"/api/hotels/{hotel_id}")
    if status != 200:
        raise SystemExit(f"GET /api/hotels/{{id}} => {status}")
    rooms = json.loads(body).get("rooms") or []
    room_id = rooms[0]["id"] if rooms else str(uuid.uuid4())
    today = dt.date.today()
    query = urllib.parse.urlencode({
        "hotel_id": hotel_id,
        "check_in": (today + dt.timedelta(days=1)).isoformat(),
        "check_out": (today + dt.timedelta(days=2)).isoformat(),
    })
    checks = [
        ("GET", f"/api/availability?{query}", 200),
        ("GET", f"/api/reservations?customer_id={uuid.uuid4()}", 200),
        ("GET", f"/api/reservations/{uuid.uuid4()}", 404),
        # events de un id inexistente devuelve 200 [] (ruta abierta, sin datos)
        ("GET", f"/api/reservations/{uuid.uuid4()}/events", 200),
        ("POST", f"/api/reservations/{uuid.uuid4()}/cancel", 401),
        ("GET", f"/api/notifications?reservation_id={uuid.uuid4()}", 200),
        ("GET", f"/api/customers/{uuid.uuid4()}", 404),
        ("POST", "/api/auth/register", 422),
        ("POST", "/api/auth/login", 422),
        ("GET", "/api/auth/me", 401),
        ("POST", "/api/auth/logout", 401),
        ("POST", "/api/reservations", 401),
        ("POST", "/api/hotels", 403),
        ("GET", "/api/customers", 404),
        ("GET", "/api/auth/validate", 404),
        ("GET", "/api/payments", 404),
    ]
    for method, path, expected in checks:
        status, _ = http(method, path, body={} if method == "POST" else None)
        if status != expected:
            raise SystemExit(f"{method} {path} => {status}, esperaba {expected}")
        print(f"  OK  {method} {path.split('?')[0]} => {status}")
    status, _ = http("PUT", f"/api/availability/inventory/{room_id}", body={})
    if status != 403:
        raise SystemExit(f"PUT inventario => {status}, esperaba 403")
    print("  OK  PUT /api/availability/inventory/{id} => 403")
    print("\ncheck-ui OK")


if __name__ == "__main__":
    main()
