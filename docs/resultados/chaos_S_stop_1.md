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
- iniciado: 2026-10-22T02:52:41.192863+00:00
- finalizado: 2026-10-22T02:53:14.178708+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=29.5
- fin: 33.0

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 0.11 s
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
- outbox pendiente durante la falla: 40
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- stack_sano_al_terminar: sí
- servicios_sin_reiniciar: sí
- rto_escritura_cumplido: sí
- errores_503_durante_falla: sí
- sin_2xx_durante_falla: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=40, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=0.10533609999765758 s (objetivo 30 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** circuit breaker y health check activo en el gateway.

## Evidencia adicional (Docker health)
TTD (Docker marca no-healthy): 0.05943209999895771 s; healthy de nuevo en t=29.48432469999898 s.
Docker decide `unhealthy` con el healthcheck configurado (interval=5s, timeout=5s, retries=12, start_period=15s): tras `retries` fallos consecutivos lo marca; `restart: unless-stopped` solo reinicia si el proceso sale, no por estar unhealthy.
Health.Log (postgres): [{"Start":"2026-10-22T02:52:28.325543727Z","End":"2026-10-22T02:52:28.416723032Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T02:52:33.416404485Z","End":"2026-10-22T02:52:33.499548217Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T02:52:38.500157445Z","End":"2026-10-22T02:52:38.592002235Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T02:52:43.593111958Z","End":"2026-10-22T02:52:43.686107402Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"},{"Start":"2026-10-22T02:53:10.26323447Z","End":"2026-10-22T02:53:10.350586362Z","ExitCode":0,"Output":"/var/run/postgresql:5432 - accepting connections\n"}]

