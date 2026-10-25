# Reporte de caos — escenario A (modo api)

## Parámetros
- escenario: `A`
- modo: `api`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-25T02:10:42.448718+00:00
- finalizado: 2026-10-25T02:12:04.756655+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 15.4 → 35.4
- recuperación: healthy en t=43.5
- fin: 64.5

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|
| baseline | 23 | 100.0 | — | 8.0 | 181.4 | 188.1 |
| falla | 30 | 100.0 | — | 7.4 | 186.8 | 222.5 |
| drenaje | 30 | 100.0 | — | 8.3 | 178.9 | 185.1 |

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 0.65 s
- RTO objetivo: 300 s
- RTO cumplido: **sí**

## Reinicios de contenedores (RestartCount)
| servicio | antes | después |
|---|---|---|
| customer | 0 | 0 |
| hotel | 0 | 0 |
| availability | 1 | 1 |
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
- outbox_pendiente_despues_drenaje_cero: sí
- exito_reservas_falla >= baseline - 1pp: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** 30/30 peticiones OK (100.0%), errores {}, p95=186.8 ms.
2. **¿Cuáles siguieron funcionando?** el flujo respondió 100.0% durante la falla (baseline 100.0%).
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=0, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=0.6541327000013553 s (objetivo 300 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** dead-letter y alerta de antigüedad del backlog.

## Evidencia adicional (Docker health)
Timeline (s desde t0): ultima buena antes de la falla=15.045209199997771; primer fallo=n/d; primer exito sostenido=16.007255299999088; RTO=0.6541327000013553 s.

