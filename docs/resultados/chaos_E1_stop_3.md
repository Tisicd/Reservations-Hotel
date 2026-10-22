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
- iniciado: 2026-10-22T18:37:36.914157+00:00
- finalizado: 2026-10-22T18:39:28.157216+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=105.3
- fin: 111.2

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 26.37 s
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
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=26.36820810000063 s (objetivo 120 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Semilla=1003; retraso de caida=1.25 s; ack antes de la caida=200 (objetivo >=200); ack durante=15; todos CONFIRMED tras recuperar=True; 1 cargo/reserva=True; MANUAL_REVIEW=0; 2xx durante la ventana=15. RTO a escritura sostenida (3)=26.36820810000063 s desde la caida; healthy de nuevo en t=105.29755670001032 s. Errores por clase: {'service_503_fail_closed': 293}.
Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):
postgres-1  | 2026-10-22 18:38:56.282 UTC [61] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.282 UTC [59] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.282 UTC [55] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.284 UTC [54] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.284 UTC [35] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.284 UTC [51] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.285 UTC [52] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.286 UTC [7] LOG:  background worker "logical replication launcher" (PID 33) exited with exit code 1
postgres-1  | 2026-10-22 18:38:56.286 UTC [38] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.287 UTC [41] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.287 UTC [44] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.288 UTC [50] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:38:56.292 UTC [28] LOG:  shutting down
postgres-1  | 2026-10-22 18:38:56.294 UTC [28] LOG:  checkpoint starting: shutdown immediate
postgres-1  | 2026-10-22 18:38:56.325 UTC [28] LOG:  checkpoint complete: wrote 731 buffers (4.5%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.016 s, sync=0.011 s, total=0.033 s; sync files=77, longest=0.003 s, average=0.001 s; distance=6054 kB, estimate=6054 kB; lsn=0/596A988, redo lsn=0/596A988
postgres-1  | 2026-10-22 18:38:56.333 UTC [7] LOG:  database system is shut down
postgres-1  | 
postgres-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
postgres-1  | 
postgres-1  | 2026-10-22 18:39:16.641 UTC [7] LOG:  starting PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
postgres-1  | 2026-10-22 18:39:16.641 UTC [7] LOG:  listening on IPv4 address "0.0.0.0", port 5432
postgres-1  | 2026-10-22 18:39:16.641 UTC [7] LOG:  listening on IPv6 address "::", port 5432
postgres-1  | 2026-10-22 18:39:16.644 UTC [7] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
postgres-1  | 2026-10-22 18:39:16.649 UTC [30] LOG:  database system was shut down at 2026-10-22 18:38:56 UTC
postgres-1  | 2026-10-22 18:39:16.657 UTC [7] LOG:  database system is ready to accept connections

