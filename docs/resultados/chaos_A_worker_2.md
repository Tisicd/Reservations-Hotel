# Reporte de caos — escenario A (modo worker)

## Parámetros
- escenario: `A`
- modo: `worker`
- repetición: 2
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T02:36:03.234138+00:00
- finalizado: 2026-10-22T02:37:25.894539+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 15.4 → 35.4
- recuperación: healthy en t=44.0
- fin: 64.1

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|
| baseline | 23 | 100.0 | — | 7.9 | 176.8 | 179.9 |
| falla | 30 | 100.0 | — | 7.9 | 194.1 | 212.2 |
| drenaje | 30 | 100.0 | — | 7.7 | 187.5 | 280.1 |

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 1.17 s
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
| postgres | 0 | 0 |
| gateway | 0 | 0 |

## Medidas del escenario
- éxito reservas en baseline: 100.0%
- éxito reservas durante la falla: 100.0%
- outbox pendiente durante la falla: 8
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- stack_sano_al_terminar: sí
- outbox_pendiente_despues_drenaje_cero: sí
- exito_reservas_falla >= baseline - 1pp: sí
- outbox_pendiente_durante_falla_positiva: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** 30/30 peticiones OK (100.0%), errores {}, p95=194.1 ms.
2. **¿Cuáles siguieron funcionando?** el flujo respondió 100.0% durante la falla (baseline 100.0%).
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=8, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=1.170799999999872 s (objetivo 300 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** dead-letter y alerta de antigüedad del backlog.

