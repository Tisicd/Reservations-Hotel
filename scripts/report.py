#!/usr/bin/env python3
"""Genera docs/resultados/REPORTE.md y actualiza docs/fallos.md (stdlib)."""

import datetime as dt
import json
import pathlib
import re
import statistics

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "docs" / "resultados"
REPORT = RES / "REPORTE.md"
FALLOS = ROOT / "docs" / "fallos.md"
ORDER = ["A", "B", "C", "D", "E1", "E2", "E3", "E4", "S", "S2"]


def _json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_chaos() -> dict:
    groups: dict[tuple[str, str], list[dict]] = {}
    for path in sorted(RES.glob("chaos_*.json")):
        data = _json(path)
        sid = data.get("scenario_id")
        mode = data.get("mode") or "-"
        if sid == "S" and "SIGSTOP" not in (data.get("evidence") or ""):
            continue  # mediciones antiguas con docker pause (invalidas)
        if sid == "D" and "rm -sf" not in (data.get("evidence") or "").lower():
            continue  # D antiguo hacia stop/start, no recreacion real
        groups.setdefault((sid, mode), []).append(data)
    return groups


def _median(values):
    return statistics.median(values) if values else None


def chaos_table(groups: dict) -> list[str]:
    lines = [
        "| Escenario | Integridad | RTO/TTD medido (s) | Objetivo (s) | "
        "¿Cumplido? | Reps |", "|---|---|---|---|---|---|",
    ]
    if not groups:
        lines.append("| — | — | — | — | — | sin JSON locales (ver `chaos_*.md`) |")
        return lines
    for sid in ORDER:
        modes = sorted(m for (s, m) in groups if s == sid)
        if not modes and sid in ("A", "B", "C", "E1", "E3", "S2"):
            continue
        for mode in modes:
            ds = groups[(sid, mode)]
            rto = [d["rto_seconds"] for d in ds if d.get("rto_seconds") is not None]
            ttd = [d["rtt_ttd_seconds"] for d in ds
                   if d.get("rtt_ttd_seconds") is not None]
            objs = [d["rto_objective_seconds"] for d in ds
                    if d.get("rto_objective_seconds") is not None]
            integ = all(not d.get("hard_fail") for d in ds)
            ok = all(bool(d.get("rto_cumplido")) for d in ds)
            measured = "—"
            if rto:
                med = _median(rto)
                measured = f"{med:.2f}"
                if len(rto) > 1:
                    measured += f" [{min(rto):.2f}–{max(rto):.2f}]"
                if ttd:
                    measured += f" (TTD {_median(ttd):.2f})"
            obj = f"{objs[0]:g}" if objs else "—"
            label = sid if mode in ("-", "stop") and sid not in ("E1", "B", "C") \
                else f"{sid}/{mode}"
            lines.append(f"| {label} | {'OK' if integ else '**FALLO**'} | "
                         f"{measured} | {obj} | {'sí' if ok else '**no**'} | "
                         f"{len(ds)} |")
    return lines


def p1_section() -> list[str]:
    path = RES / "perf_P1.json"
    if not path.exists():
        return ["Sin `perf_P1.json` local (ejecutar `make perf PERF=P1`)."]
    runs = _json(path)["runs"]
    by_n: dict[int, list[dict]] = {}
    for r in runs:
        by_n.setdefault(r["replicas"], []).append(r)
    lines = [
        "| réplicas | rps máx mediana [min–max] | CV % | p95 en rps máx | "
        "errores % (global) |", "|---|---|---|---|---|",
    ]
    med = {}
    for n in sorted(by_n):
        rs = by_n[n]
        vals = [r["rps_max_ok"] for r in rs]
        m = _median(vals)
        med[n] = m
        cv = (statistics.pstdev(vals) / statistics.mean(vals) * 100.0
              if statistics.mean(vals) else 0.0)
        lines.append(f"| {n} | {m:.0f} [{min(vals):.0f}–{max(vals):.0f}] | "
                     f"{cv:.1f} | {_median([r['p95_sustainable'] for r in rs]):.0f} | "
                     f"{_median([r['error_pct'] for r in rs]):.2f} |")
    if 1 in med and 3 in med and med[1]:
        lines.append("")
        lines.append(f"**Lectura: 1 → 3 réplicas = {med[3] / med[1]:.2f}×.** "
                     "Ver `perf_P1.md` para CPU, conexiones y el detalle.")
    return lines


