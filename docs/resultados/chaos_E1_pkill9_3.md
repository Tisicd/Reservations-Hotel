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
- iniciado: 2026-10-22T18:43:37.838179+00:00
- finalizado: 2026-10-22T18:45:29.405199+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=104.7
- fin: 111.6

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 20.78 s
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
- ack_antes_caida_suficientes: sí
- durabilidad_ack_confirmado: sí
- un_cargo_por_reserva: sí
- sin_manual_review: sí
- stack_sano_al_terminar: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=20.778921200006153 s (objetivo 120 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Semilla=1003; retraso de caida=1.25 s; ack antes de la caida=200 (objetivo >=200); ack durante=25; todos CONFIRMED tras recuperar=True; 1 cargo/reserva=True; MANUAL_REVIEW=0; 2xx durante la ventana=25. RTO a escritura sostenida (3)=20.778921200006153 s desde la caida; healthy de nuevo en t=104.72099600000365 s. Errores por clase: {}.
Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):
postgres-1  | 2026-10-22 18:43:02.575 UTC [7] LOG:  database system is ready to accept connections
postgres-1  | 
postgres-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
postgres-1  | 
postgres-1  | 2026-10-22 18:45:03.156 UTC [7] LOG:  starting PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
postgres-1  | 2026-10-22 18:45:03.156 UTC [7] LOG:  listening on IPv4 address "0.0.0.0", port 5432
postgres-1  | 2026-10-22 18:45:03.156 UTC [7] LOG:  listening on IPv6 address "::", port 5432
postgres-1  | 2026-10-22 18:45:03.162 UTC [7] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
postgres-1  | 2026-10-22 18:45:03.171 UTC [30] LOG:  database system was interrupted; last known up at 2026-10-22 18:43:02 UTC
postgres-1  | 2026-10-22 18:45:03.286 UTC [31] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 18:45:03.360 UTC [32] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 18:45:03.368 UTC [33] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 18:45:03.369 UTC [34] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 18:45:03.373 UTC [35] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 18:45:03.373 UTC [36] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 18:45:03.387 UTC [37] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 18:45:03.403 UTC [38] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 18:45:03.421 UTC [39] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 18:45:03.614 UTC [30] LOG:  database system was not properly shut down; automatic recovery in progress
postgres-1  | 2026-10-22 18:45:03.620 UTC [30] LOG:  redo starts at 0/66D1220
postgres-1  | 2026-10-22 18:45:03.644 UTC [30] LOG:  invalid record length at 0/6E425D8: expected at least 24, got 0
postgres-1  | 2026-10-22 18:45:03.644 UTC [30] LOG:  redo done at 0/6E425B0 system usage: CPU: user: 0.01 s, system: 0.01 s, elapsed: 0.02 s
postgres-1  | 2026-10-22 18:45:03.649 UTC [28] LOG:  checkpoint starting: end-of-recovery immediate wait
postgres-1  | 2026-10-22 18:45:03.673 UTC [28] LOG:  checkpoint complete: wrote 924 buffers (5.6%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.011 s, sync=0.009 s, total=0.026 s; sync files=74, longest=0.002 s, average=0.001 s; distance=7621 kB, estimate=7621 kB; lsn=0/6E425D8, redo lsn=0/6E425D8
postgres-1  | 2026-10-22 18:45:03.680 UTC [7] LOG:  database system is ready to accept connections

