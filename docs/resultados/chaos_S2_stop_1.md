# Reporte de caos — escenario S2 (modo stop)

## Parámetros
- escenario: `S2`
- modo: `stop`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T19:49:15.452413+00:00
- finalizado: 2026-10-22T19:50:50.875814+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=94.4
- fin: 95.4

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD (detección): 85.28 s
- RTO medido: 5.96 s
- RTO objetivo: 30 s
- RTO cumplido: **sí**

## Reinicios de contenedores (RestartCount)
| servicio | antes | después |
|---|---|---|
| customer | None | None |
| hotel | None | None |
| availability | None | None |
| payment | None | None |
| reservation | None | None |
| notification | None | None |
| postgres | None | None |
| gateway | None | None |

## Medidas del escenario
- éxito reservas en baseline: 100.0%
- éxito reservas durante la falla: 0.0%
- outbox pendiente durante la falla: 0
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- todos_los_servicios_503: sí
- todos_reconectan_200: sí
- sin_2xx_durante_caida: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** no se restauró automáticamente.
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Healthcheck por servicio (s): {'customer': {'interval': 5.0, 'timeout': 5.0, 'retries': 12, 'start_period': 15.0}, 'hotel': {'interval': 5.0, 'timeout': 5.0, 'retries': 12, 'start_period': 15.0}, 'availability': {'interval': 5.0, 'timeout': 5.0, 'retries': 12, 'start_period': 15.0}, 'payment': {'interval': 5.0, 'timeout': 5.0, 'retries': 12, 'start_period': 15.0}, 'reservation': {'interval': 5.0, 'timeout': 5.0, 'retries': 12, 'start_period': 15.0}, 'notification': {'interval': 5.0, 'timeout': 5.0, 'retries': 12, 'start_period': 15.0}}. Antes (codigos /ready): {'customer': 200, 'hotel': 200, 'availability': 200, 'payment': 200, 'reservation': 200, 'notification': 200}. Primer 503 por servicio (s desde stop postgres): {'customer': 4.75, 'hotel': 4.75, 'availability': 4.75, 'payment': 4.75, 'reservation': 4.75, 'notification': 4.75}. TTD hasta unhealthy por servicio (s): {'customer': 60.78, 'hotel': 60.76, 'availability': 60.79, 'reservation': 63.46, 'notification': 63.77, 'payment': 85.28}. TTD esperado (retries*interval .. retries*(interval+timeout)): {'customer': {'min': 60.0, 'max': 120.0}, 'hotel': {'min': 60.0, 'max': 120.0}, 'availability': {'min': 60.0, 'max': 120.0}, 'payment': {'min': 60.0, 'max': 120.0}, 'reservation': {'min': 60.0, 'max': 120.0}, 'notification': {'min': 60.0, 'max': 120.0}}; en rango: {'customer': True, 'hotel': True, 'availability': True, 'payment': True, 'reservation': True, 'notification': True}. Ultimos codigos durante la caida: {'customer': 503, 'hotel': 503, 'availability': 503, 'payment': 503, 'reservation': 503, 'notification': 503}. Reconexion a 200 tras start (s): {'customer': 5.96, 'hotel': 5.96, 'availability': 5.96, 'payment': 5.96, 'reservation': 5.96, 'notification': 5.96}. Servicios con 503=6/6; servicios unhealthy=6/6; servicios recuperados=6/6; 2xx falsos durante la caida=[]; invariantes=0.

