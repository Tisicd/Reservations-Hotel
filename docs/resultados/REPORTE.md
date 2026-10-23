# REPORTE F4 — resiliencia y carga

Generado: 2026-10-22 22:46 · commit base `bfbd3d5`

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

#### Análisis de CPU y cuello (P1)

Reanálisis de las series ya muestreadas en `perf_P1.json` (3 repeticiones por
N, ventana de medición 20–80 s). `docker stats` tarda ~4 s por muestra, así que
cada corrida guardó ~15 muestras; se reporta **media** y **máximo** de la
ventana. La CPU de `docker stats` es **% de un núcleo** (100 % = 1 core); Docker
tiene **12 CPUs lógicas**.

#### Recurso → uso en la meseta → ¿cuello?

| Recurso | N=1 (mediana de 3) | N=3 (mediana de 3) | ¿Cuello? |
|---|---|---|---|
| `availability` por réplica (máx) | 177 % [177–179] | 140–178 % por réplica | Consumidor principal, pero **no** satura la máquina |
| `availability` total (suma de réplicas) | media 124 % [124–128] · máx 177 % | media 251–265 % · máx **430–447 %** (≈4,4 cores) | **Sí, co-cuello**: crece 2,45× |
| PostgreSQL (máx) | 68–76 % | **147–181 %** (≈1,8 cores) | **Sí, co-cuello**: crece ~2,3–2,4× |
| Gateway nginx (máx) | 13–15 % | 25–29 % | **No**: 12 workers, 1.024 conexiones |
| k6 (máx) | 32–55 % | 51–70 % (≈0,7 core) | **No**: generador sobrado |
| Conexiones a PostgreSQL (máx) | 40–46 | 51–56 | **No**: prácticamente plano |
| Esperas de lock (`wait_event_type='Lock'`) | 0 | 0 | **No** (lectura sin contención de filas) |
| CPUs lógicas disponibles | 12 | 12 | — |

#### Comprobaciones de infraestructura

- nginx: `worker_processes auto` (12 workers), `worker_connections 1024`,
  `limit_req_zone rate=50r/s`, `limit_conn_zone conn`. El gateway no pasa del
  29 % de **un** core y en P1 se usa el listener admin **sin** `limit_*`.
- k6 en contenedor: máximo 70 % de un core; no es el generador el que limita.
- `availability` por réplica usa hasta 1,8 cores (más de un hilo), no está
  limitada por un solo hilo/GIL; su suma (≈4,4 cores) sigue por debajo de los
  12 disponibles.
- PostgreSQL sube de ~0,7 a ~1,8 cores y las conexiones no crecen (40→56):
  no es un problema de pool, sino de **trabajo por consulta**.

#### Conclusión

El 2,09× **no** se explica por la infraestructura de medición: ni gateway
(≤29 % de un core) ni k6 (≤70 %) están cerca de saturar un núcleo. Tampoco hay
un muro de CPU al 100 % de la máquina: en el punto de saturación
`availability` suma ≈4,4 cores y PostgreSQL ≈1,8, de 12 disponibles.

Lo que explica el resultado es el **crecimiento conjunto de CPU de
`availability` (2,45×) y PostgreSQL (~2,3–2,4×)** al pasar de 1 a 3 réplicas:
cada réplica adicional reduce su CPU en la meseta (177 % → ~155 %), pero el
trabajo total por petición en PG crece y las conexiones no se multiplican. El
codo se alcanza por **latencia** (p95 = 300 ms por cola de espera), no por un
recurso al 100 %: por eso 3 réplicas mejoran 2,09× en vez de 3×. Para acercarse
a 3× habría que reducir el trabajo compartido en PostgreSQL (caché/optimización
de la consulta de disponibilidad) o escalar la BD; ambas cosas están fuera del
alcance de F4.

No se modificó nginx: `worker_processes auto` ya estaba y no es el cuello, así
que no aplica una comparación antes/después.

### P3 — contención de escritura vía reservation (V1 vs V2)

| variante | réplicas | CONFIRMED/esperado | rps mediana [min–max] | p95 mediana (ms) | locks máx |
|---|---|---|---|---|---|
| V1 | 1 | 20/20 | 242.6 [227.6–270.0] | 5448 | 0 |
| V1 | 3 | 20/20 | 288.0 [222.9–307.7] | 5293 | 0 |
| V2 | 1 | 50/50 | 241.5 [222.4–249.1] | 6057 | 0 |
| V2 | 3 | 50/50 | 265.0 [143.6–323.3] | 6208 | 0 |

