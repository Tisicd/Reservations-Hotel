# Prompt para OpenCode: F4b Parte 2 — carga (k6) y reporte

> Rama: `feat/f4b-carga`, desde `main` con la Parte 1 fusionada. **Tres hitos con commit propio.** Reglas de honestidad vigentes: evidencia o no existe · cada cifra con su plausibilidad · aserciones duras solo de integridad · no modificar pruebas para que pasen · hallazgos nunca ocultos.

---

## ROL
Ingeniero de rendimiento (SRE). Arquitectura aceptada. No rediseñes servicios; un cuello de botella o defecto hallado se **reporta** y, si procede, se corrige en commit aparte.

## LEE
`docs/03-estado-del-proyecto.md`, `docs/fases/F4-fallos-carga-reportes.md`, `docs/prompts/F4a-caos.md` (reglas de medición), `docs/resultados/F4a-cierre.md`, `docs/resultados/F4b-resiliencia.md`, `docs/resultados/chaos_E2_hallazgo.md`, `gateway/conf.d/default.conf`, `docs/adr/0007`, `docs/imagenes.md`.

## PASO 0 (commit `chore: base para carga`)
1. Confirma que `feat/f4b-resiliencia` está fusionada en `main` con CI verde; si no, avisa y detente. Versiona `docs/prompts/` pendiente y etiqueta `f4b1`.
2. Verifica `make build && make up && make seed` seguidos y `make invariants` ⇒ 0. Registra **hardware y versiones** (CPU modelo y núcleos, RAM total y asignada a Docker, versión de Docker Desktop, SO) en `docs/resultados/entorno.md`.

## LECCIONES QUE CONDICIONAN EL DISEÑO (de F4a/F4b)
- Los límites del gateway (`limit_conn`, `limit_req`) son **por IP** y todo el tráfico sale de una IP: para medir **capacidad de los servicios** se usa el **listener admin** (loopback, hoy `127.0.0.1:8081`) sirviendo también `/api/*` **sin `limit_*`** (documéntalo en ADR-0007). Solo P4 usa el listener público.
- Los rechazos del gateway son **429**; los 503 son fail-closed de servicios; no se mezclan.
- La API de `reservation` es síncrona con espera de hasta `SAGA_SYNC_WAIT_SECONDS=5`: una solicitud lenta retiene un hilo. Hipótesis a medir (no asumir): capacidad ≈ `hilos disponibles / espera`.
- Aislamiento: datos de prueba en un **hotel y habitaciones dedicados** y **bandas de fechas únicas por ejecución**; nunca reutilizar el inventario de la semilla.
- Docker Desktop: `host.docker.internal` para llegar desde el contenedor de k6 al listener admin.

## PREPARACIÓN (Hito 1)
- **k6 en contenedor** (`grafana/k6:<tag fijado>`), scripts montados desde `tests/perf/`; `make perf` (todas) y `make perf PERF=P1` (una). La imagen **no** forma parte de las del producto; documéntala y su tamaño en `docs/imagenes.md`.
- `tests/perf/setup.py` (solo biblioteca estándar): crea por el listener admin un hotel dedicado con N habitaciones (UUID deterministas `uuid5`) y fija inventario holgado (`PUT /inventory`); es **idempotente**. P3 fija el cupo exacto `K` por prueba.
- **Hipótesis registradas ANTES de ejecutar** en `tests/perf/hypotheses.md` (con fecha/hora y commit): para P1, P3 (ambas variantes), P2, P5; qué esperas y por qué. Después se contrastan; no se reescriben.
- `tests/perf/thresholds.json` con umbrales definidos antes (p. ej. lectura p95 < 300 ms y errores < 1 % en carga nominal; reservas p95 < 2 s).
- **Muestreadores** (en `tests/perf/run.py`, hilos durante cada ejecución, 1 s): `docker stats` por contenedor (CPU %, memoria), y consulta a PostgreSQL como superusuario de desarrollo: conexiones por BD y estado, y **número de sesiones esperando bloqueos** (`wait_event_type = 'Lock'`). Guardar series en JSON.
- **Escalado de réplicas:** `docker compose up -d --no-build --scale availability=N availability` + `make gateway-refresh`, esperando **convergencia** (todas las réplicas reciben tráfico, verificado con un sondeo) antes de medir. **Finalizer:** dejar siempre `availability=3` y el stack sano.
- **Protocolo por prueba:** calentamiento 20 s; ≥ 60 s de medición; **3 repeticiones**; reportar mediana y rango; marcar como **ruidosa** toda serie con coeficiente de variación > 15 %. `make invariants` tras toda prueba de escritura.

