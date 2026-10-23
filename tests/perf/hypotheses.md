# Hipótesis de carga (registradas antes de ejecutar)

Fecha: 2026-10-22 · Commit base: `7cf7a1a` (tag `f4b1`) · Arnés: `tests/perf/`

Estas hipótesis se escriben **antes** de medir y no se reescriben después;
el informe de cada prueba dice si se cumplieron.

| ID | Hipótesis | Por qué |
|---|---|---|
| **P1** lectura 1 vs 3 réplicas | El rps máximo sostenible (p95 < 300 ms, errores < 1 %) **crece al menos 2×** al pasar de 1 a 3 réplicas, pero **no 3×**: PostgreSQL y la máquina son compartidos y las 3 réplicas abren más conexiones al mismo PG. | La lectura es stateless y escala horizontalmente, pero cada réplica consulta su propia conexión a `availability_db`; el cuello se moverá de CPU del servicio a PG/conexiones. |
| **P3 V1** contención en la misma habitación/noches con K unidades, 200 intentos concurrentes | **No escala con réplicas**: el rps de confirmaciones no mejora de 1 a 3 porque la escritura se serializa en PostgreSQL sobre la misma fila de inventario; aparecerán sesiones esperando bloqueos (`wait_event_type='Lock'`). Se confirman **exactamente K** y el resto recibe 409/503 (nunca sobreventa). | El `UPDATE ... WHERE held+confirmed < total` es atómico por fila; el lock de fila serializa a los escritores. |
| **P3 V2** mismos 200 intentos repartidos en 50 habitaciones/noches | **Escala mejor que V1** (más paralelismo real): el rps de confirmaciones sube y las esperas de lock bajan al repartir la contención entre filas. | Sin contención sobre una sola fila, el trabajo se reparte entre filas y conexiones. |
| **P2** mezcla 90/10 + 10 % de pagos `slow` | Las reservas son síncronas (espera hasta `SAGA_SYNC_WAIT_SECONDS=5`) y **acoplan** hilos: con 10 % de pagos lentos, la latencia de las reservas rápidas y de las lecturas **sube**; el `limit_conn` del gateway público no aplica (se usa admin), así que el efecto vendrá de hilos/conexiones de `reservation`. | Cada reserva lenta retiene un hilo de FastAPI y una conexión; el pool y los hilos son finitos. |
| **P5** rampa hasta saturación de la mezcla | El primer cuello será **CPU de `reservation`/`payment`** o el **pool de conexiones a PostgreSQL** (conexiones activas y locks), no el gateway (admin sin `limit_*`). Se identificará con CPU por contenedor, conexiones por BD y `wait_event_type='Lock'`. | El gateway admin no limita; el trabajo real está en los servicios síncronos y PG. |

## Nota de método

- Calentamiento 20 s; medición ≥ 60 s; 3 repeticiones; mediana y rango.
- Serie **ruidosa** si CV > 15 %.
- k6, servicios y PostgreSQL comparten máquina: resultados **comparativos**, no absolutos.

## P3b ? contenci?n aislada de `availability` (F4c)

Fecha: 2026-10-23 ? Commit: rama `feat/f4c-carga-cierre` (antes de medir)

| Hip?tesis | Por qu? |
|---|---|
| **V1** (misma habitaci?n/noches, K=20, 200 holds directos) tendr? **p95 mayor** que **V2** (50 habitaciones, 1 unidad cada una). | En V1 los 200 UPDATE compiten por la misma fila de `inventory`; en V2 se reparten entre 50 filas. |
| **N=3 no mejora V1**: el rps/tiempo de V1 con 3 r?plicas ser? similar al de 1. | La serializaci?n es por fila en PostgreSQL, no por proceso de `availability`; m?s r?plicas no eliminan el lock. |
| **V2 mejora con N=3** frente a N=1 (m?s paralelismo real entre filas/conexiones). | Sin una fila caliente, el trabajo se reparte entre r?plicas y conexiones. |
| Habr? **esperas de lock** (`wait_event_type='Lock'`) en V1 y pr?cticamente ninguna en V2; **cero deadlocks** y **cero 503 por lock timeout** (con `lock_timeout=2s`). | Es la comprobaci?n directa de la contenci?n; `lock_timeout` evita esperas infinitas. |
