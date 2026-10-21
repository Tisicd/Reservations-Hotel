# Prompt para OpenCode: F4a arnés de caos + escenarios A, B, C, D, E2 y S

> Pegar desde "ROL". Rama: `feat/f4a-caos`, desde `main` con el control de imágenes fusionado. **Cuatro commits: PASO 0, Hito 1 (arnés + A + B), Hito 2 (C + D), Hito 3 (E2 + S + docs).** Esta es la evidencia central de la defensa: prioriza la **honestidad de las mediciones** sobre la apariencia.

---

## ROL
Ingeniero de fiabilidad (SRE). Arquitectura aceptada y F1–F2 cerradas. **No rediseñes servicios.** Si una prueba revela un defecto real, **repórtalo como hallazgo** (no lo ocultes ni cambies la prueba para que pase) y propón la corrección en un commit aparte.

## LEE ANTES DE ACTUAR
`docs/03-estado-del-proyecto.md`, `docs/fases/F4-fallos-carga-reportes.md`, `docs/fases/F0-negocio-y-resiliencia.md` (§0 invariantes, §2.3 modos de fallo, §4 RTO/RPO objetivo), `docs/proceso/modos-de-caida.md`, `tests/invariants/` y `tests/e2e/` (reutiliza helpers; **no dupliques**), `compose.yaml`, `Makefile`.

## PASO 0 (commit `chore: base para caos`)
1. Confirma que `make test` mantiene **al menos el mismo total** que antes del cambio de imágenes (251 pasadas en F2) y que no hay omitidas; si el total bajó, explica por qué.
2. Verifica que `docs/imagenes.md` incluye la tabla actual de **tamaños** por imagen (se usa en el informe, punto 4 del enunciado). Documenta en el README el flujo `make build && make up && make seed`.
3. Añade al chequeador la alarma **`OUTBOX_BACKLOG_OLD`** (evento del outbox en `PENDING` con antigüedad > umbral configurable; por defecto 300 s). Prueba: inyección dentro de transacción, igual que las demás.
4. Crea `docs/prompts/` completo en `main` si falta algo.

## OBJETIVO
Un arnés reproducible que **inyecte fallos reales** en el stack levantado, mida impacto y recuperación, compruebe invariantes y **no pérdida de datos**, y genere un reporte por escenario con las 5 preguntas del enunciado respondidas con cifras.

## ALCANCE
**Puedes crear/modificar:** `tests/chaos/**`, `tests/invariants/**` (solo la alarma), `Makefile`, `docs/fallos.md` (esqueleto), `docs/resultados/chaos_*.md`, `docs/proceso/modos-de-caida.md`, `docs/03-estado-del-proyecto.md` (estado), `tests/requirements.txt` **solo si es imprescindible** (prefiere la biblioteca estándar y lo que ya usan los e2e).
**Prohibido:** cambiar código de servicios (salvo corrección de un defecto hallado, en commit aparte y avisando), borrar volúmenes, `docker system prune`, nuevas dependencias en las imágenes del producto.