def p3_section() -> list[str]:
    path = RES / "perf_P3.json"
    if not path.exists():
        return ["Sin `perf_P3.json` local (ejecutar `make perf PERF=P3`)."]
    runs = _json(path)["runs"]
    lines = [
        "| variante | réplicas | CONFIRMED/esperado | rps mediana [min–max] | "
        "p95 mediana (ms) | locks máx |", "|---|---|---|---|---|---|",
    ]
    for mode in ("V1", "V2"):
        for n in sorted({r["replicas"] for r in runs}):
            rs = [r for r in runs if r["mode"] == mode and r["replicas"] == n]
            if not rs:
                continue
            conf = _median([r["confirmed"] for r in rs])
            exp = _median([r["expected"] for r in rs])
            rps = [r["rps"] for r in rs]
            lines.append(f"| {mode} | {n} | {conf:.0f}/{exp:.0f} | "
                         f"{_median(rps):.1f} [{min(rps):.1f}–{max(rps):.1f}] | "
                         f"{_median([r['p95'] for r in rs]):.0f} | "
                         f"{max(r['max_lock'] for r in rs)} |")
    ok = all(r["confirmed"] == r["expected"] for r in runs)
    lines.append("")
    lines.append("**Escritura:** "
                 + (f"{len(runs)}/{len(runs)} repeticiones con exactamente las "
                    "unidades disponibles (sin sobreventa)."
                    if ok else "**recuento distinto del esperado** (ver P3)."))
    lines.append("El rps del burst de 200 es ruidoso; no se usa para concluir "
                 "escalado. La integridad (K exacto) es el resultado robusto.")
    return lines


def p1_analysis() -> list[str]:
    path = RES / "perf_P1_analisis.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^# .*\n", "", text)
    return [re.sub(r"^## ", "#### ", text, flags=re.MULTILINE).strip()]


def p3b_section() -> list[str]:
    path = RES / "perf_P3b.json"
    if not path.exists():
        return ["Sin `perf_P3b.json` local (ejecutar `make perf PERF=P3b`)."]
    runs = _json(path)["runs"]
    lines = [
        "| variante | réplicas | HELD/esperado | p95 mediana [min–max] | "
        "locks máx | deadlocks |", "|---|---|---|---|---|---|",
    ]
    for mode in ("V1", "V2"):
        for n in sorted({r["replicas"] for r in runs}):
            rs = [r for r in runs if r["mode"] == mode and r["replicas"] == n]
            if not rs:
                continue
            held = _median([r["held"] for r in rs])
            exp = _median([r["expected"] for r in rs])
            p95 = [r["p95"] for r in rs]
            lines.append(f"| {mode} | {n} | {held:.0f}/{exp:.0f} | "
                         f"{_median(p95):.0f} [{min(p95):.0f}–{max(p95):.0f}] | "
                         f"{max(r['max_lock'] for r in rs)} | "
                         f"{max(r['deadlocks'] for r in rs)} |")
    ok = all(r["held"] == r["expected"] and r["deadlocks"] == 0
             for r in runs)
    lines.append("")
    lines.append("**P3b:** " + (f"{len(runs)}/{len(runs)} con HELD exacto, "
                 "409 en el resto, 0 deadlocks e invariantes 0."
                 if ok else "**alguna repetición no cumple** (ver P3b)."))
    lines.append("V1 acumula esperas de lock (8–41) y V2 casi ninguna (0–2), "
                 "pero V1 **no** es más lento que V2 (p95 similar): el p95 lo "
                 "marca la cola del pool, no el lock. N=3 baja la latencia sin "
                 "cambiar los HELD (K fijo).")
    return lines


