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
- iniciado: 2026-10-21T10:49:42.515171+00:00
- finalizado: 2026-10-21T10:52:19.477681+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 157.0

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: no alcanzado
- RTO objetivo: 30 s
- RTO cumplido: **no**

## Reinicios de contenedores (RestartCount)
| servicio | antes | después |
|---|---|---|
| customer | None | 0 |
| hotel | None | 0 |
| availability | None | 0 |
| payment | None | 0 |
| reservation | None | 0 |
| notification | None | 0 |
| postgres | None | 0 |
| gateway | None | 0 |

## Medidas del escenario
- éxito reservas en baseline: 100.0%
- éxito reservas durante la falla: 100.0%
- outbox pendiente durante la falla: 0
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: no
- stack_sano_al_terminar: sí
- todas_las_reservas_estables: no
- un_cargo_por_reserva: no

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** (endpoints con errores) — ver tabla de métricas y ventanas de caída.
2. **¿Cuáles siguieron funcionando?** (endpoints con éxito durante la falla) — ver éxito % por fase.
3. **¿Qué información se perdió?** — ver FALLA DURA
4. **¿Cómo se recuperó?** — política de reinicio de Docker / worker de recuperación
5. **¿Qué mecanismo mejoraría la resiliencia?** — cola durable con dead-letter y alerta por antigüedad del backlog (alarma OUTBOX_BACKLOG_OLD).