**Escritura:** 12/12 repeticiones con exactamente las unidades disponibles (sin sobreventa).
El rps del burst de 200 es ruidoso; no se usa para concluir escalado. La integridad (K exacto) es el resultado robusto.

### P3b — contención aislada de availability (holds directos)

| variante | réplicas | HELD/esperado | p95 mediana [min–max] | locks máx | deadlocks |
|---|---|---|---|---|---|
| V1 | 1 | 20/20 | 2168 [2079–2183] | 12 | 0 |
| V1 | 3 | 20/20 | 975 [832–1136] | 41 | 0 |
| V2 | 1 | 50/50 | 2148 [2058–2185] | 0 | 0 |
| V2 | 3 | 50/50 | 1072 [979–1073] | 2 | 0 |

**P3b:** 12/12 con HELD exacto, 409 en el resto, 0 deadlocks e invariantes 0.
V1 acumula esperas de lock (8–41) y V2 casi ninguna (0–2), pero V1 **no** es más lento que V2 (p95 similar): el p95 lo marca la cola del pool, no el lock. N=3 baja la latencia sin cambiar los HELD (K fijo).

### P4 — límite público y canario admin

| fase | peticiones | 200 | 429 | otros | p50 ms | p95 ms |
|---|---|---|---|---|---|---|
| A (tasa) | 200 | 0 | 0 | 200 | 21 | 122 |
| B (60 conexiones) | 60 | 0 | 0 | 60 | 62 | 79 |
| canario baseline | 20 | 0 | 0 | 20 | 9 | 32 |
| canario ráfaga | 8 | 0 | 0 | 8 | 31 | 95 |

Recuperación tras la ráfaga: **10 ms**.
El canario admin no recibe 429 y su p95 queda < 300 ms; el límite público no degrada el tráfico administrativo.

### Comparativa 1 vs 3 réplicas

- **Lectura (P1):** ~2,1× (sublineal); CPU de availability y PostgreSQL crecen ~2,4×; gateway y k6 no saturan un núcleo.
- **Escritura (P3/P3b):** el burst de 200 no permite concluir escalado por rps; la integridad exacta se mantiene. P3 medía la saga síncrona; P3b aísla availability y muestra locks en V1, sin mejora de HELD con N.

### Limitaciones

- P2 y P5 no ejecutados (recorte declarado); no hay conclusión de mezcla 90/10 ni de rampa de saturación de la mezcla.
- Resultados comparativos en una sola máquina (k6, servicios y PostgreSQL comparten CPU/RAM).
- P3: rps del burst ruidoso (CV hasta 31 %); no se usa para escalado.
- P3b: locks muestreados ~100 ms; esperas más cortas pueden no registrarse. `lock_timeout=2s` se fija por rol durante la prueba y se revierte al terminar.

## 4. Hallazgos

- B/kill: objetivo no cumplido en 1/5 reps (máx 2.41 s vs 2 s; mediana 0.33 s)
- S/stop: objetivo no cumplido en 1/1 reps (máx 93.21 s vs 30 s; mediana 93.21 s)
- B/kill: 1/5 reps > 2 s (máx 2.41 s); intermitente, no se ajusta el objetivo
- P3 V2/N=3: rps ruidoso (CV 31 %)
- S: `retries=12` da TTD ≈ 93 s (> 30 s); se mantiene por falsos positivos.
- `limit_conn`/`limit_req` son por IP: el listener admin sin límites se usa para medir capacidad; P4 mide el público y observa 429 sin degradar el canario admin.
- RPO depende de la frecuencia de `make backup` (manual).
- Backup por BD, no consistente entre servicios (ventana entre dumps).
- P1: 2,09× explicado por CPU de availability (2,45×) y PostgreSQL (~2,3×); gateway y k6 no son cuello (ver `perf_P1_analisis.md`).
- P3: la latencia de 5–6,5 s es la saga síncrona (`SAGA_SYNC_WAIT_SECONDS=5`), no contención; recomendación: responder 202 inmediato, reducir la espera o más procesos/réplicas de `reservation`.
- P3b: V1 acumula locks (8–41) y V2 casi ninguno, pero V1 no es más lento que V2; N=3 baja latencia sin cambiar HELD (K fijo).
- P2 y P5 no ejecutados (recorte declarado en este reporte).

## 5. Conclusiones (redactar)

### Resiliencia

### Capacidad y escalado

### Hallazgos y siguientes pasos
