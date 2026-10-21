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
- iniciado: 2026-10-21T07:29:25.432571+00:00
- finalizado: 2026-10-21T07:30:51.707720+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 15.4 → 35.4
- recuperación: healthy en t=44.3
- fin: 65.5

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|
| baseline | 23 | 100.0 | — | 7.6 | 168.5 | 196.9 |
| falla | 30 | 100.0 | — | 7.8 | 197.0 | 209.8 |
| drenaje | 30 | 100.0 | — | 8.4 | 223.6 | 252.5 |

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 0.80 s
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

## Aserciones duras
- invariantes con 0 violaciones: True
- no pérdida de datos: True
- stack sano al terminar: True

## Medidas del escenario
- éxito reservas en baseline: 100.0%
- éxito reservas durante la falla: 100.0%
- outbox pendiente durante la falla: 7
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- stack_sano_al_terminar: sí
- exito_reservas_falla >= baseline - 1pp: sí
- outbox_pendiente_despues_drenaje_cero: sí
- outbox_pendiente_durante_falla_positiva: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** (endpoints con errores) — ver tabla de métricas y ventanas de caída.
2. **¿Cuáles siguieron funcionando?** (endpoints con éxito durante la falla) — ver éxito % por fase.
3. **¿Qué información se perdió?** — ninguna (no_perdida_datos OK)
4. **¿Cómo se recuperó?** — politica de reinicio de Docker / worker de recuperación
5. **¿Qué mecanismo mejoraría la resiliencia?** — cola durable con dead-letter y alerta por antigüedad del backlog (alarma OUTBOX_BACKLOG_OLD).

