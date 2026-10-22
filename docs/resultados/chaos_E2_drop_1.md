# Reporte de caos — escenario E2 (modo drop)

## Parámetros
- escenario: `E2`
- modo: `drop`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T14:08:41.886533+00:00
- finalizado: 2026-10-22T14:08:52.600215+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 10.7

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: no alcanzado
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
- éxito reservas durante la falla: 100.0%
- outbox pendiente durante la falla: 0
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- stack_sano_al_terminar: sí
- todas_las_reservas_estables: sí
- un_cargo_por_reserva: sí
- sin_manual_review: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=n/d s (objetivo 30 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** conciliación contra extractos del proveedor real y webhooks.

## Evidencia adicional (Docker health)
creadas=20/20; estados finales={'07e864d6-f6da-4230-b85a-552e6a840788': 'CONFIRMED', '679082a5-17b2-498e-a35c-cec0135ac0ea': 'CONFIRMED', '820dfc9d-9cd3-4b85-b6e4-165247076b01': 'CONFIRMED', '0352eeff-3858-46a7-9313-0e0be626f763': 'CONFIRMED', '7427fa43-5848-4f75-9cb7-54ab044ffc11': 'CONFIRMED', 'f6bad128-abe5-45ae-90d8-98c5369ead4f': 'CONFIRMED', 'b8aa5d0f-9a1b-47f7-bb6d-0fc8286a12f0': 'CONFIRMED', 'a5510bc2-dacd-4f3a-9dff-b8396688a4ad': 'CONFIRMED', '4335438b-eb6c-4900-a105-0a026e5d44a8': 'CONFIRMED', '10032364-8c15-4426-8818-8e319264c980': 'CONFIRMED', '0f083d7e-cd06-4dc9-a9f8-e8c6ab88d9ab': 'CONFIRMED', 'ffd036ec-3e32-4aba-98f4-d21a158b0b2c': 'CONFIRMED', '16b7d1b4-8029-4776-8f5c-7cd0bb8d28c9': 'CONFIRMED', '223a52f1-d947-44a4-90e6-2027f7a7908e': 'CONFIRMED', 'fbb54654-9b0f-4704-95b7-400afe7e702d': 'CONFIRMED', '5f18b10e-bbad-4cba-b922-fd4956883945': 'CONFIRMED', 'aa204a0f-0b3f-4c93-af94-c294a493bf89': 'CONFIRMED', 'b705c3e5-594e-4d45-aef8-b3234e8abf95': 'CONFIRMED', '82cadefb-c828-4ea5-bce0-fbb932a3d44b': 'CONFIRMED', '54a07e0d-5422-4724-95de-242d4cb9551b': 'CONFIRMED'}; MANUAL_REVIEW=0; tiempo a estado final por reserva (API sincrona) ms: p50=770.1 p95=1047.9 max=1061.7. Concurrencia limitada a 10 por el limit_conn del gateway (20 concurrentes => ~10 respuestas 503 de nginx); ver docs/resultados/chaos_E2_hallazgo.md.

