#!/usr/bin/env python3
"""Orquestador de pruebas de carga (k6 en contenedor) — F4b Parte 2.

Solo biblioteca estandar. Muestrea CPU (docker stats), conexiones y esperas de
lock en PostgreSQL, escala `availability` y genera el informe de cada prueba.
"""

import argparse
import datetime as dt
import json
import math
import os
import pathlib
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PERF_DIR = ROOT / "tests" / "perf"
RESULTS = ROOT / "docs" / "resultados"
STATE = PERF_DIR / "state.json"
OUT = PERF_DIR / "out"
K6_IMAGE = os.getenv("K6_IMAGE", "grafana/k6:0.54.0")
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.dev.yaml"]
ADMIN = os.getenv("GATEWAY_ADMIN_URL", "http://127.0.0.1:8081").rstrip("/")
THRESHOLDS = json.loads((PERF_DIR / "thresholds.json").read_text(encoding="utf-8"))
APP_SERVICES = ["availability", "reservation", "payment", "customer",
                "hotel", "notification", "availability-worker"]
SAMPLE_SERVICES = ["availability", "reservation", "payment", "postgres",
                   "gateway", "availability-worker"]


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _check(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    r = _run(cmd, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(
            f"comando fallo ({' '.join(cmd)}): {r.stderr.strip() or r.stdout.strip()}")
    return r


def _containers(svc: str) -> list[str]:
    r = _run(["docker", "ps", "--filter", f"label=com.docker.compose.service={svc}",
              "--format", "{{.ID}}"])
    return [x for x in r.stdout.split() if x]


def _ip(cid: str) -> str:
    r = _run(["docker", "inspect", cid, "--format",
              "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}"])
    parts = [p for p in r.stdout.split() if p]
    return parts[-1] if parts else ""


def _pg_container() -> str:
    r = _run(["docker", "ps", "--filter", "name=postgres", "--format", "{{.Names}}"])
    names = [n for n in r.stdout.split() if n]
    if not names:
        raise RuntimeError("no hay contenedor postgres")
    return names[0]


def _wait_healthy(n: int, timeout: float = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        ids = _containers("availability")
        if len(ids) == n:
            states = []
            for cid in ids:
                r = _run(["docker", "inspect", cid, "--format",
                          "{{.State.Health.Status}}"])
                states.append(r.stdout.strip())
            if all(s == "healthy" for s in states):
                return
        time.sleep(1)
    raise RuntimeError(f"availability no convergio a {n} replicas healthy")


def _probe(n: int, hotel: str, check_in: str, check_out: str,
           attempts: int = 200) -> set[str]:
    ips = {_ip(cid) for cid in _containers("availability")}
    url = (f"{ADMIN}/api/availability?hotel_id={hotel}"
           f"&check_in={check_in}&check_out={check_out}")
    seen: set[str] = set()
    for _ in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"X-Request-ID": "perf-probe"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                up = resp.headers.get("X-Upstream", "")
                ip = up.split(":")[0]
                if ip in ips:
                    seen.add(ip)
        except Exception:  # noqa: BLE001
            pass
        if len(seen) >= n:
            return seen
        time.sleep(0.1)
    raise RuntimeError(f"convergencia incompleta: {len(seen)}/{n} replicas "
                       f"({sorted(seen)})")


def scale(n: int, hotel: str, check_in: str, check_out: str) -> None:
    _check(COMPOSE + ["up", "-d", "--no-build", "--scale",
                      f"availability={n}", "availability"], timeout=300)
    _check(["make", "gateway-refresh"], timeout=300)
    _wait_healthy(n)
    seen = _probe(n, hotel, check_in, check_out)
    print(f"  convergencia: {len(seen)}/{n} replicas -> {sorted(seen)}")


class Sampler(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self.samples: list[dict] = []
        self.pg = _pg_container()

    def run(self) -> None:
        while not self._stop.is_set():
            t = time.time()
            cpu = self._cpu()
            conns, locks, by_db = self._pg()
            self.samples.append({"t": t, "cpu": cpu, "pg_conn": conns,
                                 "pg_lock": locks, "pg_by_db": by_db})
            self._stop.wait(1.0)

    def stop(self) -> None:
        self._stop.set()
        self.join(timeout=10)

    def _cpu(self) -> dict[str, float]:
        r = _run(["docker", "stats", "--no-stream", "--format",
                  "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"])
        out: dict[str, float] = {}
        for line in r.stdout.splitlines():
            parts = line.split("|")
            if len(parts) >= 2:
                try:
                    out[parts[0]] = float(parts[1].rstrip("%"))
                except ValueError:
                    pass
        return out

    def _pg(self) -> tuple[int, int, dict[str, int]]:
        base = ["docker", "exec", self.pg, "psql", "-U", "postgres", "-tAc"]
        r = _run([*base, "select datname, count(*) from pg_stat_activity "
                         "where datname is not null group by 1"])
        by_db: dict[str, int] = {}
        for line in r.stdout.splitlines():
            if "|" in line:
                name, count = line.rsplit("|", 1)
                try:
                    by_db[name] = int(count)
                except ValueError:
                    pass
        r = _run([*base, "select count(*) from pg_stat_activity "
                         "where wait_event_type='Lock'"])
        try:
            locks = int(r.stdout.strip() or 0)
        except ValueError:
            locks = 0
        return sum(by_db.values()), locks, by_db


def _parse_ts(value: str) -> float:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(p / 100.0 * len(ordered)) - 1))
    return ordered[idx]


def analyze(raw: pathlib.Path, summary: pathlib.Path) -> dict:
    points = []
    for line in raw.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") != "Point" or item.get("metric") != "http_req_duration":
            continue
        data = item["data"]
        points.append((_parse_ts(data["time"]), float(data["value"]),
                       str(data.get("tags", {}).get("status", ""))))
    if not points:
        raise RuntimeError(f"sin muestras http_req_duration en {raw}")
    t0 = min(p[0] for p in points)
    thr = THRESHOLDS["read"]
    buckets: dict[int, list[tuple[float, str]]] = {}
    for ts, value, status in points:
        elapsed = ts - t0
        if elapsed < 20 or elapsed > 90:
            continue
        buckets.setdefault(int((elapsed - 20) // 10), []).append((value, status))
    per_bucket = []
    for key in sorted(buckets):
        vals = buckets[key]
        p95 = _pct([v for v, _ in vals], 95)
        errors = sum(1 for _, s in vals if s != "200")
        per_bucket.append({"bucket": key, "n": len(vals), "rps": len(vals) / 10.0,
                           "p95": p95, "error_pct": 100.0 * errors / len(vals)})
    ok = [b["rps"] for b in per_bucket
          if b["p95"] < thr["p95_ms"] and b["error_pct"] < thr["error_pct"]]
    all_vals = [v for ts, v, _ in points if 20 <= ts - t0 <= 90]
    status_counts: dict[str, int] = {}
    for ts, _, status in points:
        if 20 <= ts - t0 <= 90:
            status_counts[status] = status_counts.get(status, 0) + 1
    errors = sum(c for s, c in status_counts.items() if s != "200")
    result = {
        "t0": t0,
        "rps_max_ok": max(ok) if ok else 0.0,
        "p50": _pct(all_vals, 50), "p95": _pct(all_vals, 95),
        "p99": _pct(all_vals, 99), "max": max(all_vals) if all_vals else 0.0,
        "error_pct": 100.0 * errors / len(all_vals) if all_vals else 0.0,
        "status": status_counts, "buckets": per_bucket,
    }
    if summary.exists():
        data = json.loads(summary.read_text(encoding="utf-8"))
        result["dropped"] = data.get("metrics", {}).get("dropped_iterations", {}).get("count", 0)
        result["http_reqs"] = data.get("metrics", {}).get("http_reqs", {}).get("count", 0)
    return result


def run_k6(script: str, env: dict[str, str]) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "raw.json"
    summary = OUT / "summary.json"
    for path in (raw, summary):
        path.unlink(missing_ok=True)
    cmd = ["docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
           "-v", f"{PERF_DIR}:/scripts", "-v", f"{OUT}:/out"]
    for key, value in env.items():
        cmd += ["-e", f"{key}={value}"]
    cmd += [K6_IMAGE, "run", "--out", "json=/out/raw.json", f"/scripts/{script}"]
    r = _run(cmd, timeout=400)
    if r.returncode != 0:
        raise RuntimeError(f"k6 fallo: {r.stderr.strip() or r.stdout.strip()}")
    return analyze(raw, summary)


def _cpu_summary(samples: list[dict], start: float, end: float) -> dict:
    out: dict[str, float] = {}
    for sample in samples:
        if not (start <= sample["t"] <= end):
            continue
        for name, value in sample["cpu"].items():
            svc = next((s for s in SAMPLE_SERVICES if f"-{s}-" in name), None)
            if svc:
                out[svc] = max(out.get(svc, 0.0), value)
    return out


def _series_summary(samples: list[dict], start: float, end: float,
                    cpu: dict) -> dict:
    window = [s for s in samples if start <= s["t"] <= end]
    return {
        "max_conn": max((s["pg_conn"] for s in window), default=0),
        "max_lock": max((s["pg_lock"] for s in window), default=0),
        "cpu_max": cpu,
        "samples": [{"t": round(s["t"] - start, 2),
                     "cpu": {k: round(v, 1) for k, v in s["cpu"].items()},
                     "pg_conn": s["pg_conn"], "pg_lock": s["pg_lock"]}
                    for s in window],
    }


def run_p1(state: dict, reps: int, replica_sets: list[int]) -> None:
    hotel = state["hotel_id"]
    check_in = state["base_day"]
    day = dt.date.fromisoformat(check_in) + dt.timedelta(days=1)
    check_out = day.isoformat()
    runs = []
    for n in replica_sets:
        scale(n, hotel, check_in, check_out)
        for rep in range(1, reps + 1):
            print(f"  P1 N={n} rep={rep} ...", flush=True)
            sampler = Sampler()
            sampler.start()
            result = run_k6("p1.js", {
                "BASE_URL": "http://host.docker.internal:8081",
                "HOTEL_ID": hotel, "CHECK_IN": check_in, "CHECK_OUT": check_out,
                "TARGET_RATE": "400", "RAMP": "60s",
            })
            time.sleep(0.5)
            sampler.stop()
            start, end = result["t0"] + 20, result["t0"] + 80
            cpu = _cpu_summary(sampler.samples, start, end)
            series = _series_summary(sampler.samples, start, end, cpu)
            runs.append({"replicas": n, "rep": rep, **{k: result[k] for k in (
                "rps_max_ok", "p50", "p95", "p99", "max", "error_pct", "status",
                "dropped", "http_reqs", "buckets")}, **series})
            print(f"    rps_max={result['rps_max_ok']:.0f} p95={result['p95']:.0f}ms "
                  f"err={result['error_pct']:.2f}% cpu={cpu}", flush=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "perf_P1.json").write_text(
        json.dumps({"runs": runs}, indent=2) + "\n", encoding="utf-8")
    write_report_p1(runs, hotel, check_in, check_out)


def _agg(values: list[float]) -> dict:
    mean = statistics.mean(values) if values else 0.0
    cv = (statistics.pstdev(values) / mean * 100.0) if mean else 0.0
    return {"median": statistics.median(values) if values else 0.0,
            "min": min(values) if values else 0.0,
            "max": max(values) if values else 0.0,
            "cv": cv, "noisy": cv > THRESHOLDS["noise_cv_pct"]}


def write_report_p1(runs: list[dict], hotel: str, check_in: str,
                    check_out: str) -> None:
    lines = [
        "# perf P1 — lectura `GET /api/availability`: 1 vs 3 réplicas",
        "",
        f"Fecha: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        f"Hotel dedicado: `{hotel}` · noches `{check_in}` → `{check_out}`",
        "",
        "## Parámetros",
        "",
        f"- k6 `{K6_IMAGE}` en contenedor, `ramping-arrival-rate` (modelo abierto).",
        "- Calentamiento 20 s a 20 rps; medición 60 s rampa 20 → 400 rps; "
        f"{len({r['replicas'] for r in runs})} conjuntos de réplicas × "
        f"{len(runs) // max(1, len({r['replicas'] for r in runs}))} repeticiones.",
        "- Listener **admin** `127.0.0.1:8081` (`/api/*` sin `limit_*`).",
        f"- Umbrales: p95 < {THRESHOLDS['read']['p95_ms']} ms y errores < "
        f"{THRESHOLDS['read']['error_pct']} %.",
        "",
        "## Hipótesis previa",
        "",
        "> 3 réplicas suben el rps máximo ≥ 2× pero no 3× (PostgreSQL y la "
        "máquina son compartidos).",
        "",
        "## Resultados por repetición",
        "",
        "| réplicas | rep | rps máx (umbrales) | p50 ms | p95 ms | p99 ms | "
        "errores % | clases | CPU máx availability % | conexiones PG máx | "
        "locks máx |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        classes = ", ".join(f"{k}:{v}" for k, v in sorted(r["status"].items()))
        lines.append(
            f"| {r['replicas']} | {r['rep']} | **{r['rps_max_ok']:.0f}** | "
            f"{r['p50']:.0f} | {r['p95']:.0f} | {r['p99']:.0f} | "
            f"{r['error_pct']:.2f} | {classes or '—'} | "
            f"{r['cpu_max'].get('availability', 0):.0f} | {r['max_conn']} | "
            f"{r['max_lock']} |")
    lines += ["", "## Agregado (mediana y rango)", "",
              "| réplicas | rps máx mediana [min–max] | CV % | p95 mediana | "
              "errores % mediana | ruidosa |", "|---|---|---|---|---|---|"]
    for n in sorted({r["replicas"] for r in runs}):
        rs = [r for r in runs if r["replicas"] == n]
        a = _agg([r["rps_max_ok"] for r in rs])
        p95 = statistics.median([r["p95"] for r in rs])
        err = statistics.median([r["error_pct"] for r in rs])
        lines.append(f"| {n} | {a['median']:.0f} [{a['min']:.0f}–{a['max']:.0f}] | "
                     f"{a['cv']:.1f} | {p95:.0f} | {err:.2f} | "
                     f"{'sí' if a['noisy'] else 'no'} |")
    med = {n: statistics.median([r["rps_max_ok"] for r in runs
                                 if r["replicas"] == n])
           for n in sorted({r["replicas"] for r in runs})}
    lines += ["", "## Conclusión honesta", ""]
    if 1 in med and 3 in med and med[1] > 0:
        ratio = med[3] / med[1]
        verdict = ("escala de forma aproximadamente lineal" if ratio >= 2.7 else
                   "escala de forma sublineal" if ratio >= 1.3 else
                   "no escala (mismo techo)")
        lines.append(
            f"El rps máximo sostenible pasó de **{med[1]:.0f}** (1 réplica) a "
            f"**{med[3]:.0f}** (3 réplicas): **{ratio:.2f}×**, por lo que "
            f"{verdict}. Las series de CPU de `availability`, conexiones a "
            "PostgreSQL y esperas de lock permiten atribuir el techo: si la CPU "
            "de availability no llega al 100 % y las conexiones/locks suben, el "
            "límite está en PostgreSQL o en la máquina compartida.")
    else:
        lines.append("Faltan datos de 1 o 3 réplicas para comparar.")
    lines += ["", "## Advertencia", "",
              "k6, los servicios y PostgreSQL comparten la misma máquina. Los "
              "resultados son **comparativos**, no absolutos.", ""]
    (RESULTS / "perf_P1.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  informe: {RESULTS / 'perf_P1.md'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--perf", default="all", help="P1 | all")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--replicas", default="1,3")
    args = parser.parse_args()
    if not STATE.exists():
        _check([sys.executable, str(PERF_DIR / "setup.py")], timeout=300)
    state = json.loads(STATE.read_text(encoding="utf-8"))
    replica_sets = [int(x) for x in args.replicas.split(",") if x]
    try:
        if args.perf in ("all", "P1"):
            print("P1 lectura 1 vs 3 replicas")
            run_p1(state, args.reps, replica_sets)
        else:
            raise SystemExit(f"prueba no implementada aun: {args.perf}")
    finally:
        print("finalizer: availability=3")
        try:
            scale(3, state["hotel_id"], state["base_day"],
                  (dt.date.fromisoformat(state["base_day"]) +
                   dt.timedelta(days=1)).isoformat())
        except Exception as exc:  # noqa: BLE001
            print(f"AVISO: no se pudo dejar availability=3: {exc}")


if __name__ == "__main__":
    main()
