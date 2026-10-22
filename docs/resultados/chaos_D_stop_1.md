# Reporte de caos — escenario D (modo stop)

## Parámetros
- escenario: `D`
- modo: `stop`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T19:04:59.451763+00:00
- finalizado: 2026-10-22T19:05:12.746669+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=10.3
- fin: 13.3

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 2.18 s
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
| postgres | 1 | 0 |
| gateway | 0 | 0 |

## Medidas del escenario
- éxito reservas en baseline: 100.0%
- éxito reservas durante la falla: 0.0%
- outbox pendiente durante la falla: 0
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- stack_sano_al_terminar: sí
- servicios_app_sin_reiniciar: sí
- rto_escritura_sostenida_cumplido: sí
- errores_503_durante_falla: no
- filas_conservadas: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=2.183647600002587 s (objetivo 120 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** réplica de PostgreSQL con failover automático y PITR.

## Evidencia adicional (Docker health)
Timeline cruda: ultima buena antes de la caida=si; primer write sostenido (3) a 2.183647600002587 s desde la eliminacion; healthy de nuevo en t=10.294365800000378 s. Causa del fallo: recreacion real (rm -sf + up -d --no-build), volumen persistente. Errores durante la ventana: {}.
Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):
postgres-1  | 
postgres-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
postgres-1  | 
postgres-1  | 2026-10-22 19:05:04.467 UTC [7] LOG:  starting PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
postgres-1  | 2026-10-22 19:05:04.468 UTC [7] LOG:  listening on IPv4 address "0.0.0.0", port 5432
postgres-1  | 2026-10-22 19:05:04.468 UTC [7] LOG:  listening on IPv6 address "::", port 5432
postgres-1  | 2026-10-22 19:05:04.472 UTC [7] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
postgres-1  | 2026-10-22 19:05:04.479 UTC [31] LOG:  database system was shut down at 2026-10-22 19:05:03 UTC
postgres-1  | 2026-10-22 19:05:04.487 UTC [7] LOG:  database system is ready to accept connections

