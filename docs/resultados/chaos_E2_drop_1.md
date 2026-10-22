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
- iniciado: 2026-10-22T18:26:42.929092+00:00
- finalizado: 2026-10-22T18:26:53.335499+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 10.4

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
creadas=20/20; estados finales={'fc2ee089-b24a-48e5-9eac-69682261cafe': 'CONFIRMED', 'f9c769d1-2d9b-4f62-b991-05d60ad7fbc5': 'CONFIRMED', '82f43f72-718c-48ba-9f00-259b0a01363f': 'CONFIRMED', 'e6910a99-460f-4f02-9f9a-d10f73eeca09': 'CONFIRMED', 'ef07dd66-06a8-467b-90bc-f8e0efbee60e': 'CONFIRMED', '9c931155-b682-401f-ae61-fb0d2ea1a482': 'CONFIRMED', '86e68fdb-d802-422c-b334-71f0c0c371eb': 'CONFIRMED', '2190ff42-8edd-4bf3-938c-6c663ee2bd32': 'CONFIRMED', '7fed7a53-3390-470c-b84c-c2fee5a029b1': 'CONFIRMED', '5a2536ae-7d55-4d15-8647-3b2f38673579': 'CONFIRMED', '8b2995ba-640b-4e49-976f-4019ae1d5d9e': 'CONFIRMED', 'c789d733-0b3d-43c9-8c1a-a36db13d45de': 'CONFIRMED', '85e43fef-b9ee-42f3-b071-225ef82f5ace': 'CONFIRMED', '5081303f-5aa8-4414-9deb-0a44b7afba57': 'CONFIRMED', '2c55ca0b-4d36-437f-a481-220ff782287c': 'CONFIRMED', '89204dd5-25f4-4957-bb3e-26c60e6dcec4': 'CONFIRMED', '0f1795f1-e186-412e-bddc-e8fe756c44ae': 'CONFIRMED', 'c3bd9a79-ee88-4bb5-a53c-a72accb59646': 'CONFIRMED', '6c34b696-41d3-4172-a9d7-b154487a8508': 'CONFIRMED', '4967f6f4-37df-44e4-9a64-8f69d1e3d97a': 'CONFIRMED'}; MANUAL_REVIEW=0; tiempo a estado final por reserva (API sincrona) ms: p50=705.3 p95=890.0 max=913.9. Concurrencia limitada a 10 por el limit_conn del gateway (20 concurrentes => ~10 respuestas 429 de nginx); ver docs/resultados/chaos_E2_hallazgo.md.

