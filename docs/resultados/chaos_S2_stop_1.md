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
- iniciado: 2026-10-22T19:16:52.440039+00:00
- finalizado: 2026-10-22T19:17:05.151518+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 12.7

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 5.89 s
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
Antes (codigos /ready): {'customer': 200, 'hotel': 200, 'availability': 200, 'payment': 200, 'reservation': 200, 'notification': 200}. Primer 503 por servicio (s desde stop postgres): {'customer': 4.78, 'hotel': 4.78, 'availability': 4.78, 'payment': 4.78, 'reservation': 4.78, 'notification': 4.78}. Ultimos codigos durante la caida: {'customer': 503, 'hotel': 503, 'availability': 503, 'payment': 503, 'reservation': 503, 'notification': 503}. Reconexion a 200 tras start (s): {'customer': 5.89, 'hotel': 5.89, 'availability': 5.89, 'payment': 5.89, 'reservation': 5.89, 'notification': 5.89}. Servicios con 503=6/6; servicios recuperados=6/6; 2xx falsos durante la caida=[]; invariantes=0.

