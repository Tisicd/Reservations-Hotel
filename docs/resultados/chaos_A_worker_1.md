# Reporte de caos — escenario A (modo worker)

## Parámetros
- escenario: `A`
- modo: `worker`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T18:59:52.445479+00:00
- finalizado: 2026-10-22T19:01:14.298829+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 15.4 → 35.4
- recuperación: healthy en t=44.1
- fin: 64.2

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|
| baseline | 23 | 100.0 | — | 9.2 | 189.3 | 193.6 |
| falla | 30 | 100.0 | — | 8.7 | 190.3 | 205.0 |
| drenaje | 30 | 100.0 | — | 7.5 | 175.3 | 183.2 |

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 1.15 s
- RTO objetivo: 300 s
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
- outbox pendiente durante la falla: 9
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- stack_sano_al_terminar: sí
- outbox_pendiente_despues_drenaje_cero: sí
- exito_reservas_falla >= baseline - 1pp: sí
- outbox_pendiente_durante_falla_positiva: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** 30/30 peticiones OK (100.0%), errores {}, p95=190.3 ms.
2. **¿Cuáles siguieron funcionando?** el flujo respondió 100.0% durante la falla (baseline 100.0%).
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=9, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=1.14794759999495 s (objetivo 300 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** dead-letter y alerta de antigüedad del backlog.

## Evidencia adicional (Docker health)
Timeline (s desde t0): ultima buena antes de la falla=15.028961300005903; primer fallo=n/d; primer exito sostenido=16.53738510000403; RTO=1.14794759999495 s.

