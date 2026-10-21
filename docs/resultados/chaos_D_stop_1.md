# Reporte de caos — escenario D (modo stop)

## Parámetros
- escenario: `D`
- modo: `stop`
- repetición: 1
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-21T09:28:54.917954+00:00
- finalizado: 2026-10-21T09:29:28.696460+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: healthy en t=30.7
- fin: 33.8

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 0.11 s
- RTO objetivo: 120 s
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
- éxito reservas durante la falla: 0.0%
- outbox pendiente durante la falla: 40
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- no_perdida_datos: sí
- stack_sano_al_terminar: sí
- servicios_sin_reiniciar: sí
- rto_escritura_cumplido: sí
- errores_503_durante_falla: sí
- filas_conservadas: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** (endpoints con errores) — ver tabla de métricas y ventanas de caída.
2. **¿Cuáles siguieron funcionando?** (endpoints con éxito durante la falla) — ver éxito % por fase.
3. **¿Qué información se perdió?** — ninguna (no_perdida_datos OK)
4. **¿Cómo se recuperó?** — política de reinicio de Docker / worker de recuperación
5. **¿Qué mecanismo mejoraría la resiliencia?** — cola durable con dead-letter y alerta por antigüedad del backlog (alarma OUTBOX_BACKLOG_OLD).

