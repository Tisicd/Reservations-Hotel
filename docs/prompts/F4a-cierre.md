# Prompt para OpenCode: F4a cierre (auditoría de evidencia + completar + analizar E2)

> Pegar desde "ROL". Trabajo sobre el código ya escrito. **No se acepta nada sin evidencia ejecutable.** Cuatro commits: PASO 0 (git), AUDITORÍA, COMPLETAR, HALLAZGOS.

---

## ROL
Ingeniero de fiabilidad (SRE) y revisor. Tu informe anterior mezcla trabajo de imágenes Docker con trabajo de caos, atribuye un hallazgo a una causa que no tiene relación (el `pip install` del Dockerfile no puede explicar un comportamiento de concurrencia en tiempo de ejecución) y no muestra las salidas exigidas. **Corrige con rigor:** cada afirmación de "hecho" debe venir con el comando ejecutado y su salida, o con `archivo:línea`. Si algo no existe, dilo.

## LEE
`docs/prompts/F4a-caos.md` (es el **contrato**: arnés, escenarios, aserciones, informes, criterios de aceptación), `docs/03-estado-del-proyecto.md`, `docs/fases/F0-negocio-y-resiliencia.md` §4, `tests/chaos/`, `docs/resultados/chaos_*.md`, `Makefile`.

## PASO 0: higiene de Git (commit propio)
El trabajo de caos quedó commiteado en la rama `chore/docker-imagenes` (`276460c`). **Sepáralo:** la rama de imágenes debe contener solo lo de imágenes y el caos debe vivir en `feat/f4a-caos` (con `git rebase -i`/`cherry-pick`; no pierdas commits; muestra `git log --oneline` de ambas ramas antes y después). Si el CI de imágenes ya pasó, ese PR puede fusionarse primero.

## FASE 1: AUDITORÍA (solo lectura; entrega `docs/resultados/F4a-auditoria.md`)
Tabla con **una fila por requisito** de `F4a-caos.md` y columnas `requisito | estado (✔/parcial/✘) | evidencia`:
1. Paso 0: total de pruebas ≥ 251 y 0 omitidas; `OUTBOX_BACKLOG_OLD` implementada y probada.
2. Arnés: `Stack` (incluye acción sobre **una** réplica de `availability`), `TrafficGenerator` (modo crudo y modo con reintentos con la misma clave), `Canary` (lectura y escritura), `compute_outage_windows`, fases base→falla→recuperación→cola, finalizer que restaura el stack, cierre con invariantes y `assert_no_loss`.
3. Pruebas unitarias del **propio arnés** (sin Docker): lista y resultado.
4. Escenarios **A, B, C, D, E2 y S**: aserciones duras implementadas (cuáles) y qué se midió. **El escenario S no tiene informe en la lista que reportaste: confirma si existe.**
5. Informes `chaos_<ID>.md`: ¿incluyen las **5 preguntas respondidas con cifras**, la tabla **RTO medido vs objetivo** y `objetivo cumplido: sí/no`?
6. `make chaos`, `make chaos SCEN=A`, `make chaos REPEAT=3` y la **precondición** (imágenes, stack sano, semilla) existen y funcionan.
7. `docs/fallos.md` (esqueleto), `docs/proceso/modos-de-caida.md` y `03-estado-del-proyecto.md` actualizados.
8. `make images`: 0 imágenes nuevas tras la batería.
Sé explícito con lo que **no** esté hecho; no lo des por implícito.

## FASE 2: COMPLETAR lo que falte (commit `test(chaos): completar F4a`)
Todo lo marcado parcial/✘, siguiendo `F4a-caos.md` sin recortar. Después ejecuta el protocolo completo y **pega la salida**:
`make clean-all && make build && make up && make seed && make chaos REPEAT=3`
Entrega la **tabla resumen**: `escenario | integridad (invariantes y no pérdida) | RTO medido | objetivo | ¿cumplido? | repeticiones consistentes | hallazgos`. El stack debe terminar `healthy` y `make invariants` ⇒ 0 violaciones.

## FASE 3: HALLAZGO DE E2 (commit `docs(chaos): análisis del hallazgo E2` + corrección si procede)
Reportaste que algunas reservas del escenario E2 quedan en `PAYMENT_UNKNOWN` tras la espera síncrona de 5 s. **Eso, por sí solo, es el comportamiento diseñado** (la API responde `202` y el worker resuelve después); el criterio de F4a es que **terminen `CONFIRMED`** dentro de un plazo razonable. Determina cuál de estos tres casos es el real, con evidencia:
- **(a) Defecto del test:** el arnés evaluó el estado final justo después de la espera síncrona. Corrige el arnés para **sondear hasta un límite** (p. ej. 60 s) y registrar la **distribución del tiempo hasta el estado final** (p50/p95/máx.).
- **(b) Defecto real:** alguna reserva **sigue en `PAYMENT_UNKNOWN` más allá del ciclo de recuperación/reconciliación** (`RECOVERY_INTERVAL_SECONDS`, `RECONCILE_INTERVAL_SECONDS`, `RECONCILE_MIN_AGE_SECONDS`). Entrega: reproducción mínima, `GET /reservations/{id}/events` de las afectadas, logs de `reservation-worker`, `reservation-relay` y `payment-worker`, causa raíz y propuesta (commit aparte).
- **(c) Límite de capacidad:** con 20+ solicitudes concurrentes que esperan hasta 5 s, los hilos del servidor (endpoints síncronos) se saturan y suben las latencias. Hipótesis a **medir, no asumir**: capacidad aproximada por réplica ≈ `hilos_disponibles / espera_síncrona`. Mide latencia de la propia API, nº de respuestas `201` vs `202` y ocupación del pool de hilos durante E2.
**Retira expresamente** la atribución al `pip install` del Dockerfile salvo que muestres evidencia. Documenta la conclusión en `docs/resultados/chaos_E2_hallazgo.md` (qué se observó, qué se concluyó, qué se recomienda: p. ej. reducir `SAGA_SYNC_WAIT_SECONDS`, responder `202` de inmediato, o más réplicas/hilos). Lo medido aquí alimentará las pruebas de carga P2 y P3 de F4b.

## CRITERIOS DE ACEPTACIÓN (muestra la salida)
- [ ] Git separado y `git log` de ambas ramas.
- [ ] `docs/resultados/F4a-auditoria.md` con todas las filas respaldadas por evidencia.
- [ ] Protocolo completo ejecutado con `REPEAT=3`; tabla resumen; stack sano; `make invariants` ⇒ 0.
- [ ] Informes de **A, B, C, D, E2 y S**, todos con las 5 preguntas con cifras y RTO medido vs objetivo.
- [ ] Hallazgo de E2 clasificado (a/b/c) con evidencia y recomendación.
- [ ] `make images`: 0 imágenes nuevas.
- [ ] Ninguna prueba modificada **solo para que pase**: si cambias una aserción, explica por qué con evidencia.

## ENTREGA
Informe con salidas reales, tabla resumen y hallazgos. No fusiones a `main`.

## REGLAS
Evidencia o no existe · no ocultar hallazgos · no modificar pruebas para que pasen · nada destructivo (sin `-v`, sin prune global) · si cambias arquitectura, propón el ADR y detente.