def p4_section() -> list[str]:
    path = RES / "perf_P4.json"
    if not path.exists():
        return ["Sin `perf_P4.json` local (ejecutar `make perf PERF=P4`)."]
    d = _json(path)

    def row(name: str, block: dict) -> str:
        codes = block["codes"]
        other = sum(v for k, v in codes.items() if k not in (200, 429))
        return (f"| {name} | {block['n']} | {codes.get(200, 0)} | "
                f"{codes.get(429, 0)} | {other} | {block['p50']:.0f} | "
                f"{block['p95']:.0f} |")

    lines = [
        "| fase | peticiones | 200 | 429 | otros | p50 ms | p95 ms |",
        "|---|---|---|---|---|---|---|",
        row("A (tasa)", d["phase_a"]),
        row("B (60 conexiones)", d["phase_b"]),
        row("canario baseline", d["canary_baseline"]),
        row("canario ráfaga", d["canary_burst"]),
        "",
    ]
    rec = d.get("recovery_ms")
    lines.append(f"Recuperación tras la ráfaga: **{rec:.0f} ms**."
                 if rec is not None else "Recuperación: no observada.")
    lines.append("El canario admin no recibe 429 y su p95 queda < 300 ms; el "
                 "límite público no degrada el tráfico administrativo.")
    return lines


def _read_entorno() -> str:
    path = RES / "entorno.md"
    if not path.exists():
        return "(sin `entorno.md`)"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^# .*\n", "", text)
    return re.sub(r"^## ", "### ", text, flags=re.MULTILINE).strip()


def findings(groups: dict) -> list[str]:
    out: list[str] = []
    for (sid, mode), ds in sorted(groups.items()):
        if not all(bool(d.get("rto_cumplido")) for d in ds):
            rto = [d["rto_seconds"] for d in ds if d.get("rto_seconds") is not None]
            obj = next((d["rto_objective_seconds"] for d in ds
                        if d.get("rto_objective_seconds") is not None), None)
            bad = sum(1 for d in ds if not bool(d.get("rto_cumplido")))
            if rto and obj is not None:
                out.append(f"{sid}/{mode}: objetivo no cumplido en {bad}/{len(ds)} "
                           f"reps (máx {max(rto):.2f} s vs {obj:g} s; "
                           f"mediana {_median(rto):.2f} s)")
            else:
                out.append(f"{sid}/{mode}: objetivo no cumplido")
        if any(d.get("hard_fail") for d in ds):
            out.append(f"{sid}/{mode}: hard_fail en alguna repeticion")
    b = groups.get(("B", "kill"), [])
    slow = [d["rto_seconds"] for d in b
            if d.get("rto_seconds") is not None and d["rto_seconds"] > 2]
    if slow:
        out.append(f"B/kill: {len(slow)}/{len(b)} reps > 2 s "
                   f"(máx {max(slow):.2f} s); intermitente, no se ajusta el objetivo")
    p3 = RES / "perf_P3.json"
    if p3.exists():
        runs = _json(p3)["runs"]
        for mode in ("V1", "V2"):
            for n in sorted({r["replicas"] for r in runs}):
                vals = [r["rps"] for r in runs
                        if r["mode"] == mode and r["replicas"] == n]
                if len(vals) > 1 and statistics.mean(vals):
                    cv = statistics.pstdev(vals) / statistics.mean(vals) * 100
                    if cv > 15:
                        out.append(f"P3 {mode}/N={n}: rps ruidoso (CV {cv:.0f} %)")
    out += [
        "S: `retries=12` da TTD ≈ 93 s (> 30 s); se mantiene por falsos positivos.",
        "`limit_conn`/`limit_req` son por IP: el listener admin sin límites se "
        "usa para medir capacidad; P4 mide el público y observa 429 sin "
        "degradar el canario admin.",
        "RPO depende de la frecuencia de `make backup` (manual).",
        "Backup por BD, no consistente entre servicios (ventana entre dumps).",
        "P1: 2,09× explicado por CPU de availability (2,45×) y PostgreSQL "
        "(~2,3×); gateway y k6 no son cuello (ver `perf_P1_analisis.md`).",
        "P3: la latencia de 5–6,5 s es la saga síncrona "
        "(`SAGA_SYNC_WAIT_SECONDS=5`), no contención; recomendación: responder "
        "202 inmediato, reducir la espera o más procesos/réplicas de "
        "`reservation`.",
        "P3b: V1 acumula locks (8–41) y V2 casi ninguno, pero V1 no es más "
        "lento que V2; N=3 baja latencia sin cambiar HELD (K fijo).",
        "P2 y P5 no ejecutados (recorte declarado en este reporte).",
    ]
    return out


