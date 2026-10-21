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
        "    \n"
        "print(killed)\n"
    )
    _run(["docker", "exec", cid, "python", "-c", code])


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
            if "timeout" in low:
                return "timeout"
            return "connection"
        return f"exception:{type(exc).__name__}"
    if status_code is None:
        return "no_response"
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
    return {
        "total": total,
        "ok": len(ok),
        "success_pct": round(100.0 * len(ok) / total, 2) if total else 0.0,
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
        try:
            r = self.client.get(
                f"{PUBLIC_URL}/availability",
                params={"hotel_id": self.hotel["id"], "check_in": day.isoformat(),
                        "check_out": (day + dt.timedelta(days=1)).isoformat()},
            )
            latency = (time.monotonic() - start) * 1000
            ok = r.status_code in HTTP_OK
            res_id = None
            if ok:
                try:
                    rooms = r.json().get("rooms", [])
                    for room in rooms:
                        if room.get("room_id") == self.room["id"]:
                            break
                except Exception:
                    pass
            return RequestSample("manual", wall, start, "availability", "GET",
                                 latency, r.status_code,
                                 classify_error(None, r.status_code), res_id, ok)
        except Exception as exc:  # noqa: BLE001
            latency = (time.monotonic() - start) * 1000
            return RequestSample("manual", wall, start, "availability", "GET",
                                 latency, None, classify_error(exc, None), None, False)

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
                        pass
                    return RequestSample("manual", wall, start, "reservations", "POST",
                                         latency, r.status_code,
                                         classify_error(None, r.status_code),
                                         reservation_id, True)
                last_error_class = classify_error(None, r.status_code)
                if self.mode == "raw" or attempts > self.max_retries:
                    return RequestSample("manual", wall, start, "reservations", "POST",
                                         latency, r.status_code, last_error_class,
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
    """Agrupa sondeos fallidos consecutivos en ventanas de indisponibilidad.

    Una ventana se confirma tras ``min_consecutive`` sondeos fallidos
    consecutivos y comienza en el primer fallo de la racha; termina en el
    último fallo observado antes de que se confirmen
    ``min_consecutive`` sondeos OK consecutivos.
    """
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
# Estado / invariantes
# ---------------------------------------------------------------------------

def snapshot_state() -> dict:
    return snapshot_committed()


def count_pending_outbox() -> int:
    eng = sa.create_engine(
        _url("notification_db"), poolclass=sa.pool.NullPool,
        connect_args={"connect_timeout": 5},
    )
    try:
        with eng.connect() as conn:
            return conn.execute(
                sa.text("SELECT count(*) FROM notifications WHERE status='PENDING'")
            ).scalar_one()
    finally:
        eng.dispose()


# ---------------------------------------------------------------------------
# Escenario
# ---------------------------------------------------------------------------

@dataclass
class FaultSpec:
    kind: str  # "stop" | "start" | "kill" | "exec_kill9"
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
    raise ValueError(f"escenario no implementado en el arnés: {scenario_id}")


def _recovery_spec(scenario_id: str, mode: str, spec: FaultSpec) -> FaultSpec:
    if scenario_id == "A":
        return FaultSpec("start", spec.svc, spec.container)
    if scenario_id == "B":
        # modo kill: si el contenedor no se reinició solo, lo arrancamos;
        # modo kill9: el contenedor se reinicia con la política, solo esperamos.
        return FaultSpec("start", spec.svc, spec.container)
    raise ValueError(f"escenario no implementado: {scenario_id}")


def _objective_for(scenario_id: str) -> int:
    if scenario_id == "A":
        return RTO_OBJECTIVES["notification"]
    if scenario_id == "B":
        return RTO_OBJECTIVES["availability-read"]
    return RTO_OBJECTIVES["reservation"]


def run_scenario(scenario_id: str, mode: str, repeat: int,
                 baseline_seconds: float = DEFAULT_BASELINE_SECONDS,
                 fault_seconds: float = DEFAULT_FAULT_SECONDS,
                 drain_seconds: float = DEFAULT_DRAIN_SECONDS,
                 rps: float = DEFAULT_RPS) -> ScenarioResult:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:8]
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()

    spec = _fault_spec(scenario_id, mode)
    recovery = _recovery_spec(scenario_id, mode, spec)
    recovery_container = spec.container or primary_container(spec.svc)

    restart_before = {svc: restart_count(svc) for svc in SERVICES}
    health_before = stack_healthy()
    snapshot_before = snapshot_state()

    generator = TrafficGenerator(run_id, rps, seed=seed)
    canary = Canary(run_id, seed=seed)

    phases: list[dict] = {}
    all_samples: list[RequestSample] = []
    canary_samples: list[CanarySample] = []

    def run_phase(name: str, seconds: float, traffic: bool) -> None:
        if traffic:
            generator.start()
            canary.start()
        else:
            canary.start()
        time.sleep(seconds)
        gen_samples = generator.stop()
        can_samples = canary.stop()
        for s in gen_samples:
            s.phase = name
        all_samples.extend(gen_samples)
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
    run_phase(Phase.FAULT.value, fault_seconds, True)
    pendiente_durante_falla = count_pending_outbox()

    t_recover_start = time.monotonic()
    _apply(recovery)
    recovered = wait_healthy(recovery_container, timeout=120)
    t_recovered = time.monotonic() if recovered else None

    run_phase(Phase.DRAIN.value, drain_seconds, True)
    pendiente_despues_drenaje = count_pending_outbox()
    for _ in range(30):
        if pendiente_despues_drenaje == 0:
            break
        time.sleep(1)
        pendiente_despues_drenaje = count_pending_outbox()
    t_end = time.monotonic()

    # Tiempos relativos al arranque del escenario (segundos).
    def rel(t: float | None) -> float | None:
        return None if t is None else t - t0
    t_baseline_rel = 0.0
    t_fault_rel = t_fault - t0
    t_recovered_rel = rel(t_recovered)
    t_end_rel = t_end - t0

    # Canary -> ventanas de caída, TTD y RTO.
    windows = compute_outage_windows(canary_samples, min_consecutive=2)
    outage_windows = [{"start": w.start - t0, "end": w.end - t0,
                       "duration_ms": w.duration_ms}
                      for w in windows]
    ttd = None
    rto = None
    fault_windows = [w for w in windows if w.start >= t_fault]
    if fault_windows:
        ttd = fault_windows[0].start - t_fault
    # RTO: instante del primer sondeo OK sostenido tras el fallo.
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
    exito_baseline = metrics_by_phase.get("baseline", {}).get("success_pct", 100.0)
    exito_falla = metrics_by_phase.get("falla", {}).get("success_pct", 100.0)

    restart_after = {svc: restart_count(svc) for svc in SERVICES}
    health_after = stack_healthy()

    # Cierre obligatorio: invariantes + no pérdida + restaurar stack sano.
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
            hard_fail_reason = "invariantes: " + "; ".join(str(v) for v in violations[:5])
    except Exception as exc:  # noqa: BLE001
        close_ok = False
        close_error = str(exc)
        hard_fail = True
        hard_fail_reason = str(exc)

    # Restaurar stack sano (finalizer).
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

    exito_suficiente = exito_falla >= exito_baseline - 1.0
    outbox_drenado = pendiente_despues_drenaje == 0
    assertions = {
        "invariantes_cero_violaciones": not hard_fail or "invariantes" not in str(hard_fail_reason),
        "no_perdida_datos": close_ok,
        "stack_sano_al_terminar": restore_ok and all(stack_healthy().values()),
        "exito_reservas_falla >= baseline - 1pp": exito_suficiente,
        "outbox_pendiente_despues_drenaje_cero": outbox_drenado,
    }
    if scenario_id == "A" and mode == "worker":
        assertions["outbox_pendiente_durante_falla_positiva"] = pendiente_durante_falla > 0
    if not exito_suficiente or not outbox_drenado:
        hard_fail = True
        hard_fail_reason = (hard_fail_reason + "; " if hard_fail_reason else "") + \
            f"exito_falla={exito_falla}% < baseline-1pp={exito_baseline - 1.0}% " \
            f"o outbox no drenado={pendiente_despues_drenaje}"

    finished_at = dt.datetime.now(dt.timezone.utc).isoformat()

    return ScenarioResult(
        scenario_id=scenario_id, mode=mode, repeat=repeat,
        baseline_seconds=baseline_seconds, fault_seconds=fault_seconds,
        drain_seconds=drain_seconds, rps=rps, seed_file=str(SEED_PATH),
        started_at=started_at, finished_at=finished_at,
        t_baseline=t_baseline_rel, t_fault=t_fault_rel, t_recovered=t_recovered_rel,
        t_end=t_end_rel, rtt_ttd_seconds=ttd, rto_seconds=rto,
        rto_objective_seconds=objective, rto_cumplido=cumplido,
        pendiente_durante_falla=pendiente_durante_falla,
        pendiente_despues_drenaje=pendiente_despues_drenaje,
        exito_baseline=exito_baseline, exito_falla=exito_falla,
        restart_before=restart_before, restart_after=restart_after,
        health_before=health_before, health_after=health_after,
        hard_fail=hard_fail, hard_fail_reason=hard_fail_reason,
        metrics_by_phase=metrics_by_phase, outage_windows=outage_windows,
        assertions=assertions, close_ok=close_ok, close_error=close_error,
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
    lines.append(f"# Reporte de caos — escenario {result.scenario_id} (modo {result.mode})")
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
    lines.append(f"- falla: {result.t_fault:.1f} → {result.t_fault + result.fault_seconds:.1f}")
    lines.append(f"- recuperación: healthy en t={result.t_recovered:.1f}"
                 if result.t_recovered is not None else "- recuperación: no alcanzó healthy")
    lines.append(f"- fin: {result.t_end:.1f}")
    lines.append("")
    lines.append("## Métricas por fase (peticiones de fondo)")
    lines.append("| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, m in result.metrics_by_phase.items():
        errs = ", ".join(f"{k}={v}" for k, v in m["errors_by_class"].items()) or "—"
        lines.append(
            f"| {name} | {m['total']} | {m['success_pct']} | {errs} | "
            f"{m['p50_ms']} | {m['p95_ms']} | {m['p99_ms']} |"
        )
    lines.append("")
    lines.append("## Ventanas de indisponibilidad (canario)")
    if result.outage_windows:
        lines.append("| ventana | inicio (s) | fin (s) | duración_ms |")
        lines.append("|---|---|---|---|")
        for w in result.outage_windows:
            lines.append(f"| {w['start']:.2f} | {w['end']:.2f} | {w['duration_ms']:.0f} |")
    else:
        lines.append("(ninguna ventana detectada)")
    lines.append("")
    lines.append(f"- TTD (detección): {result.rtt_ttd_seconds:.2f} s"
                 if result.rtt_ttd_seconds is not None else "- TTD: no detectado")
    objetivo = result.rto_objective_seconds
    lines.append(f"- RTO medido: {result.rto_seconds:.2f} s"
                 if result.rto_seconds is not None else "- RTO medido: no alcanzado")
    lines.append(f"- RTO objetivo: {objetivo} s")
    lines.append(f"- RTO cumplido: **{'sí' if result.rto_cumplido else 'no'}**")
    lines.append("")
    lines.append("## Reinicios de contenedores (RestartCount)")
    lines.append("| servicio | antes | después |")
    lines.append("|---|---|---|")
    for svc in SERVICES:
        lines.append(f"| {svc} | {result.restart_before.get(svc)} | "
                     f"{result.restart_after.get(svc)} |")
    lines.append("")
    lines.append("## Aserciones duras")
    lines.append(f"- invariantes con 0 violaciones: "
                 f"{result.assertions['invariantes_cero_violaciones']}")
    lines.append(f"- no pérdida de datos: {result.assertions['no_perdida_datos']}")
    lines.append(f"- stack sano al terminar: "
                 f"{result.assertions['stack_sano_al_terminar']}")
    if result.hard_fail:
        lines.append(f"\n**FALLA DURA:** {result.hard_fail_reason}")
    if result.close_error:
        lines.append(f"\n*Nota de cierre:* {result.close_error}")
    lines.append("")
    lines.append("## Medidas del escenario")
    lines.append(f"- éxito reservas en baseline: {result.exito_baseline}%")
    lines.append(f"- éxito reservas durante la falla: {result.exito_falla}%")
    lines.append(f"- outbox pendiente durante la falla: {result.pendiente_durante_falla}")
    lines.append(f"- outbox pendiente tras el drenaje: {result.pendiente_despues_drenaje}")
    for k, v in result.assertions.items():
        lines.append(f"- {k}: {'sí' if v else 'no'}")
    lines.append("")
    lines.append("## Las 5 preguntas del enunciado")
    lines.append("1. **¿Qué componentes se afectaron?** (endpoints con errores) — ver tabla de métricas y ventanas de caída.")
    lines.append("2. **¿Cuáles siguieron funcionando?** (endpoints con éxito durante la falla) — ver éxito % por fase.")
    lines.append("3. **¿Qué información se perdió?** — " +
                 ("ninguna (no_perdida_datos OK)"
                  if result.assertions["no_perdida_datos"] else "ver FALLA DURA"))
    lines.append("4. **¿Cómo se recuperó?** — " +
                 ("politica de reinicio de Docker / worker de recuperación"
                  if result.assertions["stack_sano_al_terminar"] else "no se restauró automáticamente"))
    lines.append("5. **¿Qué mecanismo mejoraría la resiliencia?** — "
                 "cola durable con dead-letter y alerta por antigüedad del backlog (alarma OUTBOX_BACKLOG_OLD).")
    lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                         encoding="utf-8")
    return md_path, json_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _list_scenarios() -> list[str]:
    return ["A", "B"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecutar escenarios de caos.")
    parser.add_argument("--scenario", default="all",
                        help="A | B | all (default: all)")
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
    modes = {"A": ["api", "worker"], "B": ["kill", "kill9"]}

    results: list[ScenarioResult] = []
    any_hard_fail = False
    for scen in scenarios:
        for mode in modes[scen]:
            for rep in range(1, args.repeat + 1):
                print(f"=== escenario {scen} modo {mode} repetición {rep} ===")
                result = run_scenario(scen, mode, rep,
                                      args.baseline_seconds, args.fault_seconds,
                                      args.drain_seconds, args.rps)
                md_path, json_path = write_reports(result)
                print(f"  reporte: {md_path.name}  "
                      f"RTO={result.rto_seconds}s objetivo={result.rto_objective_seconds}s "
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
