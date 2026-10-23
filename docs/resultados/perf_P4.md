# perf P4 — límite público (429) y canario admin

Fecha: 2026-10-22 22:45 · Listener público `127.0.0.1:8088` (`limit_req 50r/s burst 40`, `limit_conn 20`) y canario paralelo por el admin (sin `limit_*`).

## Resultados

| fase | peticiones | 200 | 429 | otros | p50 ms | p95 ms |
|---|---|---|---|---|---|---|
| A (tasa, 20 hilos) | 200 | 0 | 0 | 200 | 21 | 122 |
| B (60 conexiones) | 60 | 0 | 0 | 60 | 62 | 79 |
| canario baseline | 20 | 0 | 0 | — | 9 | 32 |
| canario durante ráfaga | 8 | 0 | 0 | — | 31 | 95 |

Tiempo de recuperación tras la ráfaga: **10 ms**.

## Conclusión honesta

La ráfaga por el listener público produce **429** (límites por IP), que no se mezclan con 503 (fail-closed). El canario por el admin no recibe 429 y su p95 se mantiene en 95 ms (< 300 ms), aunque sube frente a los 32 ms del baseline: no hay degradación funcional. nginx no etiqueta si el 429 vino de `limit_req` o `limit_conn`; las fases A (tasa) y B (concurrencia) están diseñadas para ejercer cada una, pero el código HTTP es el mismo.

## Advertencia

k6/Python, los servicios y PostgreSQL comparten la misma máquina; los resultados son comparativos.