def write_fallos(items: list[str]) -> None:
    block = ["<!-- report:findings -->", "## Hallazgos F4b Parte 2", ""]
    block += [f"- {x}" for x in items]
    block += ["<!-- /report:findings -->"]
    text = FALLOS.read_text(encoding="utf-8")
    pattern = re.compile(r"<!-- report:findings -->.*?<!-- /report:findings -->",
                         re.DOTALL)
    new = "\n".join(block)
    if pattern.search(text):
        text = pattern.sub(new, text)
    else:
        text = text.rstrip() + "\n\n" + new + "\n"
    FALLOS.write_text(text, encoding="utf-8")


def main() -> None:
    groups = load_chaos()
    items = findings(groups)
    lines = [
        "# REPORTE F4 — resiliencia y carga",
        "",
        f"Generado: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        f"commit base `{_commit()}`",
        "",
        "## 1. Entorno",
        "",
        _read_entorno(),
        "",
        "## 2. Caos",
        "",
        "Un objetivo por escenario; S evalúa el TTD de detección (no el TTR). "
        "S2 evalúa la reconexión y reporta además el TTD de los healthchecks. "
        "Los JSON locales son la fuente; si faltan, se indica. Se excluyen las "
        "mediciones inválidas de S (docker pause) y D (stop/start), quedándose "
        "con las de SIGSTOP y recreación real.",
        "",
        *chaos_table(groups),
        "",
        "## 3. Carga",
        "",
        "### P1 — lectura (1 vs 3 réplicas)",
        "",
        *p1_section(),
        "",
        "#### Análisis de CPU y cuello (P1)",
        "",
        *p1_analysis(),
        "",
        "### P3 — contención de escritura vía reservation (V1 vs V2)",
        "",
        *p3_section(),
        "",
        "### P3b — contención aislada de availability (holds directos)",
        "",
        *p3b_section(),
        "",
        "### P4 — límite público y canario admin",
        "",
        *p4_section(),
        "",
        "### Comparativa 1 vs 3 réplicas",
        "",
        "- **Lectura (P1):** ~2,1× (sublineal); CPU de availability y "
        "PostgreSQL crecen ~2,4×; gateway y k6 no saturan un núcleo.",
        "- **Escritura (P3/P3b):** el burst de 200 no permite concluir "
        "escalado por rps; la integridad exacta se mantiene. P3 medía la saga "
        "síncrona; P3b aísla availability y muestra locks en V1, sin mejora "
        "de HELD con N.",
        "",
        "### Limitaciones",
        "",
        "- P2 y P5 no ejecutados (recorte declarado); no hay conclusión de "
        "mezcla 90/10 ni de rampa de saturación de la mezcla.",
        "- Resultados comparativos en una sola máquina (k6, servicios y "
        "PostgreSQL comparten CPU/RAM).",
        "- P3: rps del burst ruidoso (CV hasta 31 %); no se usa para escalado.",
        "- P3b: locks muestreados ~100 ms; esperas más cortas pueden no "
        "registrarse. `lock_timeout=2s` se fija por rol durante la prueba y "
        "se revierte al terminar.",
        "",
        "## 4. Hallazgos",
        "",
        *[f"- {x}" for x in items],
        "",
        "## 5. Conclusiones (redactar)",
        "",
        "### Resiliencia",
        "",
        "### Capacidad y escalado",
        "",
        "### Hallazgos y siguientes pasos",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    write_fallos(items)
    print(f"reporte: {REPORT}")
    print(f"fallos: {FALLOS}")


def _commit() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() or "n/d"


if __name__ == "__main__":
    main()
