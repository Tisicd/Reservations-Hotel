# Reporte de caos — escenario E2 (modo drop)

## Parámetros
- escenario: `E2`
- modo: `drop`
- repetición: 2
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T18:27:02.455769+00:00
- finalizado: 2026-10-22T18:27:12.319989+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 9.9

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
creadas=20/20; estados finales={'403d9f09-addc-4c2d-a289-436cfe26b635': 'CONFIRMED', 'e4159bed-2cc4-43b6-ae42-0da2fc89ec0f': 'CONFIRMED', '46222edd-b8d2-45a9-8bfa-12c45b013662': 'CONFIRMED', '43fa6b70-1da9-47fc-a5d7-f3ad6e20dc9c': 'CONFIRMED', '0ac59dbe-0ad1-4559-a475-ecc176c77ff3': 'CONFIRMED', '45a8269c-993b-4c4d-8c0e-97b28bb2293a': 'CONFIRMED', '177f920b-db74-4785-b020-3bc024a6dbfc': 'CONFIRMED', '2cfd2a95-ec37-40c5-857b-df2116be3479': 'CONFIRMED', '01260d47-ab98-4a5a-b19c-30a82cfb92af': 'CONFIRMED', 'b1eaf0f2-7072-4f30-abaf-568d2e436a65': 'CONFIRMED', 'cf53688d-bc21-4605-8ba5-e385f4d8f265': 'CONFIRMED', 'bee6dcac-94ae-4884-8720-3dbcc50fb82b': 'CONFIRMED', 'b1821695-d924-43f4-8d24-9fac5d04ccf6': 'CONFIRMED', '53aa5b06-b5ce-42ee-803d-2854d3633d18': 'CONFIRMED', '827e73b8-3660-4205-8404-6e649c66f4e2': 'CONFIRMED', '71f1e5a5-32f8-4ee3-b289-ded5ebc20941': 'CONFIRMED', 'd2fbeae1-7c9f-4095-8fa1-94a3427b40fb': 'CONFIRMED', '7071de83-ae17-4abb-9d6e-1ce7b7896e82': 'CONFIRMED', 'e49a197b-97df-4c11-bb73-1725618dc448': 'CONFIRMED', '5646dcd1-b6f7-4dde-89f4-412ad646d41f': 'CONFIRMED'}; MANUAL_REVIEW=0; tiempo a estado final por reserva (API sincrona) ms: p50=736.6 p95=986.0 max=1005.3. Concurrencia limitada a 10 por el limit_conn del gateway (20 concurrentes => ~10 respuestas 429 de nginx); ver docs/resultados/chaos_E2_hallazgo.md.

