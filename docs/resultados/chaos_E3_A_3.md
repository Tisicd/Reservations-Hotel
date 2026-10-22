# Reporte de caos — escenario E3 (modo A)

## Parámetros
- escenario: `E3`
- modo: `A`
- repetición: 3
- rps: 1.5
- baseline_s: 15
- fault_s: 20
- drain_s: 20
- semilla: `D:\github\tlhotel\reservas-platform\secrets\seed.json`
- iniciado: 2026-10-22T14:06:59.586292+00:00
- finalizado: 2026-10-22T14:07:53.329091+00:00

## Línea de tiempo (segundos desde arranque)
- baseline: 0 → 15.0
- falla: 0.0 → 20.0
- recuperación: no alcanzó healthy
- fin: 53.7

## Métricas por fase (peticiones de fondo)
| fase | peticiones | éxito % | errores por clase | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|

## Ventanas de indisponibilidad (canario)
(ninguna ventana detectada)

- TTD: no detectado
- RTO medido: 30.49 s
- RTO objetivo: 900 s
- RTO cumplido: **sí**

## Reinicios de contenedores (RestartCount)
| servicio | antes | después |
|---|---|---|
| customer | None | None |
| hotel | None | None |
| availability | None | None |
| payment | None | None |
| reservation | None | None |
| notification | None | None |
| postgres | None | None |
| gateway | None | None |

## Medidas del escenario
- éxito reservas en baseline: 100.0%
- éxito reservas durante la falla: 0.0%
- outbox pendiente durante la falla: 0
- outbox pendiente tras el drenaje: 0
- invariantes_cero_violaciones: sí
- rto_restauracion_cumplido: sí
- rpo_observado: sí
- variante: sí

## Las 5 preguntas del enunciado
1. **¿Qué componentes se afectaron?** sin tráfico de fondo en este escenario (C/D/E2/S).
2. **¿Cuáles siguieron funcionando?** sin tráfico de fondo; se comprobó el estado final de las reservas y los invariantes.
3. **¿Qué información se perdió?** ver FALLA DURA.
4. **¿Cómo se recuperó?** no se restauró automáticamente.
5. **¿Qué mecanismo mejoraría la resiliencia?** más réplicas y health checks activos.

## Evidencia adicional (Docker health)
Variante A; backup=20261022T140703Z; volumen=reservas-platform_pgdata. RTO borrado->trafico+invariantes=30.5 s (objetivo 900). Reservas creadas tras el backup perdidas (RPO observado)=5/5. Invariantes tras restaurar=0.
Violaciones: []

