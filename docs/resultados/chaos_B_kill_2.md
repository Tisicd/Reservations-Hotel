# Reporte de caos — escenario B (modo kill)

## Parámetros
- escenario: `B`
- modo: `kill`
- repetición: 2
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T02:40:14.604431+00:00
- finalizado: 2026-10-22T02:41:33.854905+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 15.4 → 35.4
- recuperación: healthy en t=41.3
- fin: 61.4

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|
| baseline | 23 | 100.0 | — | 6.4 | 49.5 | 150.3 |
| falla | 28 | 96.43 | 5xx=1 | 7.0 | 181.8 | 187.1 |
| drenaje | 30 | 100.0 | — | 7.8 | 123.5 | 181.1 |
| falla_retry | 30 | 100.0 | — | 7.8 | 183.4 | 191.2 |

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 0.36 s
- RTO objetivo: 2 s
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
- éxito reservas durante la falla: 96.43%
- outbox pendiente durante la falla: 2
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- stack_sano_al_terminar: sí
- outbox_pendiente_despues_drenaje_cero: sí
- exito_con_reintento >= 99%: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** 27/28 peticiones OK (96.43%), errores {'5xx': 1}, p95=181.8 ms.
2. **¿Cuáles siguieron funcionando?** el flujo respondió 96.43% durante la falla (baseline 100.0%).
3. **¿Qué información se perdió?** ninguna (no_perdida_datos OK); outbox pendiente durante la falla=2, tras drenaje=0.
4. **¿Cómo se recuperó?** política de reinicio/worker de recuperación; RTO medido=0.3562074000001303 s (objetivo 2 s, cumplido=sí).
5. **¿Qué mecanismo mejoraría la resiliencia?** health check activo y reintentos acotados; autoescalado en multinodo.

