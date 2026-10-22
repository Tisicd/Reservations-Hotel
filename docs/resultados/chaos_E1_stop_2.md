# Reporte de caos — escenario E1 (modo stop)

## Parámetros
- escenario: `E1`
- modo: `stop`
- repetición: 2
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T14:00:09.119557+00:00
- finalizado: 2026-10-22T14:00:59.922773+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=44.1
- fin: 50.8

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 26.36 s
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
- durabilidad_ack_confirmado: sí
- un_cargo_por_reserva: sí
- sin_manual_review: sí
- stack_sano_al_terminar: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=26.35797040000034 s (objetivo 120 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Acknowledged (201 CONFIRMED) antes=14, durante=0; todos CONFIRMED tras recuperar=True; 1 cargo por reserva=True; MANUAL_REVIEW=0.
Timeline cruda: ultima buena antes de la caida=True; RTO a escritura sostenida (3)=26.35797040000034 s desde la caida; healthy de nuevo en t=44.14430120000907 s. 2xx durante la ventana de falla=0. Errores por clase: {'service_503_fail_closed': 47}.
Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):
postgres-1  | 2026-10-22 14:00:27.446 UTC [43] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.446 UTC [37] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.446 UTC [45] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.449 UTC [41] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.449 UTC [42] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.449 UTC [40] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.449 UTC [38] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.449 UTC [39] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.449 UTC [36] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.449 UTC [34] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.450 UTC [35] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:00:27.453 UTC [7] LOG:  background worker "logical replication launcher" (PID 33) exited with exit code 1
postgres-1  | 2026-10-22 14:00:27.455 UTC [28] LOG:  shutting down
postgres-1  | 2026-10-22 14:00:27.457 UTC [28] LOG:  checkpoint starting: shutdown immediate
postgres-1  | 2026-10-22 14:00:27.520 UTC [28] LOG:  checkpoint complete: wrote 123 buffers (0.8%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.021 s, sync=0.011 s, total=0.065 s; sync files=59, longest=0.002 s, average=0.001 s; distance=840 kB, estimate=840 kB; lsn=0/35E1F78, redo lsn=0/35E1F78
postgres-1  | 2026-10-22 14:00:27.526 UTC [7] LOG:  database system is shut down
postgres-1  | 
postgres-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
postgres-1  | 
postgres-1  | 2026-10-22 14:00:47.626 UTC [7] LOG:  starting PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
postgres-1  | 2026-10-22 14:00:47.626 UTC [7] LOG:  listening on IPv4 address "0.0.0.0", port 5432
postgres-1  | 2026-10-22 14:00:47.626 UTC [7] LOG:  listening on IPv6 address "::", port 5432
postgres-1  | 2026-10-22 14:00:47.632 UTC [7] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
postgres-1  | 2026-10-22 14:00:47.641 UTC [30] LOG:  database system was shut down at 2026-10-22 14:00:27 UTC
postgres-1  | 2026-10-22 14:00:47.649 UTC [7] LOG:  database system is ready to accept connections

