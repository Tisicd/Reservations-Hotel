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
- iniciado: 2026-10-22T13:39:38.788116+00:00
- finalizado: 2026-10-22T13:40:11.310182+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=28.3
- fin: 32.5

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 6.48 s
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
- éxito reservas en baseline: 0.0%
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
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=6.475031099995249 s (objetivo 120 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** réplica de PostgreSQL con failover automático y PITR.

## Evidencia adicional (Docker health)
Timeline cruda: ultima buena antes de la caida=no; primer write sostenido (3) a 6.475031099995249 s desde la eliminacion; healthy de nuevo en t=28.337095599999884 s. Causa del fallo: recreacion real (rm -sf + up -d --no-build), volumen persistente. Errores durante la ventana: {}.
Ultimas lineas del log de PostgreSQL (incluye recuperacion WAL):
postgres-1  | 
postgres-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
postgres-1  | 
postgres-1  | 2026-10-22 13:40:01.957 UTC [7] LOG:  starting PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
postgres-1  | 2026-10-22 13:40:01.958 UTC [7] LOG:  listening on IPv4 address "0.0.0.0", port 5432
postgres-1  | 2026-10-22 13:40:01.958 UTC [7] LOG:  listening on IPv6 address "::", port 5432
postgres-1  | 2026-10-22 13:40:01.972 UTC [7] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
postgres-1  | 2026-10-22 13:40:01.984 UTC [31] LOG:  database system was shut down at 2026-10-22 13:39:57 UTC
postgres-1  | 2026-10-22 13:40:01.984 UTC [32] FATAL:  the database system is starting up
postgres-1  | 2026-10-22 13:40:02.007 UTC [7] LOG:  database system is ready to accept connections

