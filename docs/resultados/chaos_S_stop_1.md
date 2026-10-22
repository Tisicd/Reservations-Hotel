# Reporte de caos — escenario S (modo stop)

## Parámetros
- escenario: `S`
- modo: `stop`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T19:44:58.209826+00:00
- finalizado: 2026-10-22T19:46:45.888187+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=103.0
- fin: 107.7

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD (detección): 93.21 s
- RTO medido: 93.21 s
- RTO objetivo: 30 s
- RTO cumplido: **no**

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
- stack_sano_al_terminar: sí
- sin_2xx_durante_falla: sí
- ttd_observado: sí
- rto_vuelta_healthy_cumplido: no

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=93.21044278144836 s (objetivo 30 s, cumplido=no).
5. **¿Qué mecanismo mejoraría la resiliencia?** circuit breaker y health check activo en el gateway.

## Evidencia adicional (Docker health)
Timeline cruda: ultima buena antes de la caida=si; primer error a 8.00963739999861 s; primer unhealthy (docker events) a 93.21044278144836 s; recovery tras SIGCONT=3.4294284999923548 s; downtime total=96.63987128144072 s. Primer write sostenido (3) a 98.79854109999724 s.
Se congelan los procesos `postgres` con SIGSTOP (no `docker stop`): un contenedor detenido no ejecuta healthchecks y no emite `health_status`; con SIGSTOP el healthcheck sigue ejecutandose y falla, por lo que Docker aplica `retries`. Healthcheck de postgres: interval=5s timeout=5s retries=12 start_period=15s; TTD esperado ~ retries x (interval + duracion del check) = 12 x (5 + ~3) = ~96 s (rango 60-120 s). Objetivo de 30 s: NO cumplido; el compromiso retries=12 evita falsos unhealthy a cambio de ~96 s de deteccion.
Errores durante la caida: {'timeout': 7, 'service_503_fail_closed': 14}; 2xx=0.
Health.Log (postgres): [{"Start":"2026-10-22T19:46:16.417755873Z","End":"2026-10-22T19:46:19.494920924Z","ExitCode":2,"Output":"/var/run/postgresql:5432 - no response\n"},{"Start":"2026-10-22T19:46:24.495609481Z","End":"2026-10-22T19:46:27.58102073Z","ExitCode":2,"Output":"/var/run/postgresql:5432 - no response\n"},{"Start":"2026-10-22T19:46:32.581816193Z","End":"2026-10-22T19:46:35.663857336Z","ExitCode":2,"Output":"/var/run/postgresql:5432 - no response\n"},{"Start":"2026-10-22T19:46:40.664985121Z","End":"2026-10-22T19:46:40.753025734Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T19:46:45.753651602Z","End":"2026-10-22T19:46:45.846867612Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"}]

