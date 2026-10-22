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
- iniciado: 2026-10-22T13:40:35.244316+00:00
- finalizado: 2026-10-22T13:41:00.926149+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=19.3
- fin: 25.7

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD (detección): 8.08 s
- RTO medido: 13.28 s
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
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=13.28420639038086 s (objetivo 30 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** circuit breaker y health check activo en el gateway.

## Evidencia adicional (Docker health)
Timeline cruda: ultima buena antes de la caida=si; primer error a 8.01110200000403 s; primer unhealthy (docker events) a 8.08486557006836 s; primer healthy de nuevo a 13.28420639038086 s (desde el pause). Primer write sostenido (3) a 13.971550400005071 s.
Se usa `docker pause` (no `stop`) porque un contenedor detenido no emite `health_status: unhealthy`: se verifico que `docker stop` deja `State.Health.Status=unhealthy` sin evento y detiene los healthchecks. Con pause el healthcheck falla y Docker emite la transicion.
Errores durante la caida: {'timeout': 1}; 2xx=0.
Health.Log (postgres): [{"Start":"2026-10-22T13:40:27.305857856Z","End":"2026-10-22T13:40:27.384873044Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T13:40:32.38574105Z","End":"2026-10-22T13:40:32.479402521Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T13:40:37.479562252Z","End":"2026-10-22T13:40:37.607359575Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T13:40:53.91460655Z","End":"2026-10-22T13:40:54.028984318Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T13:40:59.030277664Z","End":"2026-10-22T13:40:59.150800845Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"}]

