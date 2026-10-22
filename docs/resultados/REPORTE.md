# REPORTE F4 — resiliencia y carga

Generado: 2026-10-22 16:45 · commit base `fcfe179`

## 1. Entorno

Fecha: 2026-10-22 · Commit base: `7cf7a1a` (tag `f4b1`)

### Hardware y virtualización

| Elemento | Valor |
|---|---|
| Equipo | PC local (Windows 11 Pro) |
| CPU | AMD Ryzen 5 5600G with Radeon Graphics · 6 núcleos / 12 hilos |
| RAM total | 15,4 GB (16 GB) |
| RAM asignada a Docker | 7.995.179.008 bytes ≈ **7,45 GiB** (`docker info .MemTotal`) |
| CPUs visibles a Docker | 12 (`docker info .NCPU`) |
| SO | Microsoft Windows 11 Pro 10.0.26200 build 26200 |
| Docker Desktop | **4.48.0** (207573) |
| Docker Engine | **28.5.1** (cliente y servidor) |
| Docker Compose | v2.40.2-desktop.1 |
| Backend de contenedores | WSL2, kernel 6.18.54.1-microsoft-standard-WSL2 |

### Software de prueba

| Elemento | Versión |
|---|---|
| k6 | `grafana/k6:0.54.0` (contenedor; ver `docs/imagenes.md`) |
| Python (arnés) | 3.13 (venv del repo) |
| PostgreSQL | 16 (contenedor `postgres`) |

### Advertencia

k6, los servicios y PostgreSQL **comparten la misma máquina**. Las cifras son
**comparativas** (1 vs 3 réplicas, V1 vs V2, antes/después) y **no absolutas**:
el techo observado puede ser de la máquina anfitriona y no del diseño.

### Reproducción

```
make build && make up && make seed
make invariants
make perf            # todas las pruebas
make perf PERF=P1    # una prueba
```

## 2. Caos

Un objetivo por escenario; S evalúa el TTD de detección (no el TTR). S2 evalúa la reconexión y reporta además el TTD de los healthchecks. Los JSON locales son la fuente; si faltan, se indica. Se excluyen las mediciones inválidas de S (docker pause) y D (stop/start), quedándose con las de SIGSTOP y recreación real.

| Escenario | Integridad | RTO/TTD medido (s) | Objetivo (s) | ¿Cumplido? | Reps |
|---|---|---|---|---|---|
| A/api | OK | 0.64 [0.64–0.72] | 300 | sí | 3 |
| A/worker | OK | 1.15 [0.81–1.17] | 300 | sí | 3 |
| B/kill | OK | 0.33 [0.29–2.41] | 2 | **no** | 5 |
| B/kill9 | OK | 0.24 [0.19–0.26] | 2 | sí | 5 |
| C/kill9 | OK | 7.17 [6.77–7.73] | 30 | sí | 3 |
| C/stop | OK | 15.30 [14.85–15.86] | 30 | sí | 3 |
| D | OK | 2.18 | 120 | sí | 1 |
| E1/pkill9 | OK | 20.80 [20.78–24.21] | 120 | sí | 3 |
| E1/stop | OK | 26.41 [26.37–29.86] | 120 | sí | 3 |
| E2/drop | OK | — | 30 | sí | 3 |
| E3/A | OK | 30.49 [30.46–30.55] | 900 | sí | 3 |
| E3/B | OK | 31.36 [30.80–32.25] | 900 | sí | 3 |
| E4/restart | OK | 6.55 [6.50–6.59] | 30 | sí | 3 |
| S | OK | 93.21 (TTD 93.21) | 30 | **no** | 1 |
| S2 | OK | 5.96 (TTD 85.28) | 30 | sí | 1 |

## 3. Carga

### P1 — lectura (1 vs 3 réplicas)

| réplicas | rps máx mediana [min–max] | CV % | p95 en rps máx | errores % (global) |
|---|---|---|---|---|
| 1 | 189 [169–190] | 5.3 | 179 | 15.29 |
| 3 | 394 [350–432] | 8.5 | 67 | 0.00 |

**Lectura: 1 → 3 réplicas = 2.09×.** Ver `perf_P1.md` para CPU, conexiones y el detalle.

### P3 — contención de escritura (V1 vs V2)

| variante | réplicas | CONFIRMED/esperado | rps mediana [min–max] | p95 mediana (ms) | locks máx |
|---|---|---|---|---|---|
| V1 | 1 | 20/20 | 242.6 [227.6–270.0] | 5448 | 0 |
| V1 | 3 | 20/20 | 288.0 [222.9–307.7] | 5293 | 0 |
| V2 | 1 | 50/50 | 241.5 [222.4–249.1] | 6057 | 0 |
| V2 | 3 | 50/50 | 265.0 [143.6–323.3] | 6208 | 0 |

**Escritura:** 12/12 repeticiones con exactamente las unidades disponibles (sin sobreventa).
El rps del burst de 200 es ruidoso; no se usa para concluir escalado. La integridad (K exacto) es el resultado robusto.

### Comparativa 1 vs 3 réplicas

- **Lectura (P1):** el rps máximo sostenible crece ~2,1× al pasar de 1 a 3 réplicas (sublineal); PostgreSQL y la máquina son compartidos.
- **Escritura (P3):** un burst fijo de 200 intentos no permite concluir escalado por rps; sí se mantiene la integridad exacta (K y 50).
- P2, P5 y P4 quedaron **recortados** (regla de recorte: P4, P5, P2).

## 4. Hallazgos

- B/kill: objetivo no cumplido en 1/5 reps (máx 2.41 s vs 2 s; mediana 0.33 s)
- S/stop: objetivo no cumplido en 1/1 reps (máx 93.21 s vs 30 s; mediana 93.21 s)
- B/kill: 1/5 reps > 2 s (máx 2.41 s); intermitente, no se ajusta el objetivo
- P3 V2/N=3: rps ruidoso (CV 31 %)
- S: `retries=12` da TTD ≈ 93 s (> 30 s); se mantiene por falsos positivos.
- `limit_conn`/`limit_req` son por IP: el listener admin sin límites se usa para medir capacidad; P4 (público) quedó recortado.
- RPO depende de la frecuencia de `make backup` (manual).
- Backup por BD, no consistente entre servicios (ventana entre dumps).
- P2, P5 y P4 no ejecutados (recorte declarado en este reporte).

## 5. Conclusiones (redactar)

### Resiliencia

### Capacidad y escalado

### Hallazgos y siguientes pasos
