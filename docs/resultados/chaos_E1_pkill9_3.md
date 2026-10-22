# Reporte de caos — escenario E1 (modo pkill9)

## Parámetros
- escenario: `E1`
- modo: `pkill9`
- repetición: 3
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T14:03:50.886713+00:00
- finalizado: 2026-10-22T14:04:39.491099+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=41.5
- fin: 48.6

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 20.69 s
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
| postgres | 2 | 3 |
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
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=20.68612710000889 s (objetivo 120 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Acknowledged (201 CONFIRMED) antes=8, durante=30; todos CONFIRMED tras recuperar=True; 1 cargo por reserva=True; MANUAL_REVIEW=0.
Timeline cruda: ultima buena antes de la caida=True; RTO a escritura sostenida (3)=20.68612710000889 s desde la caida; healthy de nuevo en t=41.45115110000188 s. 2xx durante la ventana de falla=30. Errores por clase: {'service_503_fail_closed': 4}.
Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):
postgres-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
postgres-1  | 
postgres-1  | 2026-10-22 14:04:12.885 UTC [7] LOG:  starting PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
postgres-1  | 2026-10-22 14:04:12.886 UTC [7] LOG:  listening on IPv4 address "0.0.0.0", port 5432
postgres-1  | 2026-10-22 14:04:12.886 UTC [7] LOG:  listening on IPv6 address "::", port 5432
postgres-1  | 2026-10-22 14:04:13.870 UTC [7] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
postgres-1  | 2026-10-22 14:04:13.876 UTC [30] LOG:  database system was interrupted; last known up at 2026-10-22 14:03:17 UTC
postgres-1  | 2026-10-22 14:04:13.877 UTC [31] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 14:04:13.877 UTC [32] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 14:04:13.878 UTC [33] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 14:04:13.878 UTC [34] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 14:04:14.119 UTC [35] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 14:04:14.211 UTC [36] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 14:04:14.236 UTC [37] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 14:04:14.275 UTC [30] LOG:  database system was not properly shut down; automatic recovery in progress
postgres-1  | 2026-10-22 14:04:14.279 UTC [30] LOG:  redo starts at 0/3933E10
postgres-1  | 2026-10-22 14:04:14.284 UTC [30] LOG:  invalid record length at 0/3A8E868: expected at least 24, got 0
postgres-1  | 2026-10-22 14:04:14.284 UTC [30] LOG:  redo done at 0/3A8E840 system usage: CPU: user: 0.00 s, system: 0.00 s, elapsed: 0.00 s
postgres-1  | 2026-10-22 14:04:14.287 UTC [38] FATAL:  the database system is not yet accepting connections
postgres-1  | 2026-10-22 14:04:14.287 UTC [38] DETAIL:  Consistent recovery state has not been yet reached.
postgres-1  | 2026-10-22 14:04:14.304 UTC [39] FATAL:  the database system is not yet accepting connections
postgres-1  | 2026-10-22 14:04:14.304 UTC [39] DETAIL:  Consistent recovery state has not been yet reached.
postgres-1  | 2026-10-22 14:04:14.328 UTC [28] LOG:  checkpoint starting: end-of-recovery immediate wait
postgres-1  | 2026-10-22 14:04:14.351 UTC [28] LOG:  checkpoint complete: wrote 192 buffers (1.2%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.005 s, sync=0.007 s, total=0.032 s; sync files=50, longest=0.002 s, average=0.001 s; distance=1386 kB, estimate=1386 kB; lsn=0/3A8E868, redo lsn=0/3A8E868
postgres-1  | 2026-10-22 14:04:14.355 UTC [7] LOG:  database system is ready to accept connections

