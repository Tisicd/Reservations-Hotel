# perf P3b — contención aislada de `availability` (holds directos)

Fecha: 2026-10-22 22:45 · k6 `grafana/k6:0.54.0` · 200 holds concurrentes (shared-iterations, 200 VUs), TTL 30 s, `lock_timeout=2s`.

## Parámetros

- **V1**: 200 holds sobre 1 habitación/noche con K=20 unidades (200 intentos de 1 unidad).
- **V2**: 200 holds repartidos en 50 habitaciones/noche (K=1 por habitación).
- Llamada directa `POST /svc/availability/holds` por el listener admin (sin `reservation`, sin saga).
- 1 y 3 réplicas de `availability`, 3 repeticiones, fechas únicas por invocación.
- Locks muestreados ~100 ms (`wait_event_type='Lock'`) y delta de `pg_stat_database.deadlocks` por burst.

## Hipótesis previa (registrada en `tests/perf/hypotheses.md`)

> V1 tendrá más latencia que V2; N=3 no mejora V1; V2 mejora con N; habrá esperas de lock en V1 y ninguna en V2; cero deadlocks y cero 503 por lock timeout.

## Resultados

| réplicas | variante | rep | HELD / esperado | 409 | 503 | p50 ms | p95 ms | p99 ms | locks máx | intervalo muestreo ms | deadlocks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | V1 | 1 | **20/20** | 180 | 0 | 1759 | 2168 | 2198 | 8 | 370 | 0 |
| 1 | V1 | 2 | **20/20** | 180 | 0 | 1827 | 2183 | 2192 | 12 | 354 | 0 |
| 1 | V1 | 3 | **20/20** | 180 | 0 | 1768 | 2079 | 2121 | 11 | 353 | 0 |
| 1 | V2 | 1 | **50/50** | 150 | 0 | 1986 | 2185 | 2202 | 0 | 367 | 0 |
| 1 | V2 | 2 | **50/50** | 150 | 0 | 1917 | 2148 | 2160 | 0 | 340 | 0 |
| 1 | V2 | 3 | **50/50** | 150 | 0 | 1877 | 2058 | 2068 | 0 | 355 | 0 |
| 3 | V1 | 1 | **20/20** | 180 | 0 | 874 | 1136 | 1148 | 40 | 398 | 0 |
| 3 | V1 | 2 | **20/20** | 180 | 0 | 597 | 832 | 875 | 37 | 383 | 0 |
| 3 | V1 | 3 | **20/20** | 180 | 0 | 736 | 975 | 1002 | 41 | 385 | 0 |
| 3 | V2 | 1 | **50/50** | 150 | 0 | 879 | 979 | 998 | 2 | 415 | 0 |
| 3 | V2 | 2 | **50/50** | 150 | 0 | 949 | 1072 | 1080 | 0 | 429 | 0 |
| 3 | V2 | 3 | **50/50** | 150 | 0 | 973 | 1073 | 1099 | 2 | 415 | 0 |

## Agregado (mediana y rango)

| réplicas | variante | HELD mediana | p95 mediana [min–max] | locks máx | deadlocks |
|---|---|---|---|---|---|
| 1 | V1 | 20 | 2168 [2079–2183] | 12 | 0 |
| 1 | V2 | 50 | 2148 [2058–2185] | 0 | 0 |
| 3 | V1 | 20 | 975 [832–1136] | 41 | 0 |
| 3 | V2 | 50 | 1072 [979–1073] | 2 | 0 |

## Conclusión honesta

En todas las repeticiones se cumplen las aserciones duras: HELD exacto (K en V1, una por habitación en V2), resto 409 NO_INVENTORY, 0 respuestas 503, 0 deadlocks e invariantes en 0.
V1: p95 mediana N=1 2168 ms y N=3 975 ms; locks máx 41. V2: p95 2148 ms y 1072 ms; locks máx 2. La hipótesis **V1 > V2 no se confirma**: a N=1 los p95 son casi iguales y a N=3 V2 es incluso algo mayor. La contención de fila **sí aparece** (locks 8–12 en V1/N=1 y 37–41 en V1/N=3, frente a 0–2 en V2), pero no domina el p95: las solicitudes rechazadas esperan poco y fallan con 409; el p95 está marcado por la cola del pool/conexiones del servicio, no por el tiempo de lock. N=3 reduce la latencia (más pools) pero **no** cambia el número de HELD (K fijo) ni elimina la serialización de la fila. 0 respuestas 503, 0 deadlocks; `lock_timeout=2s` no llegó a dispararse.
La hipótesis «N=3 no mejora V1» **tampoco se sostiene en latencia**: mejora de 2168 a 975 ms, aunque N=3 no aumenta los HELD (siguen K) y los waiters de lock suben de 8–12 a 37–41, señal de que la fila sigue serializando. La hipótesis «V2 mejora con N» sí se cumple en latencia (2148 → 1072 ms).
Esto aísla `availability`: a diferencia de P3, aquí no hay saga síncrona de `reservation`. La latencia de P3 (5–6,5 s, 0 locks) se explica por la espera síncrona de la saga (`SAGA_SYNC_WAIT_SECONDS=5`), no por contención de filas. Recomendación: reducir `SAGA_SYNC_WAIT_SECONDS`, responder 202 inmediato o más procesos/réplicas de `reservation`.

## Advertencia

k6, los servicios y PostgreSQL comparten la misma máquina. Los resultados son **comparativos**, no absolutos.