## PRUEBAS
| ID | Diseño | Qué se responde | Aserciones duras |
|---|---|---|---|
| **P1** Lectura 1 vs 3 réplicas | `ramping-arrival-rate` (modelo abierto) sobre `GET /api/availability` hasta saturar; N=1 y N=3 | rps máx. sostenible con umbrales cumplidos; ¿escala la lectura?; CPU por contenedor y conexiones a PG en la meseta | ninguna de integridad (solo lectura) |
| **P3** Contención | **V1:** 200 intentos concurrentes sobre la **misma** habitación/noches con `K` unidades. **V2:** los mismos 200 intentos **repartidos** en 50 habitaciones/noches. N=1 y N=3 réplicas de `availability` | Con V1, ¿la escritura escala con réplicas? (hipótesis típica: no, se serializa en PostgreSQL); diferencia V1 vs V2; sesiones esperando bloqueos y 503 por *lock timeout* | **Exactamente `K` `CONFIRMED`** en V1; invariantes en 0; 1 cobro por reserva |
| **P2** Mezcla 90/10 + variante con 10 % de pagos `slow` | Carga constante realista (lectura + reservas) | Latencia por tipo; **acoplamiento**: ¿degradan las reservas lentas a las lecturas y a las reservas rápidas? | invariantes en 0 |
| **P5** Rampa hasta saturación | `ramping-arrival-rate` sobre la mezcla | **Dónde está el cuello** (CPU de qué contenedor, conexiones/pool, bloqueos, hilos, `limit_*`) con tabla causa→evidencia | invariantes en 0 |
| **P4** Sobre el límite público | Ráfaga por el listener **público** sobre `limit_req`/`limit_conn`, con un **canario paralelo** por el listener admin | 429 observados; el canario no se degrada | — |
Cada informe `docs/resultados/perf_<ID>.md` incluye: parámetros, hipótesis previa y si se cumplió, tabla (rps logrados, p50/p95/p99, % errores por clase 429/503/5xx/timeout, `dropped_iterations`), series de CPU/conexiones/bloqueos, **conclusión honesta** y la advertencia: *k6, servicios y PostgreSQL comparten máquina; los resultados son comparativos, no absolutos*.

## REPORTE (Hito 3)
`make report` → `scripts/report.py` (solo biblioteca estándar) genera `docs/resultados/REPORTE.md` y rellena `docs/fallos.md`:
1. Entorno (de `entorno.md`).
2. **Caos:** tabla A, B, C, D, E1, E2, E3, E4, S, S2 con integridad, RTO/TTD **objetivo vs medido**, `¿cumplido?` y repeticiones (lee los JSON locales; si faltan, usa los `.md` y lo indica).
3. **Carga:** tablas por prueba y la **comparativa 1 vs 3 réplicas separando lectura y escritura**, con la conclusión.
4. **Hallazgos** (lista automática de objetivos incumplidos y anomalías, más los conocidos: `retries=12` y TTD de PostgreSQL ≈ 93 s; B 2,41 s intermitente; `limit_conn` por IP; RPO dependiente de backup manual; backup por BD no consistente entre servicios).
5. Sección **"Conclusiones"** con encabezados vacíos para que las redacte la persona (no inventes conclusiones por ella).
`REPORTE.md` y los `perf_*.md` **se versionan**; los JSON siguen ignorados por git.

## HITOS
- **1 (`test(perf): infraestructura de carga y P1`):** Paso 0, k6 en contenedor, setup, hipótesis, umbrales, muestreadores, P1.
- **2 (`test(perf): P3, P2, P5, P4`):** en ese orden de prioridad.
- **3 (`docs(report): reporte consolidado`):** `make report`, `fallos.md`, ADR-0007 actualizado.

## CRITERIOS DE ACEPTACIÓN (muestra salidas)
- [ ] Paso 0 completo; hardware registrado.
- [ ] `hypotheses.md` y `thresholds.json` commiteados **antes** de los resultados (verifícalo con `git log`).
- [ ] P1 y P3 (V1 y V2) con N=1 y N=3, ×3, con conclusión honesta apoyada en CPU/conexiones/bloqueos.
- [ ] P2 y P5 con cuello de botella identificado con datos; P4 con 429 observados.
- [ ] `make report` genera `REPORTE.md` y `fallos.md` completos desde un checkout con resultados locales.
- [ ] `availability` queda en 3 réplicas, stack sano, `make invariants` ⇒ 0, `make images`: 0 imágenes nuevas del producto.
**Regla de recorte:** obligatorios Paso 0, P1, P3 y `make report`. Recortables en este orden: P4, P5, P2. Si recortas, decláralo en el reporte.

## ENTREGA
PR con la plantilla; informe con salidas reales, tabla resumen y hallazgos. No fusiones a `main`.

## REGLAS
Evidencia o no existe · plausibilidad de cada cifra · hipótesis antes de medir · resultados comparativos, nunca absolutos · nada destructivo fuera del proyecto · si cambias arquitectura, propón el ADR y detente.
