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
- iniciado: 2026-10-22T02:51:39.753493+00:00
- finalizado: 2026-10-22T02:51:50.528890+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 10.8

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
creadas=20/20; estados finales={'f7e3c495-1a8d-4290-81b5-b2e6ad6d9075': 'CONFIRMED', 'd03ccfdd-7cff-47f4-b18c-4ae950f6def7': 'CONFIRMED', '43e27781-1280-4968-9487-a0136eba24b7': 'CONFIRMED', '911aff82-fed1-42b8-83ce-671c9df2fbdc': 'CONFIRMED', 'e2d7349e-20e9-4067-9f76-1f500fde85a5': 'CONFIRMED', '0c0d548d-83e8-4d42-8211-2499db445869': 'CONFIRMED', '3715e2a3-b082-42a6-a02e-0ac92d9befc4': 'CONFIRMED', '5beca821-7bd9-4bbb-bc16-d17970c1fa35': 'CONFIRMED', '0d8e3198-61f6-4362-869c-d7958cee47a9': 'CONFIRMED', '5ca51119-65b8-431d-ae19-f5459741e4f0': 'CONFIRMED', '2da9db66-77dc-4122-b018-d992dc8e9be3': 'CONFIRMED', 'ae5a33f2-7f93-4d3d-8b84-a7b5e35acefe': 'CONFIRMED', '472f381a-53e0-426e-87c5-8413da6947fb': 'CONFIRMED', 'ba263def-9ec3-4e8a-b0dd-b3694c922a64': 'CONFIRMED', '7a461c60-96f9-4e79-9e0c-aed4af19ca4e': 'CONFIRMED', 'cf43b29a-0ce9-4f31-b658-bebe424980c2': 'CONFIRMED', 'b4aefcaf-280b-4368-a26b-0c9aac174df2': 'CONFIRMED', 'da1930bc-521b-4397-ad92-242c2127fde0': 'CONFIRMED', 'f0665b03-8d1e-4e8c-a3be-37bd1e37f2b6': 'CONFIRMED', '77c5803a-20d2-497f-b45b-6724247448d3': 'CONFIRMED'}; MANUAL_REVIEW=0; tiempo a CONFIRMED (s): p50=0.03889600000184146 p95=0.03889600000184146 max=0.03889600000184146. Concurrencia limitada a 10 por el limit_conn del gateway (20 concurrentes => ~10 respuestas 503 de nginx); ver docs/resultados/chaos_E2_hallazgo.md.