## ARNÉS (`tests/chaos/harness.py`) — unidades pequeñas y probadas
1. **`Stack`**: envoltorio de `docker compose` / `docker` por `subprocess`: `kill(svc)`, `stop(svc)`, `start(svc)`, `recreate(svc)` (`rm -sf` + `up -d --no-build`), `exec_kill9(svc, patrón)`, `wait_healthy(svc, timeout)`, `restart_count(svc)`, `health_log(svc)`, `ps_snapshot()`. Para servicios con **réplicas** (`availability` x3) resuelve los contenedores con `docker compose ps -q <svc>` y actúa sobre **un** contenedor concreto. Nunca `--build`.
2. **`TrafficGenerator`**: hilos en segundo plano con ritmo fijo (`rps`) que crean reservas (clave única, cliente y hotel de la semilla, **fechas aleatorias** y habitaciones repartidas para no agotar el inventario) y leen disponibilidad. Dos modos de cliente: **crudo** (sin reintentos) y **con reintentos** (misma `Idempotency-Key`, ≤3 intentos, backoff). Registra por petición: instante, latencia, código HTTP, clase de error, `reservation_id`.
3. **`Canary`**: sondeo cada 500 ms de la **ruta de lectura** (`GET /api/availability`) y cada 2 s de la **ruta de escritura** (reserva de prueba). `compute_outage_windows(samples, min_consecutive=2)` devuelve ventanas de indisponibilidad; de ahí salen **TTD** (detección) y **RTO medido** (inicio de la falla → primer éxito sostenido).
4. **Fases de un escenario:** línea base (N s) → falla → recuperación → cola (N s). Cada escenario registra `t_baseline, t_fault, t_recovered, t_end`, `RestartCount` antes/después, y estado de salud de todos los servicios.
5. **Cierre obligatorio de cada escenario:** `make invariants` en **0 violaciones**, `assert_no_loss(snapshot_antes, snapshot_después)`, y **restaurar el stack a sano** (finalizer que vuelve a levantar lo caído y espera `healthy`); si no puede, falla de forma visible.
6. **Informe por escenario** (`docs/resultados/chaos_<ID>.md` + JSON ignorado por git): parámetros, línea de tiempo, tabla de métricas (éxito %, errores por clase, p50/p95/p99 antes/durante/después, ventanas de indisponibilidad, RTO medido **vs objetivo de F0 §4.2** con `objetivo cumplido: sí/no`), y las **5 preguntas** del enunciado respondidas **con las cifras medidas**: (1) ¿qué componentes se afectaron? (endpoints con errores) (2) ¿cuáles siguieron funcionando? (endpoints con éxito durante la falla) (3) ¿qué información se perdió? (resultado de `assert_no_loss` y pendientes) (4) ¿cómo se recuperó? (mecanismo observado: política de reinicio, worker, reintento del cliente, operador) (5) ¿qué mecanismo mejoraría la resiliencia? (texto de la columna "Mejora" de la tabla de abajo).
7. **Pruebas unitarias del propio arnés** (sin Docker): `compute_outage_windows`, percentiles, clasificación de errores, ensamblado del informe.

**Reglas de medición:** esperas con *polling y tiempo límite*, nunca `sleep` ciego; semilla fija del generador aleatorio registrada en el informe; **una aserción dura** solo para integridad (invariantes, no pérdida, cobro único, estados finales); los **RTO se registran contra el objetivo pero no hacen fallar la prueba** (se reportan honestamente).

