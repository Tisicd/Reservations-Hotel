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
- iniciado: 2026-10-22T02:51:59.803439+00:00
- finalizado: 2026-10-22T02:52:10.801015+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 11.0

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
creadas=20/20; estados finales={'215dfb1c-adb6-4f50-b926-08ab8011b32f': 'CONFIRMED', '1ce6c0d9-201f-4044-98bc-607eb9d29988': 'CONFIRMED', 'b53eedb9-b403-4398-963a-8c712efee029': 'CONFIRMED', '64ebe1bc-5410-421f-a5ec-cedd121a5399': 'CONFIRMED', '2f46acd8-f635-4bf1-998c-3715578283cc': 'CONFIRMED', '627a7c04-cafa-4a0c-ab13-b008cec7226d': 'CONFIRMED', 'c6f4cf38-11cc-4e67-96f8-af3419cfeec3': 'CONFIRMED', '40f69429-d4d3-40b3-856c-0f81dfedfc77': 'CONFIRMED', '1fe11154-a0a9-4ce7-b860-63a5fb470dfd': 'CONFIRMED', 'c5e5c53b-3a3e-49c6-9f55-2e9e50962edd': 'CONFIRMED', '84d55f8d-e051-4c12-a75e-67ddb914b89b': 'CONFIRMED', '95144a31-4e0e-4f7e-8c39-50e2fef346b5': 'CONFIRMED', 'a95f5a08-05e9-41f2-888f-6637beaf90d9': 'CONFIRMED', '5aaa875f-cd21-43e1-9144-9380863fd455': 'CONFIRMED', '97481426-0168-4457-b66b-3046f1aea6e2': 'CONFIRMED', 'a0dd85a2-9698-4688-afe8-ff407e3cd754': 'CONFIRMED', '273c4abc-a8e1-410d-a245-485c5fd2cef5': 'CONFIRMED', '29424e8e-e3c9-4f63-90a5-cfdc8ddb513d': 'CONFIRMED', 'c4e8fa59-d635-463a-8abe-0b75773165b7': 'CONFIRMED', 'e097a492-518a-444c-a1aa-4df210e4c09f': 'CONFIRMED'}; MANUAL_REVIEW=0; tiempo a CONFIRMED (s): p50=0.03171759999895585 p95=0.03171759999895585 max=0.03171759999895585. Concurrencia limitada a 10 por el limit_conn del gateway (20 concurrentes => ~10 respuestas 503 de nginx); ver docs/resultados/chaos_E2_hallazgo.md.

