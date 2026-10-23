# P1 — ¿por qué 2,09×? (CPU, conexiones y gateway)

Reanálisis de las series ya muestreadas en `perf_P1.json` (3 repeticiones por
N, ventana de medición 20–80 s). `docker stats` tarda ~4 s por muestra, así que
cada corrida guardó ~15 muestras; se reporta **media** y **máximo** de la
ventana. La CPU de `docker stats` es **% de un núcleo** (100 % = 1 core); Docker
tiene **12 CPUs lógicas**.

## Recurso → uso en la meseta → ¿cuello?

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

## Comprobaciones de infraestructura

- nginx: `worker_processes auto` (12 workers), `worker_connections 1024`,
  `limit_req_zone rate=50r/s`, `limit_conn_zone conn`. El gateway no pasa del
  29 % de **un** core y en P1 se usa el listener admin **sin** `limit_*`.
- k6 en contenedor: máximo 70 % de un core; no es el generador el que limita.
- `availability` por réplica usa hasta 1,8 cores (más de un hilo), no está
  limitada por un solo hilo/GIL; su suma (≈4,4 cores) sigue por debajo de los
  12 disponibles.
- PostgreSQL sube de ~0,7 a ~1,8 cores y las conexiones no crecen (40→56):
  no es un problema de pool, sino de **trabajo por consulta**.

## Conclusión

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