## ESCENARIOS
| ID | Acción (modo) | Aserciones duras | Métricas clave | Mejora (texto para la pregunta 5) |
|---|---|---|---|---|
| **A** | Detener `notification` (API) 30 s con tráfico de fondo (modo A); variante: detener `notification-worker` | Éxito de reservas ≥ línea base − 1 pp; pendientes del outbox **> 0** durante la caída y **= 0** tras la recuperación (vaciado ≤ 300 s); **una notificación por reserva confirmada**, sin duplicados | % éxito, pendientes máx., tiempo de vaciado | Cola durable con *dead-letter* y alerta por antigüedad del backlog |
| **B** | Matar **1 de las 3** réplicas de `availability` bajo carga: modo A (`docker kill`) y modo B (`kill -9` interno) | Sin pérdida ni sobreventa; las lecturas con reintento de cliente no fallan | errores durante la ventana (crudo vs con reintento), p95 antes/durante/después, tiempo hasta que nginx deja de enviar a la réplica caída | Health check activo y reintentos acotados; autoescalado en multinodo |
| **C** | Reiniciar `reservation` con 20 reservas en curso (`simulate=slow`): modo B y modo A + reinicio | **Todas** llegan a estado estable correcto; **exactamente 1 cobro por reserva**; 0 holds duplicados; 0 estados huérfanos | RTO hasta `healthy`, nº de reservas recuperadas por el worker, tiempo hasta estado estable | Replicar la API de `reservation` y mantener el worker con elección de líder |
| **D** | Eliminar y recrear el contenedor `postgres` **con el mismo volumen** bajo carga | `assert_no_loss` OK; **los servicios se reconectan sin reiniciarse** (`RestartCount` de servicios sin cambio); invariantes | RTO a escritura exitosa, errores 503 (fail-closed, nunca 2xx falsos), conteos de filas antes/después | Réplica con *failover* automático y backups con PITR |
| **E2** | 20 reservas con `process_then_drop_response` y 20 con `slow` (>timeout del proveedor) | Todas pasan por `UNKNOWN`/`202` y terminan `CONFIRMED`; **1 cobro por reserva**; 0 `MANUAL_REVIEW` | Tiempo hasta estado final (distribución p50/p95) | Conciliación contra extractos del proveedor real y webhooks |
| **S** | Detener `postgres` (servicio no saludable por dependencia): observar `/ready` y salud de Docker | Reservas devuelven **503** (nunca 2xx falsos); sin cambios de estado; invariantes OK al volver | **TTD** (tiempo hasta `unhealthy`), tiempo a `healthy`, comportamiento del gateway | Health check activo y *circuit breaker* en el gateway |
Para **S** incluye en el informe el extracto de `docker inspect` (`Health.Log`) y explica **cómo Docker decide `unhealthy`** (`interval`, `timeout`, `retries`, `start_period`), que es el punto 8 del enunciado.

## COMANDOS
`make chaos` (todos) · `make chaos SCEN=A` (uno) · `make chaos REPEAT=3` (repeticiones, cada una con su informe). **Precondición verificada por el propio comando:** imágenes construidas, stack `healthy` y semillado; si no, aborta con el mensaje exacto de qué ejecutar. `make chaos` **no** forma parte de `make test` ni del CI por defecto (CI puede ejecutar solo `SCEN=A` como humo si es estable).
Protocolo documentado: `make clean-all && make build && make up && make seed && make chaos`.

## HITOS
- **1 (`test(chaos): arnés, escenarios A y B`):** arnés + pruebas del arnés + A + B.
- **2 (`test(chaos): escenarios C y D`).**
- **3 (`test(chaos): escenarios E2 y S, informes y docs`):** E2, S, `docs/fallos.md` (esqueleto con la tabla de escenarios y enlaces a los informes), actualización de `modos-de-caida.md` y `03-estado-del-proyecto.md`.

## CRITERIOS DE ACEPTACIÓN (muestra la salida)
- [ ] Paso 0 completo; total de pruebas ≥ línea base, 0 omitidas.
- [ ] `make clean-all && make build && make up && make seed && make chaos` ⇒ todas las aserciones duras pasan; **stack sano al terminar**; `make invariants` ⇒ 0 violaciones.
- [ ] Cada escenario con su `docs/resultados/chaos_<ID>.md` con las **5 preguntas respondidas con cifras** y la tabla RTO medido vs objetivo.
- [ ] Cada escenario ejecutado **3 veces** (`REPEAT=3`) con resultados consistentes; si hay variabilidad, repórtala.
- [ ] `make images`: **0 imágenes nuevas** tras toda la batería.
- [ ] Hallazgos: lista explícita de cualquier objetivo de RTO incumplido o defecto descubierto, con evidencia (no los corrijas dentro del arnés).

## ENTREGA
PR con la plantilla; informe con archivos, salidas, tabla resumen (escenario · integridad · RTO medido · objetivo · ¿cumplido?) y hallazgos. No fusiones a `main`.

## REGLAS
Medir con honestidad · aserciones duras solo de integridad · nunca ocultar un hallazgo · nada destructivo fuera del alcance (sin `-v`, sin prune) · sin dependencias nuevas en imágenes de producto · si cambias arquitectura, propón el ADR y detente.
