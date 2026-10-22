# Reporte de caos — escenario E4 (modo restart)

## Parámetros
- escenario: `E4`
- modo: `restart`
- repetición: 2
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T18:09:10.434522+00:00
- finalizado: 2026-10-22T18:09:21.788021+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 11.4

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 6.55 s
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
- servicios_app_sin_reiniciar: sí
- todos_ready: sí
- rto_reconexion_cumplido: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** no se restauró automáticamente.
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Reinicio ordenado de postgres (docker compose restart). Reconexion por servicio (s desde el restart): {'customer': 6.53, 'hotel': 6.53, 'availability': 6.54, 'payment': 6.54, 'reservation': 6.55, 'notification': 6.55}. Servicios de aplicacion sin reiniciar=True (RestartCount antes={'customer': 0, 'hotel': 0, 'availability': 0, 'payment': 0, 'reservation': 0, 'notification': 0, 'postgres': 0, 'gateway': 0}, despues={'customer': 0, 'hotel': 0, 'availability': 0, 'payment': 0, 'reservation': 0, 'notification': 0, 'postgres': 0, 'gateway': 0}). healthy postgres=True; invariantes=0.

