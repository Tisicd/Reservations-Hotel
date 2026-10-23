# Prompt para OpenCode: F4c cierre de carga (tope 2 h)

> Rama: `feat/f4c-carga-cierre`, desde `main` con `feat/f4b-carga` fusionada (CI verde). Un commit por punto. **Hipótesis antes de medir; evidencia o no existe; no modificar pruebas para que pasen.**

---

## ROL
Ingeniero de rendimiento (SRE). Cierra los huecos de la Parte 2 para que las conclusiones de escalabilidad sean defendibles. No amplíes alcance.

## LEE
`docs/resultados/perf_P1.md`, `perf_P3.md`, `tests/perf/hypotheses.md`, `thresholds.json`, `docs/resultados/REPORTE.md`, `gateway/conf.d/default.conf`, `docs/adr/0007`.

## PUNTO 0: E2E inestable en CI (commit `test(e2e): estabilizar`)
El CI de `main` falló una vez en E2E y pasó al reintentar; que pase 10/10 en local **no descarta una condición de carrera**. Con el log del run fallido (obtén el id con la API de GitHub): (1) identifica la aserción y el escenario que fallaron; (2) clasifica: **temporización del test** (esperas fijas, polling corto en un runner más lento), **colisión de datos** (fechas/clientes compartidos) o **defecto real del producto**; (3) estabiliza con *polling con tiempo límite* y datos únicos por prueba; (4) ejecuta el E2E **×20 seguidos en local y 3 veces en CI** sin fallos. Si es un defecto del producto, repórtalo con evidencia y corrígelo en commit aparte.

## PUNTO 1: explicar el 2,09× de P1 (commit `docs(perf): análisis de P1`)
La mejora de 189 → 394 rps (sublineal) está **sin explicar**: no sabemos si limita el servicio, PostgreSQL, el gateway o el generador de carga. Con las series ya muestreadas (o repitiendo P1 ×1 si no se capturaron), reporta en la meseta de N=1 y N=3 la **CPU de cada contenedor**: `availability` (suma y por réplica), `postgres`, **`gateway`** y **el contenedor de k6**, más las conexiones a PostgreSQL. Compara con los recursos disponibles (12 CPUs lógicas asignadas a Docker). Reglas de lectura: si `gateway` o `k6` están cerca de saturar un núcleo, el límite es **infraestructura de medición** y debe decirse; si `availability` está saturada por réplica, es CPU de Python; si `postgres` crece más que linealmente, es la BD. Comprueba también `worker_processes` y `worker_connections` de nginx. Entrega una tabla **recurso → uso en la meseta → ¿cuello?** y una conclusión que explique el 2,09×. Si corriges algo (p. ej. `worker_processes auto`), mide antes/después ×3.

## PUNTO 2: P3b contención aislada de `availability` (commit `test(perf): P3b holds directos`)
P3 pasó por `reservation`: con 200 solicitudes concurrentes y la saga **síncrona** (espera de hasta 5 s, ~40 hilos por proceso) midió sobre todo la **cola de la API de `reservation`** (p95 5–6,5 s, 0 esperas de bloqueo). **No contrastó** la hipótesis de contención en PostgreSQL. Para aislarla:
1. **Antes de medir**, añade a `tests/perf/hypotheses.md` (commit separado y anterior) las hipótesis de P3b: V1 (mismo cupo) con latencia mayor que V2 (repartido); **N=3 no mejora V1**; V2 mejora con N.
2. Script k6 que llama **directamente** `POST /svc/availability/holds` por el listener admin (sin `reservation`): **200 `hold_id` distintos concurrentes**. **V1:** misma habitación y noches con `K` unidades. **V2:** repartidos en 50 habitaciones/noches. N=1 y N=3 réplicas, ×3. TTL corto (30 s) y liberación/expiración al final.
3. Muestreo de bloqueos a **100 ms** (`wait_event_type='Lock'`) y delta de `pg_stat_database.deadlocks`; contar `503` por *lock timeout* (`lock_timeout=2s`) y latencias p50/p95/p99.
4. **Aserciones duras:** en V1 exactamente `K` holds `HELD` y el resto `NO_INVENTORY`; invariantes en 0 (sin `LEAKED_HOLD` ni `OVERSELL`); cero deadlocks.
5. Informe `perf_P3b.md` con hipótesis vs resultado y **conclusión honesta** (si 3 réplicas no mejoran V1, dilo y explícalo con bloqueos/CPU). Registra además en el reporte el hallazgo sobre P3: **la latencia alta de P3 se debe a la saga síncrona de `reservation`, no a contención**; recomendación: reducir `SAGA_SYNC_WAIT_SECONDS`, responder `202` inmediato, o más procesos/réplicas de `reservation`.

## PUNTO 3: P4 límite público (commit `test(perf): P4`)
Ráfaga por el listener **público** que supere `limit_req` y `limit_conn`; **canario paralelo** por el listener admin. Reporta: nº de 429 por tipo, que el canario **no** se degrada, y el tiempo de recuperación al cesar la ráfaga. Es la evidencia del control de saturación de conexiones del punto 12 del enunciado.

## PUNTO 4: reporte (commit `docs(report): P1 analizado, P3b, P4`)
`make report` actualizado: incluye P3b y P4, el análisis de P1 y la nota de **limitaciones**: P2 y P5 no ejecutados (declaración explícita), resultados comparativos en una sola máquina, ruido de P3 (CV hasta 31 %). No inventes conclusiones: deja "Conclusiones" para la persona.

## CRITERIOS DE ACEPTACIÓN (muestra salidas)
- [ ] E2E ×20 local y ×3 en CI sin fallos; causa del fallo original clasificada con evidencia.
- [ ] Tabla recurso→uso→¿cuello? de P1 con CPU de gateway y k6.
- [ ] `hypotheses.md` de P3b commiteado **antes** que los resultados (`git log`).
- [ ] P3b V1/V2 × N=1/N=3 ×3, aserciones duras en verde, conclusión honesta.
- [ ] P4 con 429 observados y canario estable.
- [ ] `availability` en 3 réplicas, stack sano, `make invariants` ⇒ 0, `make images` sin cambios del producto.
**Recorte (en este orden):** P4, mejora de nginx de P1. Obligatorios: punto 0, tabla de P1 y P3b.

## REGLAS
Hipótesis antes de medir · evidencia o no existe · cada cifra plausible · nada destructivo fuera del proyecto · si cambias arquitectura, propón el ADR y detente. No fusiones a `main`.
