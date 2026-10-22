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
- iniciado: 2026-10-22T18:35:36.335761+00:00
- finalizado: 2026-10-22T18:37:29.507064+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=101.6
- fin: 113.2

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 26.41 s
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
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=26.411236499989172 s (objetivo 120 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Semilla=1002; retraso de caida=1.28 s; ack antes de la caida=200 (objetivo >=200); ack durante=7; todos CONFIRMED tras recuperar=True; 1 cargo/reserva=True; MANUAL_REVIEW=0; 2xx durante la ventana=7. RTO a escritura sostenida (3)=26.411236499989172 s desde la caida; healthy de nuevo en t=101.60853019999922 s. Errores por clase: {'service_503_fail_closed': 286}.
Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):
postgres-1  | 2026-10-22 18:36:51.980 UTC [69] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.980 UTC [51] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.981 UTC [35] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.981 UTC [68] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.982 UTC [73] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.983 UTC [36] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.983 UTC [72] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.983 UTC [54] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.986 UTC [47] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.986 UTC [40] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.987 UTC [58] FATAL:  terminating connection due to administrator command
postgres-1  | 2026-10-22 18:36:51.989 UTC [7] LOG:  background worker "logical replication launcher" (PID 33) exited with exit code 1
postgres-1  | 2026-10-22 18:36:51.991 UTC [28] LOG:  shutting down
postgres-1  | 2026-10-22 18:36:51.993 UTC [28] LOG:  checkpoint starting: shutdown immediate
postgres-1  | 2026-10-22 18:36:52.027 UTC [28] LOG:  checkpoint complete: wrote 676 buffers (4.1%); 0 WAL file(s) added, 0 removed, 1 recycled; write=0.017 s, sync=0.012 s, total=0.037 s; sync files=80, longest=0.002 s, average=0.001 s; distance=5870 kB, estimate=5870 kB; lsn=0/5380FE0, redo lsn=0/5380FE0
postgres-1  | 2026-10-22 18:36:52.035 UTC [7] LOG:  database system is shut down
postgres-1  | 
postgres-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
postgres-1  | 
postgres-1  | 2026-10-22 18:37:12.348 UTC [7] LOG:  starting PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
postgres-1  | 2026-10-22 18:37:12.348 UTC [7] LOG:  listening on IPv4 address "0.0.0.0", port 5432
postgres-1  | 2026-10-22 18:37:12.348 UTC [7] LOG:  listening on IPv6 address "::", port 5432
postgres-1  | 2026-10-22 18:37:12.351 UTC [7] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
postgres-1  | 2026-10-22 18:37:12.357 UTC [30] LOG:  database system was shut down at 2026-10-22 18:36:52 UTC
postgres-1  | 2026-10-22 18:37:12.365 UTC [7] LOG:  database system is ready to accept connections

