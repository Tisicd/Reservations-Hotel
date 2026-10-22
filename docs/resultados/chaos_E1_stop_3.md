# Reporte de caos — escenario E1 (modo stop)

## Parámetros
- escenario: `E1`
- modo: `stop`
- repetición: 3
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T14:01:06.917595+00:00
- finalizado: 2026-10-22T14:01:57.336147+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=44.0
- fin: 50.4

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 26.11 s
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
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=26.11251830001129 s (objetivo 120 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Acknowledged (201 CONFIRMED) antes=9, durante=0; todos CONFIRMED tras recuperar=True; 1 cargo por reserva=True; MANUAL_REVIEW=0.
Timeline cruda: ultima buena antes de la caida=True; RTO a escritura sostenida (3)=26.11251830001129 s desde la caida; healthy de nuevo en t=43.98825399999623 s. 2xx durante la ventana de falla=0. Errores por clase: {'service_503_fail_closed': 47}.
Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):
postgres-1  | 2026-10-22 14:01:25.350 UTC [7] LOG:  background worker "logical replication launcher" (PID 33) exited with exit code 1
postgres-1  | 2026-10-22 14:01:25.350 UTC [45] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.350 UTC [57] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.350 UTC [35] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.350 UTC [37] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.351 UTC [34] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.353 UTC [40] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.353 UTC [56] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.356 UTC [41] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.358 UTC [44] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.358 UTC [42] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.359 UTC [43] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 14:01:25.361 UTC [28] LOG:  shutting down
postgres-1  | 2026-10-22 14:01:25.366 UTC [28] LOG:  checkpoint starting: shutdown immediate
postgres-1  | 2026-10-22 14:01:25.416 UTC [28] LOG:  checkpoint complete: wrote 164 buffers (1.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.019 s, sync=0.025 s, total=0.055 s; sync files=72, longest=0.009 s, average=0.001 s; distance=1102 kB, estimate=1102 kB; lsn=0/36F5A30, redo lsn=0/36F5A30
postgres-1  | 2026-10-22 14:01:25.425 UTC [7] LOG:  database system is shut down
postgres-1  | 
postgres-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
postgres-1  | 
postgres-1  | 2026-10-22 14:01:45.371 UTC [7] LOG:  starting PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
postgres-1  | 2026-10-22 14:01:45.371 UTC [7] LOG:  listening on IPv4 address "0.0.0.0", port 5432
postgres-1  | 2026-10-22 14:01:45.371 UTC [7] LOG:  listening on IPv6 address "::", port 5432
postgres-1  | 2026-10-22 14:01:45.374 UTC [7] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
postgres-1  | 2026-10-22 14:01:45.379 UTC [31] LOG:  database system was shut down at 2026-10-22 14:01:25 UTC
postgres-1  | 2026-10-22 14:01:45.387 UTC [7] LOG:  database system is ready to accept connections

