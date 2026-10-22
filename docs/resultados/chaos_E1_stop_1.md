# Reporte de caos — escenario E1 (modo stop)

## Parámetros
- escenario: `E1`
- modo: `stop`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T19:05:20.484185+00:00
- finalizado: 2026-10-22T19:07:45.776698+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=129.8
- fin: 145.3

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 29.86 s
- RTO objetivo: 120 s
- RTO cumplido: **sí**

## Reinicios de contenedores (RestartCount)
| servicio | antes | después |
|---|---|---|
| customer | 0 | 0 |
| hotel | 0 | 0 |
| availability | 0 | 0 |
| payment | 0 | 0 |
| reservation | 0 | 0 |
| notification | 0 | 0 |
| postgres | 0 | 0 |
| gateway | 0 | 0 |

## Medidas del escenario
- éxito reservas en baseline: 100.0%
- éxito reservas durante la falla: 0.0%
- outbox pendiente durante la falla: 0
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- ack_antes_caida_suficientes: sí
- durabilidad_ack_confirmado: sí
- un_cargo_por_reserva: sí
- sin_manual_review: sí
- stack_sano_al_terminar: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=29.85907330000191 s (objetivo 120 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Semilla=1001; retraso de caida=1.69 s; ack antes de la caida=207 (objetivo >=200); ack durante=16; todos CONFIRMED tras recuperar=True; 1 cargo/reserva=True; MANUAL_REVIEW=0; 2xx durante la ventana=16. RTO a escritura sostenida (3)=29.85907330000191 s desde la caida; healthy de nuevo en t=129.75300779999816 s. Errores por clase: {'service_503_fail_closed': 297}.
Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):
postgres-1  | 2026-10-22 19:07:04.293 UTC [37] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.294 UTC [45] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.294 UTC [86] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.295 UTC [38] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.295 UTC [44] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.295 UTC [52] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.297 UTC [7] LOG:  background worker "logical replication launcher" (PID 34) exited with exit code 1
postgres-1  | 2026-10-22 19:07:04.298 UTC [68] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.298 UTC [53] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.299 UTC [56] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.299 UTC [57] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.301 UTC [54] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 19:07:04.303 UTC [29] LOG:  shutting down
postgres-1  | 2026-10-22 19:07:04.305 UTC [29] LOG:  checkpoint starting: shutdown immediate
postgres-1  | 2026-10-22 19:07:04.330 UTC [29] LOG:  checkpoint complete: wrote 530 buffers (3.2%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.010 s, sync=0.012 s, total=0.028 s; sync files=80, longest=0.003 s, average=0.001 s; distance=5099 kB, estimate=5099 kB; lsn=0/4B83C58, redo lsn=0/4B83C58
postgres-1  | 2026-10-22 19:07:04.338 UTC [7] LOG:  database system is shut down
postgres-1  | 
postgres-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
postgres-1  | 
postgres-1  | 2026-10-22 19:07:24.694 UTC [8] LOG:  starting PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
postgres-1  | 2026-10-22 19:07:24.694 UTC [8] LOG:  listening on IPv4 address "0.0.0.0", port 5432
postgres-1  | 2026-10-22 19:07:24.694 UTC [8] LOG:  listening on IPv6 address "::", port 5432
postgres-1  | 2026-10-22 19:07:24.697 UTC [8] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
postgres-1  | 2026-10-22 19:07:24.702 UTC [31] LOG:  database system was shut down at 2026-10-22 19:07:04 UTC
postgres-1  | 2026-10-22 19:07:24.710 UTC [8] LOG:  database system is ready to accept connections

