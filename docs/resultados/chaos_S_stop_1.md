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
- iniciado: 2026-10-22T19:14:45.614670+00:00
- finalizado: 2026-10-22T19:16:36.192653+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=106.2
- fin: 110.6

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD (detección): 96.62 s
- RTO medido: 4.57 s
- RTO objetivo: 30 s
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
- stack_sano_al_terminar: sí
- sin_2xx_durante_falla: sí
- ttd_observado: sí
- rto_vuelta_healthy_cumplido: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=4.57307729999593 s (objetivo 30 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** circuit breaker y health check activo en el gateway.

## Evidencia adicional (Docker health)
Timeline cruda: ultima buena antes de la caida=si; primer error a 8.004103300001589 s; primer unhealthy (docker events) a 96.62219047546387 s; recovery tras SIGCONT=4.57307729999593 s; downtime total=101.1952677754598 s. Primer write sostenido (3) a 102.61266610000166 s.
Se congelan los procesos `postgres` con SIGSTOP (no `docker stop`): un contenedor detenido no ejecuta healthchecks y no emite `health_status`; con SIGSTOP el healthcheck sigue ejecutandose y falla, por lo que Docker aplica `retries`. Healthcheck de postgres: interval=5s timeout=5s retries=12 start_period=15s; TTD esperado ~ retries x interval = 60 s.
Errores durante la caida: {'timeout': 7, 'service_503_fail_closed': 15}; 2xx=0.
Health.Log (postgres): [{"Start":"2026-10-22T19:16:06.631813172Z","End":"2026-10-22T19:16:09.713412044Z","ExitCode":2,"Output":"/var/run/postgresql:5432 - no response\n"},{"Start":"2026-10-22T19:16:14.714602293Z","End":"2026-10-22T19:16:17.80631128Z","ExitCode":2,"Output":"/var/run/postgresql:5432 - no response\n"},{"Start":"2026-10-22T19:16:22.807375542Z","End":"2026-10-22T19:16:25.896011786Z","ExitCode":2,"Output":"/var/run/postgresql:5432 - no response\n"},{"Start":"2026-10-22T19:16:30.896827371Z","End":"2026-10-22T19:16:30.979079269Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T19:16:35.979230089Z","End":"2026-10-22T19:16:36.061778925Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"}]

