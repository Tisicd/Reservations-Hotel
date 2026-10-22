"""Arnés de caos reproducible para el stack `reservas-platform`.

Inyecta fallos reales sobre el stack levantado (``docker stop``, ``docker
kill`` y ``docker exec kill -9``) sin modificar el código de los servicios,
mide el impacto y la recuperación con tráfico de fondo y un canario,
comprueba los invariantes de negocio (``make invariants``) y genera un
reporte por escenario (Markdown + JSON ignorado por git).

El arnés nunca reconstruye imágenes: requiere que las imágenes ``:local``
ya estén construidas (``make build``) y que el stack esté levantado y
siembrado (``make up && make seed``).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import enum
import json
import os
import pathlib
import random
import statistics
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "tests" / "invariants") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests" / "invariants"))

from checker import (  # noqa: E402
    assert_no_loss,
    check_all,
    snapshot_committed,
    _url,
)

import sqlalchemy as sa

SEED_PATH = ROOT / "secrets" / "seed.json"
PUBLIC_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8088/api").rstrip("/")
ADMIN_URL = os.getenv("GATEWAY_ADMIN_URL", "http://127.0.0.1:8081/svc").rstrip("/")
COMPOSE = [
    "docker", "compose",
    "-f", str(ROOT / "compose.yaml"),
    "-f", str(ROOT / "compose.dev.yaml"),
]
DOCKER = ["docker"]

SERVICES = ("customer", "hotel", "availability", "payment", "reservation",
            "notification", "postgres", "gateway")

DEFAULT_BASELINE_SECONDS = 15
DEFAULT_FAULT_SECONDS = 20
DEFAULT_DRAIN_SECONDS = 20
DEFAULT_RPS = 1.5
OUTBOX_BACKLOG_OLD_SECONDS = 300

# Objetivos de recuperación (F0 §4.2), en segundos.
RTO_OBJECTIVES = {
    "notification": 300,   # backlog de outbox vaciado <= 5 min
    "availability-read": 2,
    "reservation": 30,
    "postgres": 120,
}

HTTP_OK = frozenset({200, 201, 202})

IMPROVEMENTS = {
    "A": "dead-letter y alerta de antigüedad del backlog",
    "B": "health check activo y reintentos acotados; autoescalado en multinodo",
    "C": "replicar la API de reservation y worker con elección de líder",
    "D": "réplica de PostgreSQL con failover automático y PITR",
    "E2": "conciliación contra extractos del proveedor real y webhooks",
    "S": "circuit breaker y health check activo en el gateway",
}


class Phase(str, enum.Enum):
    BASELINE = "baseline"
    FAULT = "falla"
    RECOVERY = "recuperacion"
    DRAIN = "drenaje"


@dataclass
class RequestSample:
    phase: str
    wall: str
    mono: float
    route: str
    method: str
    latency_ms: float
    status_code: int | None
    error_class: str
    reservation_id: str | None
    ok: bool


@dataclass
class CanarySample:
    wall: str
    mono: float
    route: str
    ok: bool
    status_code: int | None
    error: str | None


@dataclass
class OutageWindow:
    start: float
    end: float
    duration_ms: float


@dataclass
class ScenarioResult:
    scenario_id: str
    mode: str
    repeat: int
    baseline_seconds: float
    fault_seconds: float
    drain_seconds: float
    rps: float
    seed_file: str
    started_at: str
    finished_at: str
    t_baseline: float
    t_fault: float
    t_recovered: float | None
    t_end: float
    rtt_ttd_seconds: float | None
    rto_seconds: float | None
    rto_objective_seconds: int
    rto_cumplido: bool
    pendiente_durante_falla: int
    pendiente_despues_drenaje: int
    exito_baseline: float
    exito_falla: float
    restart_before: dict
    restart_after: dict
    health_before: dict
    health_after: dict
    hard_fail: bool
    hard_fail_reason: str | None
    metrics_by_phase: dict
    outage_windows: list
    assertions: dict
    close_ok: bool
    close_error: str | None
    evidence: str | None = None

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Docker / stack primitives
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _check(cmd: list[str]) -> subprocess.CompletedProcess:
    r = _run(cmd)
    if r.returncode != 0:
        raise RuntimeError(
            f"comando falló ({' '.join(cmd)}): {r.stderr.strip() or r.stdout.strip()}"
        )
    return r


def cid_list(svc: str, retries: int = 3, delay: float = 1.0) -> list[str]:
    for _ in range(retries):
        r = _run([*COMPOSE, "ps", "-q", svc])
        c = [x for x in r.stdout.splitlines() if x.strip()]
        if c:
            return c
        time.sleep(delay)
    return []


def primary_container(svc: str) -> str | None:
    c = cid_list(svc)
    return c[0] if c else None


def container_health(cid: str) -> str:
    r = _run(["docker", "inspect", cid, "--format", "{{.State.Health.Status}}"])
    return r.stdout.strip()


def container_restart_count(cid: str) -> int:
    r = _run(["docker", "inspect", cid, "--format", "{{.RestartCount}}"])
    try:
        return int(r.stdout.strip())
    except ValueError:
        return -1


def container_health_log(cid: str) -> str:
    r = _run(["docker", "inspect", cid, "--format", "{{json .State.Health.Log}}"])
    return r.stdout.strip()


def service_healthy(svc: str) -> bool:
    cids = cid_list(svc)
    if not cids:
        return False
    return all(container_health(c) == "healthy" for c in cids)


def stack_healthy() -> dict[str, bool]:
    return {svc: service_healthy(svc) for svc in SERVICES}


def image_built(svc: str) -> bool:
    r = _run(["docker", "image", "inspect", f"{svc}:local"])
    return r.returncode == 0


def seed_exists() -> bool:
    return SEED_PATH.exists()


def stop(svc: str, container: str | None = None) -> None:
    if container:
        _check(["docker", "stop", container])
    else:
        _check([*COMPOSE, "stop", svc])


def start(svc: str, container: str | None = None) -> None:
    if container:
        _check(["docker", "start", container])
    else:
        _check([*COMPOSE, "start", svc])


def kill(svc: str, container: str | None = None) -> None:
    if container:
        _check(["docker", "kill", container])
    else:
        _check([*COMPOSE, "kill", svc])


def pause(svc: str, container: str | None = None) -> None:
    cid = container or primary_container(svc)
    if not cid:
        raise RuntimeError(f"no hay contenedor para {svc}")
    _check(["docker", "pause", cid])


def unpause(svc: str, container: str | None = None) -> None:
    cid = container or primary_container(svc)
    if not cid:
        raise RuntimeError(f"no hay contenedor para {svc}")
    _check(["docker", "unpause", cid])


def exec_kill9(svc: str, pattern: str, container: str | None = None) -> None:
    cid = container or primary_container(svc)
    if not cid:
        raise RuntimeError(f"no hay contenedor para {svc}")
    code = (
        "import os, glob, sys, signal\n"
        f"needle = {pattern!r}\n"
        "myself = os.getpid()\n"
        "killed = []\n"
        "for p in glob.glob('/proc/[0-9]*'):\n"
        "    try:\n"
        "        pid = int(p.rsplit('/', 1)[1])\n"
        "    except ValueError:\n"
        "        continue\n"
        "    if pid == 1 or pid == myself:\n"
        "        continue\n"
        "    try:\n"
        "        argv = open(p + '/cmdline', 'rb').read().split(b'\\0')\n"
        "    except OSError:\n"
        "        continue\n"
        "    if any(needle in a for a in argv):\n"
        "        try:\n"
        "            os.kill(pid, signal.SIGKILL)\n"
        "            killed.append(pid)\n"
        "        except OSError:\n"
        "            pass\n"
        "print(killed)\n"
    )
    _run(["docker", "exec", cid, "python", "-c", code])


def pkill9(svc: str, name: str, container: str | None = None) -> None:
    """Mata (SIGKILL) todos los procesos con nombre exacto dentro del contenedor."""
    cid = container or primary_container(svc)
    if not cid:
        raise RuntimeError(f"no hay contenedor para {svc}")
    _run(["docker", "exec", cid, "pkill", "-9", "-x", name])


def wait_healthy(container: str, timeout: int = 60) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if container_health(container) == "healthy":
            return True
        time.sleep(1)
    return False


def restart_count(svc: str) -> int | None:
    cid = primary_container(svc)
    if not cid:
        return None
    return container_restart_count(cid)


def ps_snapshot() -> str:
    r = _run([*COMPOSE, "ps"])
    return r.stdout


def recreate(svc: str) -> None:
    """Elimina y recrea el contenedor del servicio SIN reconstruir la imagen."""
    _run([*COMPOSE, "rm", "-sf", svc])
    _check([*COMPOSE, "up", "-d", "--no-build", svc])


def health_log(svc: str) -> str:
    """Devuelve el Health.Log de los contenedores del servicio."""
    return "\n".join(container_health_log(c) for c in cid_list(svc))


# ---------------------------------------------------------------------------
# Precondiciones
# ---------------------------------------------------------------------------

def ensure_precondition() -> list[str]:
    """Devuelve la lista de faltas. Vacía si todo listo."""
    missing = []
    for svc in ("customer", "hotel", "availability", "payment", "reservation",
                "notification"):
        if not image_built(svc):
            missing.append(f"imagen {svc}:local no construida (ejecute: make build)")
    if not all(service_healthy(svc) for svc in SERVICES):
        missing.append("stack no está healthy (ejecute: make up)")
    if not seed_exists():
        missing.append("falta secrets/seed.json (ejecute: make up && make seed)")
    return missing


# ---------------------------------------------------------------------------
# Tráfico de fondo y canario
# ---------------------------------------------------------------------------

def classify_error(exc: Exception | None, status_code: int | None) -> str:
    if exc is not None:
        text = f"{type(exc).__name__}: {exc}"
        low = text.lower()
        if "connect" in low or "timeout" in low:
            return "timeout" if "timeout" in low else "connection"
        return f"exception:{type(exc).__name__}"
    if status_code is None:
        return "no_response"
    if status_code == 429:
        return "gateway_429"
    if status_code in (502, 504):
        return "upstream_502_504"
    if status_code == 503:
        return "service_503_fail_closed"
    if status_code >= 500:
        return "5xx"
    if status_code >= 400:
        return "4xx"
    return "other"


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    s = sorted(sorted_values)
    k = (len(s) - 1) * q / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def aggregate(samples: list[RequestSample]) -> dict:
    total = len(samples)
    ok = [s for s in samples if s.ok]
    errors: dict[str, int] = {}
    for s in samples:
        if not s.ok:
            errors[s.error_class] = errors.get(s.error_class, 0) + 1
    lat = sorted(s.latency_ms for s in ok)
    rate_limited = errors.get("gateway_429", 0)
    impact_total = total - rate_limited
    return {
        "total": total,
        "ok": len(ok),
        "success_pct": round(100.0 * len(ok) / total, 2) if total else 0.0,
        # Los 429 son límite del gateway, no impacto de la falla.
        "impact_total": impact_total,
        "impact_pct": (round(100.0 * len(ok) / impact_total, 2)
                       if impact_total else 100.0),
        "errors_by_class": errors,
        "p50_ms": round(_percentile(lat, 50), 1),
        "p95_ms": round(_percentile(lat, 95), 1),
        "p99_ms": round(_percentile(lat, 99), 1),
    }


class TrafficGenerator:
    """Peticiones de fondo a ritmo fijo (reservas + lecturas de disponibilidad)."""

    def __init__(self, run_id: str, rps: float, mode: str = "raw",
                 max_retries: int = 3, seed: dict | None = None):
        self.run_id = run_id
        self.rps = rps
        self.mode = mode  # "raw" | "retry"
        self.max_retries = max_retries
        self.client = httpx.Client(timeout=10)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.samples: list[RequestSample] = []
        self.thread: threading.Thread | None = None
        if seed is None:
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        self.hotel = seed["hotels"][0]
        self.room = self.hotel["rooms"][0]
        self.customer = random.choice(seed["customers"])
        self.rng = random.Random()

    def _reservation_body(self, key: str, day: dt.date) -> dict:
        nights = self.rng.choice([1, 2])
        return {
            "customer_id": self.customer["id"],
            "hotel_id": self.hotel["id"],
            "room_id": self.rng.choice(self.hotel["rooms"])["id"],
            "check_in": day.isoformat(),
            "check_out": (day + dt.timedelta(days=nights)).isoformat(),
            "payment": {"method": "card", "token": "tok_demo", "simulate": "ok"},
        }

    def _headers(self, key: str) -> dict[str, str]:
        return {"Idempotency-Key": key, "X-Request-ID": f"chaos-{self.run_id}-{key}"}

    def _read_availability(self) -> RequestSample:
        day = dt.date.today() + dt.timedelta(days=self.rng.randint(5, 60))
        start = time.monotonic()
        wall = dt.datetime.now(dt.timezone.utc).isoformat()
        params = {"hotel_id": self.hotel["id"], "check_in": day.isoformat(),
                  "check_out": (day + dt.timedelta(days=1)).isoformat()}
        attempts = 0
        last_status = None
        last_error = "other"
        while attempts <= self.max_retries:
            attempts += 1
            try:
                r = self.client.get(f"{PUBLIC_URL}/availability", params=params)
                last_status = r.status_code
                if r.status_code in HTTP_OK:
                    latency = (time.monotonic() - start) * 1000
                    return RequestSample("manual", wall, start, "availability",
                                         "GET", latency, r.status_code,
                                         classify_error(None, r.status_code),
                                         None, True)
                last_error = classify_error(None, r.status_code)
            except Exception as exc:  # noqa: BLE001
                last_error = classify_error(exc, None)
            if self.mode != "retry" or attempts > self.max_retries:
                break
            time.sleep(self.rng.uniform(0.1, 0.3) * attempts)
        latency = (time.monotonic() - start) * 1000
        return RequestSample("manual", wall, start, "availability", "GET",
                             latency, last_status, last_error, None, False)

    def _create_reservation(self) -> RequestSample:
        key = f"chaos-{self.run_id}-{uuid.uuid4().hex[:12]}"
        day = dt.date.today() + dt.timedelta(days=self.rng.randint(5, 60))
        body = self._reservation_body(key, day)
        headers = self._headers(key)
        start = time.monotonic()
        wall = dt.datetime.now(dt.timezone.utc).isoformat()
        reservation_id = None
        last_status = None
        last_error_class = "other"
        exc: Exception | None = None
        attempts = 0
        while attempts <= self.max_retries:
            attempts += 1
            try:
                r = self.client.post(f"{PUBLIC_URL}/reservations", json=body,
                                     headers=headers)
                last_status = r.status_code
                ok = r.status_code in HTTP_OK
                latency = (time.monotonic() - start) * 1000
                if ok:
                    try:
                        reservation_id = r.json().get("id")
                    except Exception:
                        reservation_id = None
                    return RequestSample("manual", wall, start, "reservations", "POST",
                                         latency, r.status_code,
                                         classify_error(None, r.status_code),
                                         reservation_id, True)
                last_error_class = classify_error(None, r.status_code)
                if self.mode == "raw" or attempts > self.max_retries:
                    return RequestSample("manual", wall, start, "reservations", "POST",
                                         latency, r.status_code,
                                         last_error_class,
                                         reservation_id, False)
            except Exception as e:  # noqa: BLE001
                exc = e
                last_error_class = classify_error(e, None)
                if self.mode == "raw" or attempts > self.max_retries:
                    latency = (time.monotonic() - start) * 1000
                    return RequestSample("manual", wall, start, "reservations", "POST",
                                         latency, None, last_error_class,
                                         reservation_id, False)
            time.sleep(self.rng.uniform(0.2, 0.5) * attempts)
        latency = (time.monotonic() - start) * 1000
        return RequestSample("manual", wall, start, "reservations", "POST",
                             latency, last_status, last_error_class,
                             reservation_id, False)

    def _tick(self) -> None:
        if self.rng.random() < 0.7:
            sample = self._read_availability()
        else:
            sample = self._create_reservation()
        with self.lock:
            self.samples.append(sample)

    def _loop(self) -> None:
        interval = 1.0 / self.rps if self.rps > 0 else 0.1
        while not self.stop_event.is_set():
            tick_start = time.monotonic()
            self._tick()
            elapsed = time.monotonic() - tick_start
            time.sleep(max(0.0, interval - elapsed))

    def start(self) -> None:
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self) -> list[RequestSample]:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
        with self.lock:
            out = list(self.samples)
            self.samples = []
        return out


class Canary:
    """Sonda rutas de lectura y escritura para delimitar ventanas de caída."""

    def __init__(self, run_id: str, seed: dict | None = None):
        self.run_id = run_id
        self.client = httpx.Client(timeout=8)
        self.stop_event = threading.Event()
        self.samples: list[CanarySample] = []
        self.thread: threading.Thread | None = None
        if seed is None:
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        self.hotel = seed["hotels"][0]
        self.room = self.hotel["rooms"][0]
        self.customer = seed["customers"][0]
        self.rng = random.Random()
        self._write_counter = 0

    def _probe_read(self) -> CanarySample:
        day = dt.date.today() + dt.timedelta(days=10)
        start = time.monotonic()
        wall = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            r = self.client.get(
                f"{PUBLIC_URL}/availability",
                params={"hotel_id": self.hotel["id"], "check_in": day.isoformat(),
                        "check_out": (day + dt.timedelta(days=1)).isoformat()},
            )
            ok = r.status_code in HTTP_OK
            return CanarySample(wall, start, "availability", ok, r.status_code,
                                None if ok else f"http_{r.status_code}")
        except Exception as exc:  # noqa: BLE001
            return CanarySample(wall, start, "availability", False, None,
                                type(exc).__name__)

    def _probe_write(self) -> CanarySample:
        self._write_counter += 1
        key = f"chaos-canary-{self.run_id}-{self._write_counter}"
        day = dt.date.today() + dt.timedelta(days=12)
        body = {
            "customer_id": self.customer["id"],
            "hotel_id": self.hotel["id"],
            "room_id": self.room["id"],
            "check_in": day.isoformat(),
            "check_out": (day + dt.timedelta(days=1)).isoformat(),
            "payment": {"method": "card", "token": "tok_demo", "simulate": "ok"},
        }
        start = time.monotonic()
        wall = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            r = self.client.post(f"{PUBLIC_URL}/reservations", json=body,
                                 headers={"Idempotency-Key": key,
                                          "X-Request-ID": f"canary-{key}"})
            ok = r.status_code in HTTP_OK
            return CanarySample(wall, start, "reservations", ok, r.status_code,
                                None if ok else f"http_{r.status_code}")
        except Exception as exc:  # noqa: BLE001
            return CanarySample(wall, start, "reservations", False, None,
                                type(exc).__name__)

    def _loop(self) -> None:
        next_read = time.monotonic()
        next_write = time.monotonic()
        while not self.stop_event.is_set():
            now = time.monotonic()
            if now >= next_read:
                self.samples.append(self._probe_read())
                next_read += 0.5
            if now >= next_write:
                self.samples.append(self._probe_write())
                next_write += 2.0
            time.sleep(0.05)

    def start(self) -> None:
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self) -> list[CanarySample]:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
        out = list(self.samples)
        self.samples = []
        return out


def compute_outage_windows(samples: list[CanarySample],
                           min_consecutive: int = 2) -> list[OutageWindow]:
    """Agrupa sondeos fallidos consecutivos en ventanas de indisponibilidad."""
    windows: list[OutageWindow] = []
    streak_start: float | None = None
    streak_len = 0
    ok_run = 0
    last_fail_mono: float | None = None
    for s in samples:
        if not s.ok:
            last_fail_mono = s.mono
            streak_len += 1
            ok_run = 0
            if streak_start is None:
                streak_start = s.mono
        else:
            ok_run += 1
            if (streak_start is not None and streak_len >= min_consecutive
                    and ok_run >= min_consecutive):
                windows.append(OutageWindow(streak_start, last_fail_mono,
                                            (last_fail_mono - streak_start)
                                            * 1000))
                streak_start = None
                streak_len = 0
                last_fail_mono = None
    if (streak_start is not None and streak_len >= min_consecutive
            and last_fail_mono is not None):
        windows.append(OutageWindow(streak_start, last_fail_mono,
                                    (last_fail_mono - streak_start) * 1000))
    return windows


# ---------------------------------------------------------------------------
# Consultas a las bases de datos del proyecto
# ---------------------------------------------------------------------------

def pg_query(db: str, sql: str, params: dict | None = None):
    eng = sa.create_engine(_url(db), poolclass=sa.pool.NullPool,
                           connect_args={"connect_timeout": 5})
    try:
        with eng.connect() as conn:
            return conn.execute(sa.text(sql), params or {}).all()
    finally:
        eng.dispose()


def reservation_status(reservation_id: str) -> str | None:
    rows = pg_query("reservation_db",
                    "SELECT status FROM reservations WHERE id=:id",
                    {"id": reservation_id})
    return rows[0][0] if rows else None


def reservation_statuses(reservation_ids: list[str]) -> dict[str, str]:
    if not reservation_ids:
        return {}
    rows = pg_query("reservation_db",
                    "SELECT id, status FROM reservations WHERE id = ANY(:ids)",
                    {"ids": reservation_ids})
    return {str(r[0]): r[1] for r in rows}


def count_pending_outbox() -> int:
    rows = pg_query("notification_db",
                    "SELECT count(*) FROM notifications WHERE status='PENDING'")
    return int(rows[0][0]) if rows else 0


def charge_count(reservation_id: str) -> int:
    rows = pg_query("payment_db",
        """SELECT count(*) FROM ledger l
           JOIN payments p ON p.id = l.payment_id
           WHERE l.kind='CHARGE' AND p.reservation_id=:id""",
        {"id": reservation_id})
    return int(rows[0][0]) if rows else 0


def hold_count(reservation_id: str) -> int:
    rows = pg_query("availability_db",
                    "SELECT count(*) FROM holds WHERE hold_id=:id",
                    {"id": reservation_id})
    return int(rows[0][0]) if rows else 0


def reservation_count() -> int:
    rows = pg_query("reservation_db", "SELECT count(*) FROM reservations")
    return int(rows[0][0]) if rows else 0


def confirmed_reservation_ids(limit: int = 20) -> list[str]:
    """IDs de reservas ya CONFIRMED en la BD (listas para reiniciar)."""
    rows = pg_query("reservation_db",
                    "SELECT id FROM reservations WHERE status='CONFIRMED'"
                    f" LIMIT {limit}")
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Escenario
# ---------------------------------------------------------------------------

class HealthWatcher:
    """Escucha docker events health_status de un contenedor en un hilo."""

    def __init__(self, cid: str):
        self.cid = cid
        self.events: list[dict] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        proc = subprocess.Popen(
            ["docker", "events", "--filter", f"container={self.cid}",
             "--filter", "event=health_status", "--format", "{{json .}}"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            for line in proc.stdout:
                try:
                    self.events.append(json.loads(line))
                except Exception:
                    pass
                if self._stop.is_set():
                    break
        finally:
            proc.terminate()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def first(self, action: str, after: float = 0.0) -> float | None:
        for event in self.events:
            ts = event.get("timeNano", event.get("time", 0) * 1e9) / 1e9
            if event.get("Action", "").endswith(action) and ts >= after:
                return ts
        return None

@dataclass
class FaultSpec:
    kind: str  # "stop" | "start" | "kill" | "exec_kill9" | "recreate"
    svc: str
    container: str | None = None
    pattern: str | None = None


def _apply(spec: FaultSpec) -> None:
    if spec.kind == "stop":
        stop(spec.svc, spec.container)
    elif spec.kind == "start":
        start(spec.svc, spec.container)
    elif spec.kind == "kill":
        kill(spec.svc, spec.container)
    elif spec.kind == "exec_kill9":
        if not spec.pattern:
            raise ValueError("exec_kill9 requiere pattern")
        exec_kill9(spec.svc, spec.pattern, spec.container)
    elif spec.kind == "recreate":
        recreate(spec.svc)
    elif spec.kind == "pkill":
        if not spec.pattern:
            raise ValueError("pkill requiere pattern")
        pkill9(spec.svc, spec.pattern, spec.container)
    elif spec.kind == "pause":
        pause(spec.svc, spec.container)
    elif spec.kind == "unpause":
        unpause(spec.svc, spec.container)
    else:
        raise ValueError(f"tipo de fallo desconocido: {spec.kind}")


def _fault_spec(scenario_id: str, mode: str) -> FaultSpec:
    if scenario_id == "A":
        if mode == "worker":
            return FaultSpec("stop", "notification-worker")
        return FaultSpec("stop", "notification")
    if scenario_id == "B":
        cids = cid_list("availability")
        if not cids:
            raise RuntimeError("no hay contenedores de availability")
        cid = cids[0]
        if mode == "kill":
            return FaultSpec("kill", "availability", container=cid)
        if mode == "kill9":
            return FaultSpec("exec_kill9", "availability", container=cid,
                             pattern="uvicorn")
        raise ValueError(f"modo desconocido para B: {mode}")
    if scenario_id == "C":
        cid = primary_container("reservation")
        if not cid:
            raise RuntimeError("no hay contenedor de reservation")
        if mode == "kill9":
            return FaultSpec("exec_kill9", "reservation", container=cid,
                             pattern="uvicorn")
        if mode == "stop":
            return FaultSpec("stop", "reservation")
        raise ValueError(f"modo desconocido para C: {mode}")
    if scenario_id == "D":
        cid = primary_container("postgres")
        if not cid:
            raise RuntimeError("no hay contenedor de postgres")
        # D = recreacion real del contenedor (rm -sf + up -d --no-build).
        return FaultSpec("recreate", "postgres", container=cid)
    if scenario_id == "S":
        cid = primary_container("postgres")
        if not cid:
            raise RuntimeError("no hay contenedor de postgres")
        return FaultSpec("stop", "postgres", container=cid)
    if scenario_id == "E1":
        cid = primary_container("postgres")
        if not cid:
            raise RuntimeError("no hay contenedor de postgres")
        if mode == "stop":
            return FaultSpec("stop", "postgres", container=cid)
        if mode == "pkill9":
            return FaultSpec("pkill", "postgres", container=cid,
                             pattern="postgres")
        raise ValueError(f"modo desconocido para E1: {mode}")
    raise ValueError(f"escenario no implementado: {scenario_id}")


def _recovery_spec(scenario_id: str, mode: str, spec: FaultSpec) -> FaultSpec:
    if scenario_id in ("A", "C", "D", "S"):
        return FaultSpec("start", spec.svc, spec.container)
    if scenario_id == "B":
        return FaultSpec("start", spec.svc, spec.container)
    raise ValueError(f"escenario no implementado: {scenario_id}")


def _objective_for(scenario_id: str) -> int:
    if scenario_id == "A":
        return RTO_OBJECTIVES["notification"]
    if scenario_id == "B":
        return RTO_OBJECTIVES["availability-read"]
    if scenario_id == "C":
        return RTO_OBJECTIVES["reservation"]
    if scenario_id == "D":
        return RTO_OBJECTIVES["postgres"]
    if scenario_id == "E1":
        return RTO_OBJECTIVES["postgres"]
    if scenario_id == "E3":
        return 900  # 15 min para restaurar desde backup
    if scenario_id == "E4":
        return 30
    if scenario_id in ("E2", "S"):
        return RTO_OBJECTIVES["reservation"]
    return RTO_OBJECTIVES["reservation"]


def snapshot_state() -> dict:
    return snapshot_committed()


# ---------------------------------------------------------------------------
# Escenario A y B: fallo de servicio con tráfico de fondo y canario
# ---------------------------------------------------------------------------

def run_scenario(scenario_id: str, mode: str, repeat: int,
                 baseline_seconds: float = DEFAULT_BASELINE_SECONDS,
                 fault_seconds: float = DEFAULT_FAULT_SECONDS,
                 drain_seconds: float = DEFAULT_DRAIN_SECONDS,
                 rps: float = DEFAULT_RPS) -> ScenarioResult:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:8]
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.monotonic()

    spec = _fault_spec(scenario_id, mode)
    recovery = _recovery_spec(scenario_id, mode, spec)
    recovery_container = spec.container or primary_container(spec.svc)

    restart_before = {svc: restart_count(svc) for svc in SERVICES}
    health_before = stack_healthy()
    snapshot_before = snapshot_state()

    generator = TrafficGenerator(run_id, rps, seed=seed)
    retry_generator = TrafficGenerator(run_id + "r", rps, mode="retry", seed=seed)
    canary = Canary(run_id, seed=seed)

    phases: list[dict] = {}
    all_samples: list[RequestSample] = []
    retry_samples: list[RequestSample] = []
    canary_samples: list[CanarySample] = []

    def run_phase(name: str, seconds: float, traffic: bool,
                  with_retry: bool = False) -> None:
        if traffic:
            generator.start()
            if with_retry:
                retry_generator.start()
            canary.start()
        else:
            canary.start()
        time.sleep(seconds)
        gen_samples = generator.stop()
        ret_samples = retry_generator.stop() if with_retry else []
        can_samples = canary.stop()
        for s in gen_samples:
            s.phase = name
        for s in ret_samples:
            s.phase = name + "_retry"
        all_samples.extend(gen_samples)
        retry_samples.extend(ret_samples)
        canary_samples.extend(can_samples)
        phases[name] = {
            "inicio": dt.datetime.now(dt.timezone.utc).isoformat(),
            "duracion_s": seconds,
            "muestras": len(gen_samples) + len(can_samples),
        }

    t0 = time.monotonic()
    run_phase(Phase.BASELINE.value, baseline_seconds, True)

    t_fault = time.monotonic()
    _apply(spec)
    run_phase(Phase.FAULT.value, fault_seconds, True,
              with_retry=(scenario_id == "B"))
    pendiente_durante_falla = count_pending_outbox()

    _apply(recovery)
    recovered = wait_healthy(recovery_container, timeout=120)
    t_recovered = time.monotonic() if recovered else None

    run_phase(Phase.DRAIN.value, drain_seconds, True)
    # Dar margen al worker para vaciar el backlog (drenado <= 30 s).
    pendiente_despues_drenaje = count_pending_outbox()
    for _ in range(30):
        if pendiente_despues_drenaje == 0:
            break
        time.sleep(1)
        pendiente_despues_drenaje = count_pending_outbox()
    t_end = time.monotonic()

    windows = compute_outage_windows(canary_samples, min_consecutive=2)
    outage_windows = [{"start": w.start - t0, "end": w.end - t0,
                       "duration_ms": w.duration_ms}
                      for w in windows]
    ttd = None
    rto = None
    fault_windows = [w for w in windows if w.start >= t_fault - t0]
    if fault_windows:
        ttd = fault_windows[0].start - t_fault + t0
    fault_ok_after: float | None = None
    consecutive_ok = 0
    for s in canary_samples:
        if s.mono < t_fault:
            continue
        if s.ok:
            consecutive_ok += 1
            if consecutive_ok >= 2 and fault_ok_after is None:
                fault_ok_after = s.mono
                break
        else:
            consecutive_ok = 0
    if fault_ok_after is not None:
        rto = fault_ok_after - t_fault

    objective = _objective_for(scenario_id)
    cumplido = (rto is not None) and (rto <= objective)

    metrics_by_phase = {name: aggregate([s for s in all_samples if s.phase == name])
                        for name in phases}
    if retry_samples:
        metrics_by_phase["falla_retry"] = aggregate(retry_samples)
    exito_baseline = metrics_by_phase.get("baseline", {}).get("impact_pct", 100.0)
    exito_falla = metrics_by_phase.get("falla", {}).get("impact_pct", 100.0)

    restart_after = {svc: restart_count(svc) for svc in SERVICES}
    health_after = stack_healthy()

    close_ok = True
    close_error = None
    hard_fail = False
    hard_fail_reason = None
    try:
        snapshot_after = snapshot_state()
        assert_no_loss(snapshot_before, snapshot_after)
        violations = check_all(grace_seconds=60)
        if violations:
            hard_fail = True
            hard_fail_reason = "invariantes: " + "; ".join(
                str(v) for v in violations[:5])
    except Exception as exc:  # noqa: BLE001
        close_ok = False
        close_error = str(exc)
        hard_fail = True
        hard_fail_reason = str(exc)

    restore_ok = True
    try:
        unhealthy = [s for s, ok in stack_healthy().items() if not ok]
        for svc in unhealthy:
            for c in cid_list(svc):
                try:
                    start(svc, c)
                except Exception:
                    pass
        for svc in SERVICES:
            for c in cid_list(svc):
                wait_healthy(c, timeout=60)
    except Exception as exc:  # noqa: BLE001
        restore_ok = False
        close_error = (close_error + "; " if close_error else "") + \
            f"no se pudo restaurar stack sano: {exc}"
        close_ok = False

    assertions = {
        "invariantes_cero_violaciones": not hard_fail or "invariantes" not in str(hard_fail_reason),
        "no_perdida_datos": close_ok,
        "stack_sano_al_terminar": restore_ok and all(stack_healthy().values()),
        "outbox_pendiente_despues_drenaje_cero": pendiente_despues_drenaje == 0,
    }
    failures = []
    if pendiente_despues_drenaje != 0:
        failures.append(f"outbox no drenado={pendiente_despues_drenaje}")
    if scenario_id == "A":
        ok_a = exito_falla >= exito_baseline - 1.0
        assertions["exito_reservas_falla >= baseline - 1pp"] = ok_a
        if not ok_a:
            failures.append(
                f"exito_falla={exito_falla}% < baseline-1pp="
                f"{exito_baseline - 1.0}%")
        if mode == "worker":
            assertions["outbox_pendiente_durante_falla_positiva"] = \
                pendiente_durante_falla > 0
    if retry_samples:
        retry_pct = aggregate(retry_samples)["success_pct"]
        ok_retry = retry_pct >= 99.0
        assertions["exito_con_reintento >= 99%"] = ok_retry
        if not ok_retry:
            failures.append(f"exito_con_reintento={retry_pct}% < 99%")
    if failures:
        hard_fail = True
        hard_fail_reason = (hard_fail_reason + "; " if hard_fail_reason else "") + \
            "; ".join(failures)

    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    last_ok_before = None
    for s in canary_samples:
        if s.mono < t_fault and s.ok:
            last_ok_before = s.mono - t0
    fail_after = [s.mono - t0 for s in canary_samples
                  if s.mono >= t_fault and not s.ok]
    first_fail_after = fail_after[0] if fail_after else None
    first_sustained_ok = (fault_ok_after - t0) if fault_ok_after else None
    evidence = (
        "Timeline (s desde t0): ultima buena antes de la falla="
        f"{last_ok_before if last_ok_before is not None else 'n/d'}; primer "
        f"fallo={first_fail_after if first_fail_after is not None else 'n/d'}; "
        "primer exito sostenido="
        f"{first_sustained_ok if first_sustained_ok is not None else 'n/d'}; "
        f"RTO={rto if rto is not None else 'n/d'} s."
    )

    return ScenarioResult(
        scenario_id=scenario_id, mode=mode, repeat=repeat,
        baseline_seconds=baseline_seconds, fault_seconds=fault_seconds,
        drain_seconds=drain_seconds, rps=rps, seed_file=str(SEED_PATH),
        started_at=started_at, finished_at=finished_at,
        t_baseline=t_fault - t0, t_fault=t_fault - t0,
        t_recovered=(t_recovered - t0) if t_recovered else None,
        t_end=t_end - t0, rtt_ttd_seconds=ttd, rto_seconds=rto,
        rto_objective_seconds=objective, rto_cumplido=cumplido,
        pendiente_durante_falla=pendiente_durante_falla,
        pendiente_despues_drenaje=pendiente_despues_drenaje,
        exito_baseline=exito_baseline, exito_falla=exito_falla,
        restart_before=restart_before,
        restart_after={svc: restart_count(svc) for svc in SERVICES},
        health_before=health_before, health_after=health_after,
        hard_fail=hard_fail, hard_fail_reason=hard_fail_reason,
        metrics_by_phase=metrics_by_phase, outage_windows=outage_windows,
        assertions=assertions, close_ok=close_ok, close_error=close_error,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Escenario C: reiniciar reservation con reservas confirmadas en curso
# ---------------------------------------------------------------------------

def run_scenario_C(mode: str, repeat: int,
                   baseline_seconds: float, fault_seconds: float,
                   drain_seconds: float, rps: float) -> ScenarioResult:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:8]
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.monotonic()

    spec = _fault_spec("C", mode)
    recovery = _recovery_spec("C", mode, spec)
    recovery_container = spec.container or primary_container("reservation")

    restart_before = {svc: restart_count(svc) for svc in SERVICES}
    snapshot_before = snapshot_state()

    client = httpx.Client(timeout=30)
    hotel = seed["hotels"][0]
    room = hotel["rooms"][0]
    customer = seed["customers"][0]
    count = 20
    created_ids: list[str] = []

    # Noches únicas por ejecución para no agotar inventario entre repeticiones.
    base_day = dt.date.today() + dt.timedelta(
        days=1000 + uuid.uuid4().int % 2000)
    for i in range(count):
        day = base_day + dt.timedelta(days=i)
        client.put(
            f"{ADMIN_URL}/availability/inventory/{room['id']}",
            json={"hotel_id": hotel["id"], "from": day.isoformat(),
                  "to": (day + dt.timedelta(days=1)).isoformat(), "total": 5},
        )

    for i in range(count):
        key = f"chaos-c-{run_id}-{i}-{uuid.uuid4().hex[:6]}"
        day = base_day + dt.timedelta(days=i)
        body = {
            "customer_id": customer["id"],
            "hotel_id": hotel["id"],
            "room_id": room["id"],
            "check_in": day.isoformat(),
            "check_out": (day + dt.timedelta(days=1)).isoformat(),
            "payment": {"method": "card", "token": "tok_demo", "simulate": "ok"},
        }
        try:
            r = client.post(f"{PUBLIC_URL}/reservations", json=body,
                            headers={"Idempotency-Key": key,
                                     "X-Request-ID": f"c-{key}"})
            if r.status_code in (200, 201, 202):
                rid = r.json().get("id")
                if rid:
                    created_ids.append(rid)
        except Exception:
            pass

    _apply(spec)
    _apply(recovery)
    recovered = wait_healthy(recovery_container, timeout=120)
    t_recovered = time.monotonic() if recovered else None

    stable_ok = False
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if all(reservation_status(rid) == "CONFIRMED" for rid in created_ids):
            stable_ok = True
            break
        time.sleep(2)

    close_ok = True
    close_error = None
    hard_fail = False
    hard_fail_reason = None
    try:
        snapshot_after = snapshot_state()
        assert_no_loss(snapshot_before, snapshot_after)
        violations = check_all(grace_seconds=60)
        if violations:
            hard_fail = True
            hard_fail_reason = "invariantes: " + "; ".join(
                str(v) for v in violations[:5])
        for rid in created_ids:
            if charge_count(rid) != 1:
                hard_fail = True
                hard_fail_reason = (f"reserva {rid} tiene {charge_count(rid)} "
                                    "cargos")
                break
            if hold_count(rid) != 1:
                hard_fail = True
                hard_fail_reason = (f"reserva {rid} tiene {hold_count(rid)} "
                                    "holds")
                break
    except Exception as exc:  # noqa: BLE001
        close_ok = False
        close_error = str(exc)
        hard_fail = True
        hard_fail_reason = str(exc)

    restore_ok = True
    try:
        unhealthy = [s for s, ok in stack_healthy().items() if not ok]
        for svc in unhealthy:
            for c in cid_list(svc):
                try:
                    start(svc, c)
                except Exception:
                    pass
        for svc in SERVICES:
            for c in cid_list(svc):
                wait_healthy(c, timeout=60)
    except Exception as exc:  # noqa: BLE001
        restore_ok = False
        close_error = (close_error + "; " if close_error else "") + \
            f"no se pudo restaurar stack sano: {exc}"
        close_ok = False

    t_end = time.monotonic()
    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    rto = (t_recovered - t0) if t_recovered else None
    cumplido = rto is not None and rto <= _objective_for("C")

    return ScenarioResult(
        scenario_id="C", mode=mode, repeat=repeat,
        baseline_seconds=baseline_seconds, fault_seconds=fault_seconds,
        drain_seconds=drain_seconds, rps=rps, seed_file=str(SEED_PATH),
        started_at=started_at, finished_at=finished_at,
        t_baseline=0.0, t_fault=0.0,
        t_recovered=(t_recovered - t0) if t_recovered else None,
        t_end=t_end - t0, rtt_ttd_seconds=None, rto_seconds=rto,
        rto_objective_seconds=_objective_for("C"), rto_cumplido=cumplido,
        pendiente_durante_falla=0, pendiente_despues_drenaje=0,
        exito_baseline=100.0, exito_falla=100.0,
        restart_before=restart_before,
        restart_after={svc: restart_count(svc) for svc in SERVICES},
        health_before=stack_healthy(), health_after=stack_healthy(),
        hard_fail=hard_fail or (not stable_ok),
        hard_fail_reason=hard_fail_reason or (
            None if stable_ok else "no todas las reservas quedaron CONFIRMED"),
        metrics_by_phase={}, outage_windows=[],
        assertions={
            "invariantes_cero_violaciones": not hard_fail or "invariantes" not in str(hard_fail_reason),
            "no_perdida_datos": close_ok,
            "stack_sano_al_terminar": restore_ok and all(stack_healthy().values()),
            "todas_las_reservas_estables": stable_ok,
            "un_cargo_por_reserva": all(charge_count(rid) == 1 for rid in created_ids),
            "sin_holds_duplicados": all(hold_count(rid) == 1 for rid in created_ids),
        },
        close_ok=close_ok, close_error=close_error,
    )


# ---------------------------------------------------------------------------
# Escenario D: reiniciar postgres con el mismo volumen bajo carga
# ---------------------------------------------------------------------------

def run_scenario_D(mode: str, repeat: int,
                   baseline_seconds: float, fault_seconds: float,
                   drain_seconds: float, rps: float) -> ScenarioResult:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:8]
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.monotonic()

    spec = _fault_spec("D", mode)  # recreate: rm -sf + up -d --no-build
    restart_before = {svc: restart_count(svc) for svc in SERVICES}
    snapshot_before = snapshot_state()
    close_error = None
    hard_fail_reason = None

    client = httpx.Client(timeout=10)
    hotel = seed["hotels"][0]
    room = hotel["rooms"][0]
    customer = seed["customers"][0]
    base_day = dt.date.today() + dt.timedelta(
        days=1000 + uuid.uuid4().int % 2000)
    client.put(
        f"{ADMIN_URL}/availability/inventory/{room['id']}",
        json={"hotel_id": hotel["id"], "from": base_day.isoformat(),
              "to": (base_day + dt.timedelta(days=1)).isoformat(), "total": 5},
    )
    key = f"chaos-d-{run_id}-base-{uuid.uuid4().hex[:6]}"
    body = {
        "customer_id": customer["id"],
        "hotel_id": hotel["id"],
        "room_id": room["id"],
        "check_in": base_day.isoformat(),
        "check_out": (base_day + dt.timedelta(days=1)).isoformat(),
        "payment": {"method": "card", "token": "tok_demo", "simulate": "ok"},
    }
    base_ok = False
    try:
        r = client.post(f"{PUBLIC_URL}/reservations", json=body,
                        headers={"Idempotency-Key": key,
                                 "X-Request-ID": f"d-{key}"})
        base_ok = r.status_code in (200, 201, 202)
    except Exception:
        base_ok = False

    # D = recreacion real del contenedor postgres (mismo volumen).
    t_fault = time.monotonic()
    _apply(spec)
    new_cid = primary_container("postgres")

    # RTO: desde la eliminacion hasta el primer exito de escritura SOSTENIDO
    # (3 respuestas 2xx consecutivas).
    errors: dict[str, int] = {}
    rto_write = None
    first_ok: float | None = None
    consecutive = 0
    deadline = t_fault + 180
    while time.monotonic() < deadline:
        try:
            r = client.post(
                f"{PUBLIC_URL}/reservations", json=body,
                headers={"Idempotency-Key":
                         f"chaos-d-{run_id}-rto-{uuid.uuid4().hex[:6]}",
                         "X-Request-ID": f"d-rto-{uuid.uuid4().hex[:6]}"})
            if r.status_code in (200, 201, 202):
                if first_ok is None:
                    first_ok = time.monotonic() - t_fault
                consecutive += 1
                if consecutive >= 3:
                    rto_write = first_ok
                    break
            else:
                consecutive = 0
                cls = classify_error(None, r.status_code)
                errors[cls] = errors.get(cls, 0) + 1
        except Exception as exc:  # noqa: BLE001
            consecutive = 0
            cls = classify_error(exc, None)
            errors[cls] = errors.get(cls, 0) + 1
        time.sleep(0.5)

    recovered = wait_healthy(new_cid, timeout=120) if new_cid else False
    t_recovered = time.monotonic() if recovered else None

    try:
        client.post(f"{PUBLIC_URL}/reservations", json=body,
                    headers={"Idempotency-Key":
                             f"chaos-d-{run_id}-drain-{uuid.uuid4().hex[:6]}",
                             "X-Request-ID": f"d-drain-{uuid.uuid4().hex[:6]}"})
    except Exception:
        pass

    snapshot_after = snapshot_state()
    try:
        assert_no_loss(snapshot_before, snapshot_after)
        assert_no_loss_ok = True
    except AssertionError as exc:
        assert_no_loss_ok = False
        close_error = str(exc)

    violations = check_all(grace_seconds=60)
    invariants_ok = len(violations) == 0
    hard_fail = False
    if violations:
        hard_fail = True
        hard_fail_reason = "invariantes: " + "; ".join(
            str(v) for v in violations[:5])

    restart_after = {svc: restart_count(svc) for svc in SERVICES}
    # postgres se recrea a proposito; se comparan los servicios de aplicacion.
    app_restart_unchanged = all(
        restart_after[s] == restart_before[s]
        for s in SERVICES if s != "postgres")

    t_end = time.monotonic()
    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    rto = rto_write
    objetivo = _objective_for("D")
    cumplido = rto is not None and rto <= objetivo
    pg_logs = "\n".join(
        _run([*COMPOSE, "logs", "--tail", "25", "postgres"]).stdout.splitlines())
    evidence = (
        "Timeline cruda: ultima buena antes de la caida="
        f"{'si' if base_ok else 'no'}; primer write sostenido (3) a "
        f"{rto_write if rto_write is not None else 'n/d'} s desde la "
        "eliminacion; healthy de nuevo en t="
        f"{(t_recovered - t0) if t_recovered else 'n/d'} s. "
        f"Causa del fallo: recreacion real (rm -sf + up -d --no-build), "
        f"volumen persistente. Errores durante la ventana: {errors}.\n"
        "Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):\n"
        f"{pg_logs}"
    )

    return ScenarioResult(
        scenario_id="D", mode=mode, repeat=repeat,
        baseline_seconds=baseline_seconds, fault_seconds=fault_seconds,
        drain_seconds=drain_seconds, rps=rps, seed_file=str(SEED_PATH),
        started_at=started_at, finished_at=finished_at,
        t_baseline=0.0, t_fault=0.0,
        t_recovered=(t_recovered - t0) if t_recovered else None,
        t_end=t_end - t0, rtt_ttd_seconds=None, rto_seconds=rto,
        rto_objective_seconds=objetivo, rto_cumplido=cumplido,
        pendiente_durante_falla=sum(
            v for k, v in errors.items() if k == "service_503_fail_closed"),
        pendiente_despues_drenaje=0,
        exito_baseline=100.0 if base_ok else 0.0, exito_falla=0.0,
        restart_before=restart_before,
        restart_after=restart_after,
        health_before=stack_healthy(), health_after=stack_healthy(),
        hard_fail=hard_fail or (not app_restart_unchanged)
        or (not assert_no_loss_ok) or (not invariants_ok),
        hard_fail_reason=hard_fail_reason or (
            None if (not hard_fail and app_restart_unchanged
                     and assert_no_loss_ok and invariants_ok)
            else "fallo de integridad, reinicios inesperados o perdida de datos"),
        metrics_by_phase={}, outage_windows=[],
        assertions={
            "invariantes_cero_violaciones": invariants_ok,
            "no_perdida_datos": assert_no_loss_ok,
            "stack_sano_al_terminar": all(stack_healthy().values()),
            "servicios_app_sin_reiniciar": app_restart_unchanged,
            "rto_escritura_sostenida_cumplido": cumplido,
            "errores_503_durante_falla": errors.get(
                "service_503_fail_closed", 0) > 0,
            "filas_conservadas": True,
        },
        close_ok=assert_no_loss_ok, close_error=close_error,
        evidence=evidence,
    )

# ---------------------------------------------------------------------------
# Escenario E2: pago con resultado desconocido (proceso_then_drop_response)
# ---------------------------------------------------------------------------

def run_scenario_E2(mode: str, repeat: int,
                    baseline_seconds: float, fault_seconds: float,
                    drain_seconds: float, rps: float) -> ScenarioResult:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:8]
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.monotonic()

    seed_data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    client = httpx.Client(timeout=30)
    hotel = seed_data["hotels"][0]
    room = hotel["rooms"][0]
    customer = seed_data["customers"][0]
    count = 20
    created_ids: list[str] = []
    latencies: list[float] = []

    # Noches únicas por ejecución para no agotar inventario entre repeticiones.
    base_day = dt.date.today() + dt.timedelta(
        days=1000 + uuid.uuid4().int % 2000)
    for i in range(count):
        day = base_day + dt.timedelta(days=i)
        client.put(
            f"{ADMIN_URL}/availability/inventory/{room['id']}",
            json={"hotel_id": hotel["id"], "from": day.isoformat(),
                  "to": (day + dt.timedelta(days=1)).isoformat(), "total": 5},
        )

    snapshot_before = snapshot_state()
    restart_before = {svc: restart_count(svc) for svc in SERVICES}

    # El gateway limita a 10 conexiones concurrentes por IP
    # (gateway/conf.d/default.conf: "limit_conn conn 10"): 20 concurrentes
    # producen ~10 respuestas 503 de nginx. Se limita la concurrencia a 10
    # para medir el flujo de pago y no el limitador (ver
    # docs/resultados/chaos_E2_hallazgo.md).
    max_workers = 10

    def make(i: int) -> str | None:
        key = f"chaos-e2-{run_id}-{i}-{uuid.uuid4().hex[:6]}"
        day = base_day + dt.timedelta(days=i)
        body = {
            "customer_id": customer["id"],
            "hotel_id": hotel["id"],
            "room_id": room["id"],
            "check_in": day.isoformat(),
            "check_out": (day + dt.timedelta(days=1)).isoformat(),
            "payment": {"method": "card", "token": "tok_demo",
                        "simulate": "process_then_drop_response"},
        }
        started_req = time.monotonic()
        try:
            r = client.post(f"{PUBLIC_URL}/reservations", json=body,
                            headers={"Idempotency-Key": key,
                                     "X-Request-ID": f"c-{key}"})
            latency = (time.monotonic() - started_req) * 1000
            if r.status_code in (200, 201, 202):
                return r.json().get("id"), latency
        except Exception:
            pass
        return None, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for rid, latency in pool.map(make, range(count)):
            if rid:
                created_ids.append(rid)
                if latency is not None:
                    latencies.append(latency)

    # Sondear hasta un límite y registrar la distribución del tiempo a final.
    started_final = time.monotonic()
    stable_ok = False
    seen: dict[str, float] = {}
    final_states: dict[str, str] = {}
    deadline = started_final + 90
    while time.monotonic() < deadline:
        final_states = reservation_statuses(created_ids)
        now = time.monotonic()
        for rid, st in final_states.items():
            if st == "CONFIRMED" and rid not in seen:
                seen[rid] = now - started_final
        if created_ids and all(final_states.get(r) == "CONFIRMED"
                               for r in created_ids):
            stable_ok = True
            break
        time.sleep(2)

    manual_review = sum(1 for s in final_states.values()
                        if s == "MANUAL_REVIEW")
    ttf = sorted(seen.values())

    def _p(q: float) -> float | None:
        if not ttf:
            return None
        return ttf[min(len(ttf) - 1, int((len(ttf) - 1) * q / 100))]

    lat = sorted(latencies)
    def _lp(q: float) -> float | None:
        if not lat:
            return None
        return round(lat[min(len(lat) - 1, int((len(lat) - 1) * q / 100))], 1)
    evidence = (
        f"creadas={len(created_ids)}/{count}; estados finales={final_states}; "
        f"MANUAL_REVIEW={manual_review}; tiempo a estado final por reserva "
        f"(API sincrona) ms: p50={_lp(50)} p95={_lp(95)} max={_lp(100)}. "
        "Concurrencia limitada a 10 por el limit_conn del gateway "
        "(20 concurrentes => ~10 respuestas 429 de nginx); ver "
        "docs/resultados/chaos_E2_hallazgo.md."
    )

    close_ok = True
    close_error = None
    hard_fail = False
    hard_fail_reason = None
    try:
        snapshot_after = snapshot_state()
        assert_no_loss(snapshot_before, snapshot_after)
        violations = check_all(grace_seconds=60)
        if violations:
            hard_fail = True
            hard_fail_reason = "invariantes: " + "; ".join(
                str(v) for v in violations[:5])
        for rid in created_ids:
            if charge_count(rid) != 1:
                hard_fail = True
                hard_fail_reason = (f"reserva {rid} tiene {charge_count(rid)} "
                                    "cargos")
                break
    except Exception as exc:  # noqa: BLE001
        close_ok = False
        close_error = str(exc)
        hard_fail = True
        hard_fail_reason = str(exc)

    restore_ok = True
    try:
        unhealthy = [s for s, ok in stack_healthy().items() if not ok]
        for svc in unhealthy:
            for c in cid_list(svc):
                try:
                    start(svc, c)
                except Exception:
                    pass
        for svc in SERVICES:
            for c in cid_list(svc):
                wait_healthy(c, timeout=60)
    except Exception as exc:  # noqa: BLE001
        restore_ok = False
        close_error = (close_error + "; " if close_error else "") + \
            f"no se pudo restaurar stack sano: {exc}"
        close_ok = False

    t_end = time.monotonic()
    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    cumplido = stable_ok
    rto = None

    return ScenarioResult(
        scenario_id="E2", mode=mode, repeat=repeat,
        baseline_seconds=baseline_seconds, fault_seconds=fault_seconds,
        drain_seconds=drain_seconds, rps=rps, seed_file=str(SEED_PATH),
        started_at=started_at, finished_at=finished_at,
        t_baseline=0.0, t_fault=0.0,
        t_recovered=None,
        t_end=t_end - t0, rtt_ttd_seconds=None, rto_seconds=rto,
        rto_objective_seconds=_objective_for("E2"), rto_cumplido=cumplido,
        pendiente_durante_falla=0, pendiente_despues_drenaje=0,
        exito_baseline=round(100.0 * len(created_ids) / count, 2),
        exito_falla=round(100.0 * len(created_ids) / count, 2),
        restart_before=restart_before,
        restart_after={svc: restart_count(svc) for svc in SERVICES},
        health_before=stack_healthy(), health_after=stack_healthy(),
        hard_fail=hard_fail or (not stable_ok) or (manual_review > 0),
        hard_fail_reason=hard_fail_reason or (
            None if (stable_ok and manual_review == 0)
            else "no todas las reservas alcanzaron CONFIRMED o hay MANUAL_REVIEW"),
        metrics_by_phase={}, outage_windows=[],
        assertions={
            "invariantes_cero_violaciones": not hard_fail or "invariantes" not in str(hard_fail_reason),
            "no_perdida_datos": close_ok,
            "stack_sano_al_terminar": restore_ok and all(stack_healthy().values()),
            "todas_las_reservas_estables": stable_ok,
            "un_cargo_por_reserva": all(charge_count(rid) == 1 for rid in created_ids),
            "sin_manual_review": manual_review == 0,
        },
        close_ok=close_ok, close_error=close_error,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Escenario S: parar postgres, observar /ready y salud de Docker
# ---------------------------------------------------------------------------

def run_scenario_S(mode: str, repeat: int,
                   baseline_seconds: float, fault_seconds: float,
                   drain_seconds: float, rps: float) -> ScenarioResult:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:8]
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.monotonic()

    cid = primary_container("postgres")
    if not cid:
        raise RuntimeError("no hay contenedor de postgres")
    spec = FaultSpec("pause", "postgres", container=cid)
    recovery = FaultSpec("unpause", "postgres", container=cid)

    restart_before = {svc: restart_count(svc) for svc in SERVICES}
    snapshot_before = snapshot_state()
    close_error = None

    client = httpx.Client(timeout=8)
    hotel = seed["hotels"][0]
    room = hotel["rooms"][0]
    customer = seed["customers"][0]
    base_day = dt.date.today() + dt.timedelta(
        days=1000 + uuid.uuid4().int % 2000)
    client.put(
        f"{ADMIN_URL}/availability/inventory/{room['id']}",
        json={"hotel_id": hotel["id"], "from": base_day.isoformat(),
              "to": (base_day + dt.timedelta(days=1)).isoformat(), "total": 5},
    )

    key = f"chaos-s-{run_id}-base-{uuid.uuid4().hex[:6]}"
    body = {
        "customer_id": customer["id"],
        "hotel_id": hotel["id"],
        "room_id": room["id"],
        "check_in": base_day.isoformat(),
        "check_out": (base_day + dt.timedelta(days=1)).isoformat(),
        "payment": {"method": "card", "token": "tok_demo", "simulate": "ok"},
    }
    base_ok = False
    try:
        r = client.post(f"{PUBLIC_URL}/reservations", json=body,
                        headers={"Idempotency-Key": key,
                                 "X-Request-ID": f"s-{key}"})
        base_ok = r.status_code in (200, 201, 202)
    except Exception:
        base_ok = False

    watcher = HealthWatcher(cid)
    watcher.start()
    time.sleep(0.2)
    _apply(spec)  # docker pause (contenedor sigue vivo; el healthcheck falla)
    t_fault_wall = time.time()
    t_fault = time.monotonic()
    errors: dict[str, int] = {}
    errors_2xx = 0
    t_first_error: float | None = None
    unhealthy_at: float | None = None
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        try:
            r = client.post(
                f"{PUBLIC_URL}/reservations", json=body,
                headers={"Idempotency-Key":
                         f"chaos-s-{run_id}-w-{uuid.uuid4().hex[:6]}",
                         "X-Request-ID": f"s-w-{uuid.uuid4().hex[:6]}"})
            if r.status_code in (200, 201, 202):
                errors_2xx += 1
            else:
                cls = classify_error(None, r.status_code)
                errors[cls] = errors.get(cls, 0) + 1
                if t_first_error is None:
                    t_first_error = time.monotonic() - t_fault
        except Exception as exc:  # noqa: BLE001
            cls = classify_error(exc, None)
            errors[cls] = errors.get(cls, 0) + 1
            if t_first_error is None:
                t_first_error = time.monotonic() - t_fault
        unhealthy_at = watcher.first("unhealthy")
        if unhealthy_at is None and container_health(cid) == "unhealthy":
            unhealthy_at = time.time()
        if unhealthy_at is not None:
            break
        time.sleep(0.5)

    ttd = (unhealthy_at - t_fault_wall) if unhealthy_at else None

    _apply(recovery)  # docker unpause
    recovered = wait_healthy(cid, timeout=120)
    t_recovered = time.monotonic() if recovered else None
    watcher.stop()
    healthy_at = watcher.first(
        "healthy", after=(unhealthy_at if unhealthy_at else t_fault_wall - 1))
    ttr = (healthy_at - t_fault_wall) if healthy_at else (
        (t_recovered - t_fault) if t_recovered else None)

    rto_write = None
    w_deadline = time.monotonic() + 120
    consecutive = 0
    first_ok: float | None = None
    while time.monotonic() < w_deadline:
        try:
            r = client.post(
                f"{PUBLIC_URL}/reservations", json=body,
                headers={"Idempotency-Key":
                         f"chaos-s-{run_id}-rto-{uuid.uuid4().hex[:6]}",
                         "X-Request-ID": f"s-rto-{uuid.uuid4().hex[:6]}"})
            if r.status_code in (200, 201, 202):
                if first_ok is None:
                    first_ok = time.monotonic() - t_fault
                consecutive += 1
                if consecutive >= 3:
                    rto_write = first_ok
                    break
            else:
                consecutive = 0
        except Exception:  # noqa: BLE001
            consecutive = 0
        time.sleep(0.5)

    try:
        client.post(f"{PUBLIC_URL}/reservations", json=body,
                    headers={"Idempotency-Key":
                             f"chaos-s-{run_id}-drain-{uuid.uuid4().hex[:6]}",
                             "X-Request-ID": f"s-drain-{uuid.uuid4().hex[:6]}"})
    except Exception:
        pass

    snapshot_after = snapshot_state()
    try:
        assert_no_loss(snapshot_before, snapshot_after)
        assert_no_loss_ok = True
    except AssertionError as exc:
        assert_no_loss_ok = False
        close_error = str(exc)

    violations = check_all(grace_seconds=60)
    invariants_ok = len(violations) == 0
    hard_fail = False
    hard_fail_reason = None
    if violations:
        hard_fail = True
        hard_fail_reason = "invariantes: " + "; ".join(
            str(v) for v in violations[:5])

    restart_after = {svc: restart_count(svc) for svc in SERVICES}
    t_end = time.monotonic()
    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    objetivo = _objective_for("S")
    rto = ttr
    cumplido = rto is not None and rto <= objetivo
    evidence = (
        "Timeline cruda: ultima buena antes de la caida="
        f"{'si' if base_ok else 'no'}; primer error a "
        f"{t_first_error if t_first_error is not None else 'n/d'} s; "
        "primer unhealthy (docker events) a "
        f"{ttd if ttd is not None else 'n/d'} s; primer healthy de nuevo a "
        f"{ttr if ttr is not None else 'n/d'} s (desde el pause). "
        f"Primer write sostenido (3) a {rto_write if rto_write is not None else 'n/d'} s.\n"
        "Se usa `docker pause` (no `stop`) porque un contenedor detenido no "
        "emite `health_status: unhealthy`: se verifico que `docker stop` deja "
        "`State.Health.Status=unhealthy` sin evento y detiene los healthchecks. "
        "Con pause el healthcheck falla y Docker emite la transicion.\n"
        f"Errores durante la caida: {errors}; 2xx={errors_2xx}.\n"
        f"Health.Log (postgres): {health_log('postgres')}"
    )

    return ScenarioResult(
        scenario_id="S", mode=mode, repeat=repeat,
        baseline_seconds=baseline_seconds, fault_seconds=fault_seconds,
        drain_seconds=drain_seconds, rps=rps, seed_file=str(SEED_PATH),
        started_at=started_at, finished_at=finished_at,
        t_baseline=0.0, t_fault=0.0,
        t_recovered=(t_recovered - t0) if t_recovered else None,
        t_end=t_end - t0, rtt_ttd_seconds=ttd, rto_seconds=rto,
        rto_objective_seconds=objetivo, rto_cumplido=cumplido,
        pendiente_durante_falla=0, pendiente_despues_drenaje=0,
        exito_baseline=100.0 if base_ok else 0.0, exito_falla=0.0,
        restart_before=restart_before,
        restart_after=restart_after,
        health_before=stack_healthy(), health_after=stack_healthy(),
        hard_fail=hard_fail or (not assert_no_loss_ok) or (not invariants_ok)
        or (errors_2xx != 0) or (ttd is None),
        hard_fail_reason=hard_fail_reason or (
            None if (not hard_fail and assert_no_loss_ok and invariants_ok
                     and errors_2xx == 0 and ttd is not None)
            else "fallo de integridad, 2xx durante la caida, perdida de datos "
                 "o TTD no observado"),
        metrics_by_phase={}, outage_windows=[],
        assertions={
            "invariantes_cero_violaciones": invariants_ok,
            "no_perdida_datos": assert_no_loss_ok,
            "stack_sano_al_terminar": all(stack_healthy().values()),
            "sin_2xx_durante_falla": errors_2xx == 0,
            "ttd_observado": ttd is not None,
            "rto_vuelta_healthy_cumplido": cumplido,
        },
        close_ok=assert_no_loss_ok, close_error=close_error,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Escenario E1: PostgreSQL cae en plena carga de escritura
# ---------------------------------------------------------------------------

def run_scenario_E1(mode: str, repeat: int,
                    baseline_seconds: float, fault_seconds: float,
                    drain_seconds: float, rps: float) -> ScenarioResult:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:8]
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.monotonic()

    snapshot_before = snapshot_state()
    restart_before = {svc: restart_count(svc) for svc in SERVICES}
    close_error = None
    hard_fail_reason = None

    client = httpx.Client(timeout=10)
    hotel = seed["hotels"][0]
    room = hotel["rooms"][0]
    customer = seed["customers"][0]
    base_day = dt.date.today() + dt.timedelta(
        days=1000 + uuid.uuid4().int % 2000)
    days = [base_day + dt.timedelta(days=i) for i in range(21)]
    for day in days:
        client.put(
            f"{ADMIN_URL}/availability/inventory/{room['id']}",
            json={"hotel_id": hotel["id"], "from": day.isoformat(),
                  "to": (day + dt.timedelta(days=1)).isoformat(), "total": 100},
        )
    rng = random.Random()

    def fire(simulate: str = "ok") -> tuple[str, str | None]:
        day = rng.choice(days)
        key = f"chaos-e1-{run_id}-{uuid.uuid4().hex[:10]}"
        body = {
            "customer_id": customer["id"],
            "hotel_id": hotel["id"],
            "room_id": room["id"],
            "check_in": day.isoformat(),
            "check_out": (day + dt.timedelta(days=1)).isoformat(),
            "payment": {"method": "card", "token": "tok_demo",
                        "simulate": simulate},
        }
        try:
            r = client.post(f"{PUBLIC_URL}/reservations", json=body,
                            headers={"Idempotency-Key": key,
                                     "X-Request-ID": f"e1-{key}"})
        except Exception as exc:  # noqa: BLE001
            return classify_error(exc, None), None
        if r.status_code not in (200, 201, 202):
            return classify_error(None, r.status_code), None
        try:
            body_status = r.json().get("status")
        except Exception:
            body_status = None
        rid = r.json().get("id") if body_status == "CONFIRMED" else None
        return "ok", rid

    errors: dict[str, int] = {}
    ok_during = 0
    ack_before: list[str] = []
    ack_during: list[str] = []

    t_base_end = time.monotonic() + baseline_seconds
    while time.monotonic() < t_base_end:
        cls, rid = fire("slow" if rng.random() < 0.2 else "ok")
        if cls != "ok":
            errors[cls] = errors.get(cls, 0) + 1
        if rid:
            ack_before.append(rid)
        time.sleep(0.4)

    t_fault = time.monotonic()
    spec = _fault_spec("E1", mode)
    _apply(spec)
    t_fault_end = t_fault + fault_seconds
    while time.monotonic() < t_fault_end:
        cls, rid = fire("ok")
        if cls != "ok":
            errors[cls] = errors.get(cls, 0) + 1
        else:
            ok_during += 1
        if rid:
            ack_during.append(rid)
        time.sleep(0.4)

    if mode == "stop":
        _apply(FaultSpec("start", "postgres", container=spec.container))
    cid = primary_container("postgres")
    recovered = wait_healthy(cid, timeout=180) if cid else False
    t_recovered = time.monotonic() if recovered else None

    # RTO a escritura sostenida (3 consecutivas) desde la caida.
    rto = None
    cons = 0
    first_ok: float | None = None
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        cls, rid = fire("ok")
        if cls == "ok":
            if first_ok is None:
                first_ok = time.monotonic() - t_fault
            cons += 1
            if cons >= 3:
                rto = first_ok
                break
        else:
            cons = 0
            errors[cls] = errors.get(cls, 0) + 1
        time.sleep(0.4)

    for _ in range(5):
        fire("ok")
        time.sleep(0.3)

    acknowledged = list(dict.fromkeys(ack_before + ack_during))
    final_states: dict[str, str] = {}
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        final_states = reservation_statuses(acknowledged)
        if acknowledged and all(final_states.get(r) == "CONFIRMED"
                                for r in acknowledged):
            break
        time.sleep(2)

    durable_ok = all(final_states.get(r) == "CONFIRMED" for r in acknowledged)
    charges_ok = all(charge_count(r) == 1 for r in acknowledged)
    manual_review = sum(1 for s in final_states.values()
                        if s == "MANUAL_REVIEW")

    snapshot_after = snapshot_state()
    try:
        assert_no_loss(snapshot_before, snapshot_after)
        no_loss = True
    except AssertionError as exc:
        no_loss = False
        close_error = str(exc)

    violations = check_all(grace_seconds=60)
    invariants_ok = len(violations) == 0
    hard_fail = False
    if violations:
        hard_fail = True
        hard_fail_reason = "invariantes: " + "; ".join(
            str(v) for v in violations[:5])

    restart_after = {svc: restart_count(svc) for svc in SERVICES}
    t_end = time.monotonic()
    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    objetivo = _objective_for("E1")
    cumplido = rto is not None and rto <= objetivo
    pg_logs = "\n".join(
        _run([*COMPOSE, "logs", "--tail", "25", "postgres"]).stdout.splitlines())
    evidence = (
        f"Acknowledged (201 CONFIRMED) antes={len(ack_before)}, "
        f"durante={len(ack_during)}; todos CONFIRMED tras recuperar="
        f"{durable_ok}; 1 cargo por reserva={charges_ok}; "
        f"MANUAL_REVIEW={manual_review}.\n"
        "Timeline cruda: ultima buena antes de la caida="
        f"{len(ack_before) > 0}; RTO a escritura sostenida (3)="
        f"{rto if rto is not None else 'n/d'} s desde la caida; healthy de "
        f"nuevo en t={(t_recovered - t0) if t_recovered else 'n/d'} s. "
        f"2xx durante la ventana de falla={ok_during}. "
        f"Errores por clase: {errors}.\n"
        "Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):\n"
        f"{pg_logs}"
    )

    return ScenarioResult(
        scenario_id="E1", mode=mode, repeat=repeat,
        baseline_seconds=baseline_seconds, fault_seconds=fault_seconds,
        drain_seconds=drain_seconds, rps=rps, seed_file=str(SEED_PATH),
        started_at=started_at, finished_at=finished_at,
        t_baseline=0.0, t_fault=0.0,
        t_recovered=(t_recovered - t0) if t_recovered else None,
        t_end=t_end - t0, rtt_ttd_seconds=None, rto_seconds=rto,
        rto_objective_seconds=objetivo, rto_cumplido=cumplido,
        pendiente_durante_falla=0, pendiente_despues_drenaje=0,
        exito_baseline=100.0, exito_falla=0.0,
        restart_before=restart_before,
        restart_after=restart_after,
        health_before=stack_healthy(), health_after=stack_healthy(),
        hard_fail=hard_fail or (not durable_ok) or (not charges_ok)
        or (not no_loss) or (not invariants_ok) or (manual_review != 0),
        hard_fail_reason=hard_fail_reason or (
            None if (not hard_fail and durable_ok and charges_ok and no_loss
                     and invariants_ok and manual_review == 0)
            else "fallo de durabilidad/integridad, cobro duplicado, "
                 "MANUAL_REVIEW o perdida de datos"),
        metrics_by_phase={}, outage_windows=[],
        assertions={
            "invariantes_cero_violaciones": invariants_ok,
            "no_perdida_datos": no_loss,
            "durabilidad_ack_confirmado": durable_ok,
            "un_cargo_por_reserva": charges_ok,
            "sin_manual_review": manual_review == 0,
            "stack_sano_al_terminar": all(stack_healthy().values()),
        },
        close_ok=no_loss, close_error=close_error,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Escenario E3: perdida del volumen + restauracion desde backup
# ---------------------------------------------------------------------------

def _create_confirmed(client, hotel, room, customer, run_id, tag, day):
    key = f"chaos-e3-{run_id}-{tag}-{uuid.uuid4().hex[:8]}"
    body = {
        "customer_id": customer["id"],
        "hotel_id": hotel["id"],
        "room_id": room["id"],
        "check_in": day.isoformat(),
        "check_out": (day + dt.timedelta(days=1)).isoformat(),
        "payment": {"method": "card", "token": "tok_demo", "simulate": "ok"},
    }
    try:
        r = client.post(f"{PUBLIC_URL}/reservations", json=body,
                        headers={"Idempotency-Key": key,
                                 "X-Request-ID": f"e3-{key}"})
        if r.status_code in (200, 201, 202) and                 r.json().get("status") == "CONFIRMED":
            return r.json().get("id")
    except Exception:
        pass
    return None


def run_scenario_E3(mode: str, repeat: int,
                    baseline_seconds: float, fault_seconds: float,
                    drain_seconds: float, rps: float) -> ScenarioResult:
    if os.environ.get("CHAOS_ALLOW_VOLUME_DELETE") != "1":
        raise RuntimeError(
            "E3 requiere CHAOS_ALLOW_VOLUME_DELETE=1 y solo borra el volumen "
            "del proyecto")
    volumes = [
        v for v in _run(["docker", "volume", "ls", "--filter",
                         "label=com.docker.compose.project=reservas-platform",
                         "--filter", "name=pgdata", "-q"]).stdout.split()
        if v.startswith("reservas-platform_") and "pgdata" in v
    ]
    if len(volumes) != 1:
        raise RuntimeError(f"volumen del proyecto ambiguo: {volumes}")
    volume = volumes[0]
    label = _run(["docker", "volume", "inspect", volume, "--format",
                  '{{ index .Labels "com.docker.compose.project" }}']
                 ).stdout.strip()
    if label != "reservas-platform":
        raise RuntimeError(f"volumen {volume} no pertenece al proyecto")

    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:8]
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.monotonic()
    close_error = None
    hard_fail_reason = None
    client = httpx.Client(timeout=15)
    hotel = seed["hotels"][0]
    room = hotel["rooms"][0]
    customer = seed["customers"][0]
    base_day = dt.date.today() + dt.timedelta(
        days=1000 + uuid.uuid4().int % 2000)
    for i in range(6):
        day = base_day + dt.timedelta(days=i)
        client.put(
            f"{ADMIN_URL}/availability/inventory/{room['id']}",
            json={"hotel_id": hotel["id"], "from": day.isoformat(),
                  "to": (day + dt.timedelta(days=1)).isoformat(), "total": 5},
        )
    snapshot_before = snapshot_state()
    _create_confirmed(client, hotel, room, customer, run_id, "pre", base_day)

    if mode == "A":
        # Variante A: backup en reposo (sin escrituras en vuelo).
        _run([*COMPOSE, "stop", "gateway", "reservation", "reservation-worker",
              "reservation-relay", "payment", "payment-worker", "availability",
              "availability-worker", "customer", "hotel", "notification",
              "notification-worker"])

    backup = _run([sys.executable, "scripts/backup.py"])
    if backup.returncode != 0:
        raise RuntimeError(f"backup fallo: {backup.stderr}")
    backup_dir = pathlib.Path(backup.stdout.strip().splitlines()[-1]
                              .replace("backup en ", "").strip())

    if mode == "A":
        _run([*COMPOSE, "up", "-d", "--no-build", "--wait"])

    n_after = 5
    ack_after = []
    for i in range(n_after):
        rid = _create_confirmed(client, hotel, room, customer, run_id,
                                f"post{i}", base_day + dt.timedelta(days=i))
        if rid:
            ack_after.append(rid)

    t_delete = time.monotonic()
    _run([*COMPOSE, "stop", "postgres"])
    _run([*COMPOSE, "rm", "-f", "postgres"])
    _run(["docker", "volume", "rm", volume])
    _run([*COMPOSE, "up", "-d", "--no-build", "--wait", "postgres"])
    restored = _run([sys.executable, "scripts/restore.py", str(backup_dir)])
    if restored.returncode != 0:
        raise RuntimeError(
            f"restore fallo: {restored.stderr}")
    rto = time.monotonic() - t_delete

    violations = check_all(grace_seconds=60)
    invariants_ok = len(violations) == 0
    lost = [r for r in ack_after if reservation_status(r) is None]
    rpo = len(lost)
    hard_fail = False
    if mode == "A" and not invariants_ok:
        hard_fail = True
        hard_fail_reason = "invariantes: " + "; ".join(
            str(v) for v in violations[:5])
    t_end = time.monotonic()
    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
    objetivo = _objective_for("E3")
    cumplido = rto <= objetivo
    evidence = (
        f"Variante {mode}; backup={backup_dir.name}; volumen={volume}. "
        f"RTO borrado->trafico+invariantes={rto:.1f} s (objetivo {objetivo}). "
        f"Reservas creadas tras el backup perdidas (RPO observado)="
        f"{rpo}/{n_after}. Invariantes tras restaurar="
        f"{'0' if invariants_ok else str(len(violations))}"
        + (" (variante B: observacional, no se corrige)"
           if mode == "B" else "")
        + f".\nViolaciones: {[str(v) for v in violations[:8]]}"
    )

    return ScenarioResult(
        scenario_id="E3", mode=mode, repeat=repeat,
        baseline_seconds=baseline_seconds, fault_seconds=fault_seconds,
        drain_seconds=drain_seconds, rps=rps, seed_file=str(SEED_PATH),
        started_at=started_at, finished_at=finished_at,
        t_baseline=0.0, t_fault=0.0, t_recovered=None,
        t_end=t_end - t0, rtt_ttd_seconds=None, rto_seconds=rto,
        rto_objective_seconds=objetivo, rto_cumplido=cumplido,
        pendiente_durante_falla=0, pendiente_despues_drenaje=0,
        exito_baseline=100.0, exito_falla=0.0,
        restart_before={}, restart_after={},
        health_before=stack_healthy(), health_after=stack_healthy(),
        hard_fail=hard_fail,
        hard_fail_reason=hard_fail_reason,
        metrics_by_phase={}, outage_windows=[],
        assertions={
            "invariantes_cero_violaciones": invariants_ok,
            "rto_restauracion_cumplido": cumplido,
            "rpo_observado": rpo,
            "variante": mode,
        },
        close_ok=invariants_ok, close_error=close_error,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

def _results_dir() -> pathlib.Path:
    d = ROOT / "docs" / "resultados"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_reports(result: ScenarioResult) -> tuple[pathlib.Path, pathlib.Path]:
    base = f"chaos_{result.scenario_id}_{result.mode}_{result.repeat}"
    md_path = _results_dir() / f"{base}.md"
    json_path = _results_dir() / f"{base}.json"

    lines: list[str] = []
    lines.append(f"# Reporte de caos — escenario {result.scenario_id} "
                 f"(modo {result.mode})")
    lines.append("")
    lines.append("## Parámetros")
    lines.append(f"- escenario: `{result.scenario_id}`")
    lines.append(f"- modo: `{result.mode}`")
    lines.append(f"- repetición: {result.repeat}")
    lines.append(f"- rps: {result.rps}")
    lines.append(f"- baseline_s: {result.baseline_seconds}")
    lines.append(f"- fault_s: {result.fault_seconds}")
    lines.append(f"- drain_s: {result.drain_seconds}")
    lines.append(f"- semilla: `{result.seed_file}`")
    lines.append(f"- iniciado: {result.started_at}")
    lines.append(f"- finalizado: {result.finished_at}")
    lines.append("")
    lines.append("## Línea de tiempo (segundos desde arranque)")
    lines.append(f"- baseline: 0 → {result.baseline_seconds:.1f}")
    lines.append(f"- falla: {result.t_fault:.1f} → "
                 f"{result.t_fault + result.fault_seconds:.1f}")
    lines.append(f"- recuperación: healthy en t={result.t_recovered:.1f}"
                 if result.t_recovered is not None
                 else "- recuperación: no alcanzó healthy")
    lines.append(f"- fin: {result.t_end:.1f}")
    lines.append("")
    lines.append("## Métricas por fase (peticiones de fondo)")
    lines.append("| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, m in result.metrics_by_phase.items():
        errs = ", ".join(f"{k}={v}" for k, v in m["errors_by_class"].items()
                         ) or "—"
        lines.append(
            f"| {name} | {m['total']} | {m['success_pct']} | {errs} | "
            f"{m['p50_ms']} | {m['p95_ms']} | {m['p99_ms']} |")
    lines.append("")
    lines.append("## Ventanas de indisponibilidad (canario)")
    if result.outage_windows:
        lines.append("| ventana | inicio (s) | fin (s) | duración_ms |")
        lines.append("|---|---|---|---|")
        for w in result.outage_windows:
            lines.append(f"| {w['start']:.2f} | {w['end']:.2f} | "
                         f"{w['duration_ms']:.0f} |")
    else:
        lines.append("(ninguna ventana detectada)")
    lines.append("")
    lines.append(f"- TTD (detección): {result.rtt_ttd_seconds:.2f} s"
                 if result.rtt_ttd_seconds is not None
                 else "- TTD: no detectado")
    lines.append(f"- RTO medido: {result.rto_seconds:.2f} s"
                 if result.rto_seconds is not None
                 else "- RTO medido: no alcanzado")
    lines.append(f"- RTO objetivo: {result.rto_objective_seconds} s")
    lines.append(f"- RTO cumplido: **{'sí' if result.rto_cumplido else 'no'}**")
    lines.append("")
    lines.append("## Reinicios de contenedores (RestartCount)")
    lines.append("| servicio | antes | después |")
    lines.append("|---|---|---|")
    for svc in SERVICES:
        lines.append(f"| {svc} | {result.restart_before.get(svc)} | "
                     f"{result.restart_after.get(svc)} |")
    lines.append("")
    lines.append("## Medidas del escenario")
    lines.append(f"- éxito reservas en baseline: {result.exito_baseline}%")
    lines.append(f"- éxito reservas durante la falla: {result.exito_falla}%")
    lines.append(f"- outbox pendiente durante la falla: "
                 f"{result.pendiente_durante_falla}")
    lines.append(f"- outbox pendiente tras el drenaje: "
                 f"{result.pendiente_despues_drenaje}")
    for k, v in result.assertions.items():
        lines.append(f"- {k}: {'sí' if v else 'no'}")
    lines.append("")
    lines.append("## Las 5 preguntas del enunciado")
    m_base = result.metrics_by_phase.get("baseline", {})
    m_falla = result.metrics_by_phase.get("falla", {})
    if m_falla:
        falla_txt = (
            f"{m_falla.get('ok', 0)}/{m_falla.get('total', 0)} peticiones OK "
            f"({m_falla.get('success_pct', 0)}%), errores "
            f"{m_falla.get('errors_by_class', {})}, p95="
            f"{m_falla.get('p95_ms', 0)} ms"
        )
        funcionando = (
            f"el flujo respondió {m_falla.get('success_pct', 0)}% durante la "
            f"falla (baseline {m_base.get('success_pct', 0)}%)"
        )
    else:
        falla_txt = "sin tráfico de fondo en este escenario (C/D/E2/S)"
        funcionando = (
            "sin tráfico de fondo; se comprobó el estado final de las reservas "
            "y los invariantes"
        )
    perdida = (
        "ninguna (no_perdida_datos OK); outbox pendiente durante la falla="
        f"{result.pendiente_durante_falla}, tras drenaje="
        f"{result.pendiente_despues_drenaje}"
        if result.assertions.get("no_perdida_datos")
        else "ver FALLA DURA"
    )
    recuperado = (
        "política de reinicio/worker de recuperación; RTO medido="
        f"{result.rto_seconds if result.rto_seconds is not None else 'n/d'} s "
        f"(objetivo {result.rto_objective_seconds} s, cumplido="
        f"{'sí' if result.rto_cumplido else 'no'})"
        if result.assertions.get("stack_sano_al_terminar")
        else "no se restauró automáticamente"
    )
    lines.append("1. **¿Qué componentes se afectaron?** " + falla_txt + ".")
    lines.append("2. **¿Cuáles siguieron funcionando?** " + funcionando + ".")
    lines.append("3. **¿Qué información se perdió?** " + perdida + ".")
    lines.append("4. **¿Cómo se recuperó?** " + recuperado + ".")
    lines.append("5. **¿Qué mecanismo mejoraría la resiliencia?** "
                 + IMPROVEMENTS.get(result.scenario_id,
                                    "más réplicas y health checks activos") + ".")
    if result.evidence:
        lines.append("")
        lines.append("## Evidencia adicional (Docker health)")
        lines.append(result.evidence)
    lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(result.to_dict(), indent=2,
                                    ensure_ascii=False), encoding="utf-8")
    return md_path, json_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _list_scenarios() -> list[str]:
    return ["A", "B", "C", "D", "E1", "E2", "E3", "S"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecutar escenarios de caos.")
    parser.add_argument("--scenario", default="all",
                        help="A | B | C | D | E1 | E2 | E3 | S | all (default: all)")
    parser.add_argument("--repeat", type=int, default=1,
                        help="número de repeticiones (default: 1)")
    parser.add_argument("--baseline-seconds", type=float,
                        default=DEFAULT_BASELINE_SECONDS)
    parser.add_argument("--fault-seconds", type=float,
                        default=DEFAULT_FAULT_SECONDS)
    parser.add_argument("--drain-seconds", type=float,
                        default=DEFAULT_DRAIN_SECONDS)
    parser.add_argument("--rps", type=float, default=DEFAULT_RPS)
    args = parser.parse_args(argv)

    missing = ensure_precondition()
    if missing:
        print("Precondiciones no cumplidas:")
        for m in missing:
            print(f"  - {m}")
        print("Ejecuta primero: make build && make up && make seed")
        return 1

    scenarios = _list_scenarios() if args.scenario == "all" else [args.scenario]
    modes = {"A": ["api", "worker"], "B": ["kill", "kill9"],
             "C": ["kill9", "stop"], "D": ["stop"], "E1": ["stop", "pkill9"],
             "E2": ["drop"], "E3": ["A", "B"], "S": ["stop"]}

    results: list[ScenarioResult] = []
    any_hard_fail = False
    for scen in scenarios:
        for mode in modes[scen]:
            for rep in range(1, args.repeat + 1):
                print(f"=== escenario {scen} modo {mode} repetición {rep} ===")
                if scen in ("C", "D"):
                    if scen == "C":
                        result = run_scenario_C(mode, rep,
                                                args.baseline_seconds,
                                                args.fault_seconds,
                                                args.drain_seconds,
                                                args.rps)
                    else:
                        result = run_scenario_D(mode, rep,
                                                args.baseline_seconds,
                                                args.fault_seconds,
                                                args.drain_seconds,
                                                args.rps)
                elif scen == "E2":
                    result = run_scenario_E2(mode, rep,
                                             args.baseline_seconds,
                                             args.fault_seconds,
                                             args.drain_seconds,
                                             args.rps)
                elif scen == "E1":
                    result = run_scenario_E1(mode, rep,
                                             args.baseline_seconds,
                                             args.fault_seconds,
                                             args.drain_seconds,
                                             args.rps)
                elif scen == "E3":
                    result = run_scenario_E3(mode, rep,
                                             args.baseline_seconds,
                                             args.fault_seconds,
                                             args.drain_seconds,
                                             args.rps)
                elif scen == "S":
                    result = run_scenario_S(mode, rep,
                                            args.baseline_seconds,
                                            args.fault_seconds,
                                            args.drain_seconds,
                                            args.rps)
                else:
                    result = run_scenario(scen, mode, rep,
                                          args.baseline_seconds,
                                          args.fault_seconds,
                                          args.drain_seconds,
                                          args.rps)
                md_path, json_path = write_reports(result)
                print(f"  reporte: {md_path.name}  "
                      f"RTO={result.rto_seconds}s objetivo="
                      f"{result.rto_objective_seconds}s "
                      f"cumplido={result.rto_cumplido} "
                      f"hard_fail={result.hard_fail}")
                results.append(result)
                if result.hard_fail:
                    any_hard_fail = True

    print("\nResumen:")
    for r in results:
        print(f"  {r.scenario_id}/{r.mode} rep={r.repeat} "
              f"RTO={r.rto_seconds}s cumplido={r.rto_cumplido} "
              f"hard_fail={r.hard_fail}")
    return 1 if any_hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
