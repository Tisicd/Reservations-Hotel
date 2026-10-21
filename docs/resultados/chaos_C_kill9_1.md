# Reporte de caos — escenario C (modo kill9)

## Parámetros
- escenario: `C`
- modo: `kill9`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-21T09:25:19.714000+00:00
- finalizado: 2026-10-21T09:25:31.156680+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=3.6
- fin: 11.4

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 3.55 s
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
- sin_holds_duplicados: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** (endpoints con errores) — ver tabla de métricas y ventanas de caída.
2. **¿Cuáles siguieron funcionando?** (endpoints con éxito durante la falla) — ver éxito % por fase.
3. **¿Qué información se perdió?** — ninguna (no_perdida_datos OK)
4. **¿Cómo se recuperó?** — política de reinicio de Docker / worker de recuperación
5. **¿Qué mecanismo mejoraría la resiliencia?** — cola durable con dead-letter y alerta por antigüedad del backlog (alarma OUTBOX_BACKLOG_OLD).

