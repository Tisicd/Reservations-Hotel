# perf P1 — lectura `GET /api/availability`: 1 vs 3 réplicas

Fecha: 2026-10-22 16:32 · Hotel dedicado: `7e96a4a2-9b0c-5cca-832b-7d84ce660e66` · noches `2032-04-13` → `2032-04-14`

## Parámetros

- k6 `grafana/k6:0.54.0` en contenedor, `ramping-arrival-rate` (modelo abierto).
- Calentamiento 20 s a 20 rps; medición 60 s rampa 20 → 700 rps; 2 conjuntos de réplicas × 3 repeticiones.
- Listener **admin** `127.0.0.1:8081` (`/api/*` sin `limit_*`).
- Umbrales: p95 < 300 ms y errores < 1.0 %.

## Hipótesis previa

> 3 réplicas suben el rps máximo ≥ 2× pero no 3× (PostgreSQL y la máquina son compartidos).

## Resultados por repetición

| réplicas | rep | rps máx (umbrales) | p95 en rps máx | p50 ms | p95 global | p99 ms | errores % | clases | CPU máx availability % | CPU total availability % | conexiones PG máx | locks máx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | **190** | 179 | 6854 | 10003 | 10008 | 15.29 | 200:6669, 504:1204 | 177 | 182 | 40 | 0 |
| 1 | 2 | **189** | 114 | 6283 | 10003 | 10011 | 11.78 | 200:6967, 504:930 | 177 | 177 | 44 | 0 |
| 1 | 3 | **169** | 219 | 6950 | 10003 | 10010 | 15.94 | 200:6600, 504:1252 | 179 | 184 | 46 | 0 |
| 3 | 1 | **350** | 67 | 388 | 4715 | 4836 | 0.00 | 200:14835 | 177 | 447 | 51 | 0 |
| 3 | 2 | **394** | 23 | 76 | 4734 | 4970 | 0.00 | 200:14952 | 169 | 430 | 56 | 0 |
| 3 | 3 | **432** | 100 | 34 | 5122 | 5333 | 0.00 | 200:14900 | 178 | 444 | 52 | 0 |

Nota: `p95 global`, `p99` y `errores %` incluyen la cola post-saturación (con 1 réplica la rampa termina en 504 por `proxy_read_timeout`); el punto sostenible es la columna `p95 en rps máx`, calculada por bucket de 2 s con p95 < 300 ms y errores < 1 %.

## Agregado (mediana y rango)

| réplicas | rps máx mediana [min–max] | CV % | p95 en rps máx mediana | errores % mediana | ruidosa |
|---|---|---|---|---|---|
| 1 | 189 [169–190] | 5.3 | 179 | 15.29 | no |
| 3 | 394 [350–432] | 8.5 | 67 | 0.00 | no |

**Contraste de la hipótesis:** se cumple (2.09×, ≥ 2× y < 3×).

## Conclusión honesta

El rps máximo sostenible pasó de **189** (1 réplica) a **394** (3 réplicas): **2.09×**, por lo que escala de forma sublineal. CPU total de `availability` (suma de réplicas, máx): 182 % → 444 % (2.45×); CPU de PostgreSQL: 70 % → 163 %; conexiones a PG: 44 → 52; máx locks: 0. Sin esperas de lock: el techo no es contención de filas; los datos apuntan a CPU de `availability` y/o a la máquina compartida.

## Advertencia

k6, los servicios y PostgreSQL comparten la misma máquina. Los resultados son **comparativos**, no absolutos.
