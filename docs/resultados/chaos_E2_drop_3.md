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
- iniciado: 2026-10-22T02:52:20.350944+00:00
- finalizado: 2026-10-22T02:52:31.219221+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 10.9

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
creadas=20/20; estados finales={'3c7c8fda-9bee-4061-ac28-a2443e2f0038': 'CONFIRMED', '15f83900-9967-47d3-85f7-4b4e845c93e9': 'CONFIRMED', 'a1985b0e-570a-4b5f-a681-a8d809a4ee5f': 'CONFIRMED', 'f67f7d44-e1ec-4a58-b7e8-5baf6e08964d': 'CONFIRMED', '22a7cf93-fb60-4af7-9e3b-e8cf8c2f3d78': 'CONFIRMED', 'f2d9e534-843b-4d85-98b5-21154d17dc7c': 'CONFIRMED', '318d000e-64ba-4926-b3b4-32732609cd5e': 'CONFIRMED', '5c097e61-2be6-4459-a5b9-a2f56f47e135': 'CONFIRMED', 'ba979a31-3a4b-4a72-a3cb-84e6ef0d458a': 'CONFIRMED', '4a1aa17e-f1eb-4578-88c9-63665199d147': 'CONFIRMED', 'ea4a7675-93fe-4e1b-82c7-4551b5a7188c': 'CONFIRMED', '2a3de712-e3ee-48a9-9792-600703b4a54d': 'CONFIRMED', 'd6b434b1-c6d8-49bb-a4ba-150ef2365fa5': 'CONFIRMED', '05624f31-4341-48c5-8e39-9b0a9c5d9f28': 'CONFIRMED', 'bbbb2a39-15e9-4a37-9733-ae058c03b3dc': 'CONFIRMED', 'ab48791c-8bb5-4fc5-85ac-d82a0cf3231c': 'CONFIRMED', '6d377be7-4ea2-4a06-842c-9bd171728940': 'CONFIRMED', '96252839-297f-4c41-aed1-cb0ca496bc78': 'CONFIRMED', '72c76f40-7aea-4b38-9843-f3809c1104e7': 'CONFIRMED', '5c130ad4-d848-4f74-81c3-b70063fb5423': 'CONFIRMED'}; MANUAL_REVIEW=0; tiempo a CONFIRMED (s): p50=0.027441000001999782 p95=0.027441000001999782 max=0.027441000001999782. Concurrencia limitada a 10 por el limit_conn del gateway (20 concurrentes => ~10 respuestas 503 de nginx); ver docs/resultados/chaos_E2_hallazgo.md.

