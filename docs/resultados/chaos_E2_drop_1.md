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
- iniciado: 2026-10-22T19:09:58.657511+00:00
- finalizado: 2026-10-22T19:10:09.952204+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 11.3

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
| postgres | 1 | 1 |
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
creadas=20/20; estados finales={'725a0b56-8966-438e-9c31-fcb9ad62ae41': 'CONFIRMED', 'e18f8c3b-52a3-4f20-8190-5545de48eb81': 'CONFIRMED', '15ab4aee-a07c-4f02-a928-5599714601f6': 'CONFIRMED', 'bb2efd51-fc59-4407-952d-6c8665991a4b': 'CONFIRMED', 'c8803e4c-8ba7-4b64-b8e6-449bb9047f75': 'CONFIRMED', 'e1859568-8b6e-4aa3-889f-0e9363d494b9': 'CONFIRMED', 'f852d12a-78ee-45fe-9ed0-ef55c13773f3': 'CONFIRMED', '5a95aa5f-af4e-479c-95e0-52653d4220f9': 'CONFIRMED', '06cdb357-4a24-4989-8b32-52681056aebe': 'CONFIRMED', '5b6334e5-4ba3-4e5f-bf83-aece22cae204': 'CONFIRMED', '3187dbf9-08c8-4344-b50b-5b49ed786ddb': 'CONFIRMED', '7cee7e5c-cb3b-42cb-93c1-a56f931cd0e3': 'CONFIRMED', '808a6181-cc2a-462b-bb72-72e3d45516c3': 'CONFIRMED', '48ede281-ffef-4dfc-b836-2ae04031b362': 'CONFIRMED', 'd04532cf-b77c-4789-8080-3c6ad1f4f852': 'CONFIRMED', '3453e64d-e81c-4f1f-9c1e-f052a457ae37': 'CONFIRMED', '82105e52-ec42-4ff7-b611-57d6bb48555f': 'CONFIRMED', '89da7a59-986b-4ba0-a1d1-9ae0ffa8f1a5': 'CONFIRMED', 'b94b8cd3-9bb9-47fa-a92b-9e43fe715b78': 'CONFIRMED', '6b012bbc-fb4c-41e2-94fa-803cd8db86ad': 'CONFIRMED'}; MANUAL_REVIEW=0; tiempo a estado final por reserva (API sincrona) ms: p50=740.9 p95=971.7 max=1005.8. Concurrencia limitada a 10 por el limit_conn del gateway (20 concurrentes => ~10 respuestas 429 de nginx); ver docs/resultados/chaos_E2_hallazgo.md.

