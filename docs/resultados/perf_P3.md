# perf P3 — contención de inventario (V1 vs V2)

Fecha: 2026-10-22 16:43 · k6 `grafana/k6:0.54.0` · 200 intentos concurrentes (shared-iterations, 200 VUs).

## Parámetros

- **V1**: 200 intentos sobre **1 habitación/noche** con K=20 unidades.
- **V2**: 200 intentos repartidos en **50 habitaciones/noche** (K=1 por habitación).
- 1 y 3 réplicas de `availability`, 3 repeticiones, bandas de fecha únicas por ejecución (inventario fijado por PUT antes de cada burst).
- Modelo abierto (k6 `shared-iterations`): los 200 intentos arrancan a la vez.

## Hipótesis previa

> V1 no escala con réplicas (se serializa en PostgreSQL) y aparecen esperas de lock; V2 escala mejor al repartir la contención.

## Resultados

| réplicas | variante | rep | CONFIRMED / esperado | estados BD | clases HTTP | p50 ms | p95 ms | rps del burst | locks máx | conexiones PG máx |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | V1 | 1 | **20/20** | CONFIRMED:20, REJECTED_NO_INVENTORY:180 | 201:200 | 5501 | 5557 | 242.6 | 0 | 46 |
| 1 | V1 | 2 | **20/20** | CONFIRMED:20, REJECTED_NO_INVENTORY:180 | 201:200 | 5398 | 5448 | 270.0 | 0 | 46 |
| 1 | V1 | 3 | **20/20** | CONFIRMED:20, REJECTED_NO_INVENTORY:180 | 201:200 | 5273 | 5336 | 227.6 | 0 | 46 |
| 1 | V2 | 1 | **50/50** | CONFIRMED:50, REJECTED_NO_INVENTORY:150 | 201:200 | 6066 | 6136 | 241.5 | 0 | 46 |
| 1 | V2 | 2 | **50/50** | CONFIRMED:50, REJECTED_NO_INVENTORY:150 | 201:200 | 5976 | 6057 | 222.4 | 0 | 46 |
| 1 | V2 | 3 | **50/50** | CONFIRMED:50, REJECTED_NO_INVENTORY:150 | 201:200 | 5915 | 6012 | 249.1 | 0 | 46 |
| 3 | V1 | 1 | **20/20** | CONFIRMED:20, REJECTED_NO_INVENTORY:180 | 201:200 | 5107 | 5176 | 307.7 | 0 | 49 |
| 3 | V1 | 2 | **20/20** | CONFIRMED:20, REJECTED_NO_INVENTORY:180 | 201:200 | 5238 | 5293 | 288.0 | 0 | 49 |
| 3 | V1 | 3 | **20/20** | CONFIRMED:20, REJECTED_NO_INVENTORY:180 | 201:200 | 5473 | 5523 | 222.9 | 0 | 45 |
| 3 | V2 | 1 | **50/50** | CONFIRMED:50, REJECTED_NO_INVENTORY:150 | 201:200 | 6135 | 6208 | 143.6 | 0 | 51 |
| 3 | V2 | 2 | **50/50** | CONFIRMED:50, REJECTED_NO_INVENTORY:150 | 201:200 | 6517 | 6592 | 265.0 | 0 | 52 |
| 3 | V2 | 3 | **50/50** | CONFIRMED:50, REJECTED_NO_INVENTORY:150 | 201:200 | 5918 | 5970 | 323.3 | 0 | 52 |

Nota: `POST /reservations` responde **201** al aceptar la reserva; el estado final se lee en la BD (las rechazadas quedan `REJECTED_NO_INVENTORY`). Por eso las 200 respuestas son 201 y el recuento de `CONFIRMED` es el que valida la no-sobreventa.

## Agregado (mediana y rango)

| réplicas | variante | CONFIRMED mediana | rps mediana [min–max] | p95 mediana | locks máx |
|---|---|---|---|---|---|
| 1 | V1 | 20 | 242.6 [227.6–270.0] | 5448 | 0 |
| 1 | V2 | 50 | 241.5 [222.4–249.1] | 6057 | 0 |
| 3 | V1 | 20 | 288.0 [222.9–307.7] | 5293 | 0 |
| 3 | V2 | 50 | 265.0 [143.6–323.3] | 6208 | 0 |

## Conclusión honesta

En **todas** las repeticiones se confirmaron exactamente las unidades disponibles (V1: K; V2: una por habitación): no hubo sobreventa. 
La medición de rps de un burst fijo de 200 intentos es **ruidosa** (V1/N=1 CV=7%; V1/N=3 CV=13%; V2/N=1 CV=5%; V2/N=3 CV=31%): no permite concluir escalado por sí sola. Lo que sí demuestra es lo importante: 12/12 repeticiones confirmaron exactamente las unidades disponibles (sin sobreventa), con 201 en todas las solicitudes y el rechazo registrado como `REJECTED_NO_INVENTORY`. Los locks se muestrearon a 1 s y dieron 0; eso **no descarta** esperas cortas, pero no hubo 503 por lock timeout y el fail-closed funcionó. V1 y V2 no muestran una diferencia de rps concluyente con este tamaño de muestra; la igualdad V1=N y V2=50 es el resultado robusto.

## Advertencia

k6, los servicios y PostgreSQL comparten la misma máquina. Los resultados son **comparativos**, no absolutos.
