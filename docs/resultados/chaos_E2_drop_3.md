# Reporte de caos — escenario E2 (modo drop)

## Parámetros
- escenario: `E2`
- modo: `drop`
- repetición: 3
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T18:27:21.458823+00:00
- finalizado: 2026-10-22T18:27:31.140085+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 9.7

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
creadas=20/20; estados finales={'58adaadd-91ee-4860-84df-26f2fbe3e821': 'CONFIRMED', 'c4623834-8d10-4805-a589-2b372e54d63c': 'CONFIRMED', '9fb5717e-e3b3-4acc-9619-b059752118ba': 'CONFIRMED', '10405171-d942-4b3b-aa71-e614eb4fe6a8': 'CONFIRMED', '47350fe7-acb7-4c8a-9b79-8da95463a816': 'CONFIRMED', 'de995c35-f12c-46c1-af93-440be0d97230': 'CONFIRMED', '92bcc4b4-7177-4fac-bcb2-477445924a52': 'CONFIRMED', '5e45b95d-1693-48cc-908e-f37dd321cf93': 'CONFIRMED', 'b48ff5e9-95b7-4c0b-80f3-977ec7d61d77': 'CONFIRMED', 'ec89b8e9-3eb4-484c-b5d4-7e70c59417c7': 'CONFIRMED', 'acb77f07-7838-490c-8ee8-92f395805cd4': 'CONFIRMED', '73f81079-834b-400a-bf94-89c68e757c4e': 'CONFIRMED', '3ea1b16a-23a7-413c-9825-a42c35cbe6e6': 'CONFIRMED', '93c4af71-c07f-4b96-874f-a27315b0239d': 'CONFIRMED', '840f7cec-35aa-4a1e-9a70-c13c65fe0a54': 'CONFIRMED', '8f9bab3e-359f-4cb3-869c-55067d6fca54': 'CONFIRMED', '5d9a49ca-2bbf-480a-b7ae-b2b34d637b0d': 'CONFIRMED', 'a65b0375-cafe-485a-b918-8b68151237cd': 'CONFIRMED', 'a3af56b8-4aca-4aa8-a063-487030b5bd8b': 'CONFIRMED', '58ee04ed-f8a6-4c6a-a01c-b3f6f9661479': 'CONFIRMED'}; MANUAL_REVIEW=0; tiempo a estado final por reserva (API sincrona) ms: p50=722.1 p95=960.9 max=979.9. Concurrencia limitada a 10 por el limit_conn del gateway (20 concurrentes => ~10 respuestas 429 de nginx); ver docs/resultados/chaos_E2_hallazgo.md.

