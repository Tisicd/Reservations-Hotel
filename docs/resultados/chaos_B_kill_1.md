# Reporte de caos — escenario B (modo kill)

## Parámetros
- escenario: `B`
- modo: `kill`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-21T07:31:32.286990+00:00
- finalizado: 2026-10-21T07:32:54.482839+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 15.4 → 35.4
- recuperación: healthy en t=41.5
- fin: 61.7

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|
| baseline | 23 | 100.0 | — | 8.8 | 188.2 | 195.4 |
| falla | 28 | 100.0 | — | 10.2 | 236.6 | 1535.8 |
| drenaje | 30 | 100.0 | — | 8.1 | 186.3 | 193.5 |

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 0.47 s
- RTO objetivo: 2 s
- RTO cumplido: **sí**

## Reinicios de contenedores (RestartCount)
| servicio | antes | después |
|---|---|---|
| customer | 0 | 0 |
| hotel | 0 | 0 |
| availability | 1 | 0 |
| payment | 0 | 0 |
| reservation | 0 | 0 |
| notification | 0 | 0 |
| postgres | 1 | 1 |
| gateway | 0 | 0 |

## Aserciones duras
- invariantes con 0 violaciones: True
- no pérdida de datos: True
- stack sano al terminar: True

## Medidas del escenario
- éxito reservas en baseline: 100.0%
- éxito reservas durante la falla: 100.0%
- outbox pendiente durante la falla: 0
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- stack_sano_al_terminar: sí
- exito_reservas_falla >= baseline - 1pp: sí
- outbox_pendiente_despues_drenaje_cero: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** (endpoints con errores) — ver tabla de métricas y ventanas de caída.
2. **¿Cuáles siguieron funcionando?** (endpoints con éxito durante la falla) — ver éxito % por fase.
3. **¿Qué información se perdió?** — ninguna (no_perdida_datos OK)
4. **¿Cómo se recuperó?** — politica de reinicio de Docker / worker de recuperación
5. **¿Qué mecanismo mejoraría la resiliencia?** — cola durable con dead-letter y alerta por antigüedad del backlog (alarma OUTBOX_BACKLOG_OLD).

