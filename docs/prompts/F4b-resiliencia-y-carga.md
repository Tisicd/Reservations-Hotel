# Prompt para OpenCode: F4b (E1, E3, E4, backup/restore, carga k6, reporte)

> Dos partes con ramas y PR propios. **Parte 1:** `feat/f4b-resiliencia` (Paso 0 + E1 + E4 + backup/restore + E3). **Parte 2:** `feat/f4b-carga` (k6 + reporte). Pega una parte a la vez. Reglas de honestidad de `F4a-caos.md` siguen vigentes: **evidencia o no existe**, aserciones duras solo de integridad, hallazgos nunca ocultos.

---

## ROL
Ingeniero de fiabilidad (SRE). Arquitectura aceptada. No rediseñes servicios; los defectos se reportan como hallazgos y se corrigen en commit aparte.

## LEE
`docs/03-estado-del-proyecto.md`, `docs/fases/F4-fallos-carga-reportes.md`, `docs/prompts/F4a-caos.md` (arnés y reglas de medición), `docs/resultados/F4a-cierre.md`, `docs/fases/F0-negocio-y-resiliencia.md` §4, `gateway/conf.d/default.conf`, `docs/adr/0007`, `docs/proceso/modos-de-caida.md`.

# PARTE 1: resiliencia (rama `feat/f4b-resiliencia`)

## PASO 0: validez de las mediciones de F4a (commit `fix(chaos): validar mediciones y atribución de errores`)
Algunas cifras de F4a **no son físicamente plausibles** y una atribución está contaminada. Antes de añadir escenarios:
1. **D (RTO 0,06–0,08 s):** recrear el contenedor `postgres` (`rm -sf` + `up -d --no-build`) no puede tardar 60 ms. Etiqueta "D/stop" sugiere que se hizo `stop/start` y no recreación. Verifica qué se ejecutó, **corrige para que D sea una recreación real** y define RTO como: desde la eliminación del contenedor hasta el **primer éxito de escritura sostenido** del canario (≥3 muestras seguidas).
2. **S (TTD ≈ 0,1 s):** Docker no marca `unhealthy` en 0,1 s; hace falta `interval × retries` del healthcheck. Define **TTD = instante de la caída → primera transición a `unhealthy`** tomada de `docker events --filter event=health_status` (o de las marcas de `Health.Log`), y **TTR = vuelta a `healthy`**. El 0,1 s medido probablemente es el primer 503; si es así, repórtalo como "tiempo hasta primer error" (otra métrica) y mide TTD correctamente.
3. **E2 "n/a (síncrona)":** el hallazgo de F4a dice que 10 de 20 solicitudes concurrentes recibieron **503 del gateway** (`limit_conn 10`). Explica cómo E2 pudo terminar 20/20 `CONFIRMED` (¿reintentos? ¿otro listener?) y registra el tiempo hasta estado final (p50/p95/máx.) por reserva.
4. **Atribución de errores:** el `503` del `limit_conn` es indistinguible del `503` fail-closed de los servicios. Cambia el gateway a **`limit_conn_status 429` y `limit_req_status 429`** (actualiza ADR-0007 y `docs/05-contratos-api.md` §1: 429 = límite del gateway), y haz que el arnés **clasifique y reporte por separado**: `429 gateway`, `503 servicio (fail-closed)`, `502/504 upstream`, `timeout cliente`. **Los 429 no cuentan como impacto de la falla.** El tráfico de fondo de los escenarios debe mantenerse bajo los límites o usar el listener admin (sin límites). **Vuelve a ejecutar B (kill y kill9) ×3** y reporta si el 96,4 % "crudo" venía de límites y no de la falla.
5. **Higiene de operación:** `make up` debe levantar el perfil de desarrollo (con listener admin) y `make seed` debe funcionar **inmediatamente después** (`make build && make up && make seed`); el perfil sin admin pasa a `make up-prod`. Actualiza README, `docs/imagenes.md`, `03-estado` y el protocolo de caos.
6. **B/kill repetición 1 (2,42 s > 2 s):** captura la línea de tiempo (logs de acceso/error de nginx, TTL del DNS dinámico, `proxy_connect_timeout`) y determina la causa de la primera caída lenta. Si hay una mitigación simple (p. ej. `resolver … valid=1s`, `proxy_connect_timeout`, `proxy_next_upstream_timeout`), aplícala y **mide antes/después ×5**. Máximo 1 h; si no, documenta como hallazgo abierto.
7. **Regla de plausibilidad para todo informe:** cada RTO/TTD debe incluir la **línea de tiempo cruda** (última muestra buena → primera muestra mala → primera buena sostenida) y, si es menor que la resolución del canario (0,5 s), una explicación.
8. Versiona `docs/prompts/F4a-cierre.md` y fusiona `feat/f4a-caos` tras CI.
Actualiza `docs/resultados/F4a-cierre.md` con una **sección "Correcciones"**: qué cifras cambiaron y por qué.

## ESCENARIOS NUEVOS (mismo arnés, informes con 5 preguntas, RTO medido vs objetivo, línea de tiempo cruda)
**E1: PostgreSQL cae en plena carga de escritura** (modo A: `docker kill` + reinicio por el arnés tras N s; modo B: `pkill -9` interno con política de reinicio). Tráfico de reservas continuo con sagas en curso (incluye algunas `slow`). Aserciones duras:
- **Durabilidad de lo reconocido:** todo `reservation_id` que el cliente vio con `201 CONFIRMED` **antes** de la caída existe tras la recuperación con el mismo estado (esta es la verdadera comprobación de I7: *ack ⇒ persistido*).
- Invariantes I1–I5 en **0**; un solo cobro por reserva; **ningún 2xx** durante la caída para operaciones que no se confirmaron (solo 503 fail-closed).
- Toda reserva en vuelo termina en estado estable; `MANUAL_REVIEW` esperado 0 (si aparece, explicarlo).
Métricas: RTO a escritura exitosa, tiempo de recuperación de WAL (extrae del log de PostgreSQL), reservas recuperadas por el worker, errores por clase. **×3 por modo.**
**E4: reinicio ordenado de PostgreSQL** (`docker compose restart postgres`) con servicios activos. Aserciones: los servicios **no se reinician** (`RestartCount` igual), vuelven a `ready` solos. Métrica: tiempo de reconexión por servicio. Compara con E1 (abrupto) en una tabla.

## BACKUP Y RESTAURACIÓN (`scripts/backup.sh`, `scripts/restore.sh`, `make backup`, `make restore`)
- `backup`: `pg_dump -Fc` de **cada** BD a `backups/<timestamp>/` (ignorado por git) con manifiesto (hora, tamaños, hash).
- `restore <dir>`: detiene servicios de aplicación y workers (no `postgres`), restaura cada BD (`pg_restore --clean --if-exists --no-owner` con el rol dueño correcto), verifica versión de migraciones y vuelve a levantar. Cronometra de principio a fin.
**E3: pérdida del volumen.** Salvaguarda: solo corre con `CHAOS_ALLOW_VOLUME_DELETE=1` y **únicamente** borra el volumen cuyo nombre pertenece al proyecto (verifica el prefijo y la etiqueta Compose antes). Pasos: tráfico → `backup` en T0 → crear N reservas **después** → eliminar `postgres` y su volumen → `up postgres` (el `init-db.sh` recrea roles y BDs) → `restore` → arrancar servicios. Mide:
- **RTO de restauración** (desde el borrado hasta servir tráfico con invariantes en 0) vs objetivo 15 min.
- **RPO observado**: reservas creadas después del backup que se perdieron (N) y el intervalo de tiempo equivalente. No se oculta ni se "arregla": es la brecha entre RPO objetivo y realidad.
- **Variante A (backup en reposo):** detener escrituras antes del backup ⇒ invariantes **0** tras restaurar (aserción dura).
- **Variante B (backup en caliente):** backup con tráfico activo. **Observacional:** `pg_dump` por BD **no** es una instantánea consistente entre servicios; ejecuta `make invariants` tras restaurar y **reporta las violaciones** (p. ej. cobro sin reserva, hold sin reserva) y cómo las resuelven los workers de recuperación/reconciliación o si requieren intervención. Es un hallazgo de diseño, no un fallo del arnés.
Documenta el procedimiento en `docs/proceso/backup-restore.md`.

## CRITERIOS DE ACEPTACIÓN (Parte 1; muestra salidas)
- [ ] Paso 0 completo con el antes/después de D, S, E2 y B, y la sección "Correcciones".
- [ ] `make build && make up && make seed` funciona seguido; `make up-prod` existe.
- [ ] E1 (modos A y B), E4 y E3 (variantes A y B) ejecutados **×3** con informes completos; aserciones duras en verde; invariantes 0 (salvo la variante B de E3, donde se reportan).
- [ ] `docs/resultados/F4b-resiliencia.md` con tabla `escenario | integridad | RTO medido | objetivo | ¿cumplido? | repeticiones | hallazgos`.
- [ ] `make images`: 0 imágenes nuevas; stack sano al final.
**Regla de recorte (Parte 1):** obligatorios Paso 0 (1, 2, 4, 5), E1 y E3-A. Recortables en este orden: B-mitigación (6), E4, E3-B, E2 (3).

# PARTE 2: carga y reporte (rama `feat/f4b-carga`)

## PREPARACIÓN
- **k6 sin instalarlo:** `make perf` ejecuta la imagen `grafana/k6:<tag fijado>` con `docker run --rm`, scripts montados desde `tests/perf/` y `host.docker.internal` como destino (documenta en `docs/imagenes.md`; no entra en las imágenes del producto).
- **Límites del gateway:** son **por IP** y todas las pruebas salen de una sola IP. Para medir capacidad **de los servicios** usa el listener admin sirviendo `/api/*` **sin `limit_*`** (documéntalo en ADR-0007). Solo P4 usa el listener público.
- Datos de prueba: inventario holgado vía `PUT /inventory` (admin) en un hotel/habitaciones dedicados; semilla fija; fechas repartidas.

## PRUEBAS (`tests/perf/*.js` + `tests/perf/run.py` orquestador; resultados JSON + `docs/resultados/perf_<ID>.md`)
| ID | Prueba | Diseño | Qué se responde |
|---|---|---|---|
| **P1** | Lectura de disponibilidad, **1 vs 3 réplicas** | `ramping-arrival-rate` (modelo abierto) hasta saturar; escalar con `--scale availability=N` y refrescar el DNS del gateway (`make gateway-refresh`) | rps máx. sostenible con p95 < 300 ms y errores < 1 %; ¿escala la lectura? |
| **P3** | **Contención** por un mismo cupo | Variante 1: 200 intentos concurrentes sobre la **misma** habitación/noches con `K` unidades. Variante 2: mismos intentos **repartidos** en 50 habitaciones/noches. 1 vs 3 réplicas de `availability` | Exactamente `K` `CONFIRMED` (aserción dura + invariantes); latencia y 503 por *lock timeout*; ¿la escritura escala con réplicas? (hipótesis: **no** en la variante 1) |
| **P2** | Mezcla 90 % lectura / 10 % reservas; variante con 10 % de pagos `slow` | Carga constante realista | Latencia por tipo; **acoplamiento** entre la espera síncrona de la saga y el resto (¿se degradan las lecturas?) |
| **P5** | Rampa hasta saturación | `ramping-arrival-rate` sobre la mezcla | **Dónde está el cuello**: CPU por contenedor, conexiones en PostgreSQL (`pg_stat_activity`), timeouts de pool, `limit_*`, hilos |
| **P4** | Sobre el límite público | Listener público, ráfaga sobre `limit_req`/`limit_conn` | 429 sin degradar a otros clientes (canario paralelo por el listener admin) |
**Protocolo:** calentamiento 20 s; **3 repeticiones**; hardware y versiones registrados (`docker info`, CPU, memoria); **umbrales definidos antes** en `tests/perf/thresholds.json`; muestreo de `docker stats` y conexiones de PostgreSQL durante la prueba; `make invariants` tras toda prueba de escritura. Resultados **comparativos** (k6 y servicios comparten máquina): dilo en cada informe.

## REPORTE (`make report` → `docs/resultados/REPORTE.md`, `scripts/report.py` solo con biblioteca estándar)
Entorno · tabla de escenarios de caos (A–D, E1–E4, S) con integridad, RTO/RPO **objetivo vs medido** y repeticiones · tablas de carga · **comparativa 1 vs 3 réplicas separando lectura y escritura** · lista automática de **hallazgos** (objetivos incumplidos, anomalías, atribuciones) · sección "Conclusiones" con encabezados para que las redactes tú. Rellena `docs/fallos.md` con la tabla y enlaces a cada informe.

## CRITERIOS DE ACEPTACIÓN (Parte 2)
- [ ] `make perf` y `make report` reproducibles desde `make clean-all && make build && make up && make seed`.
- [ ] P1 y P3 con 1 y 3 réplicas ×3, tabla comparativa y conclusión **honesta** (si 3 réplicas no mejora la escritura, se dice y se explica con las métricas de PostgreSQL).
- [ ] P2, P5 con identificación del cuello de botella apoyada en datos; P4 con 429 observados.
- [ ] `REPORTE.md` generado con todas las secciones; `docs/fallos.md` completo.
- [ ] `make images` sin cambios (la imagen de k6 se documenta aparte).
**Regla de recorte (Parte 2):** obligatorios P1, P3 y `make report`. Recortables en este orden: P4, P5, P2.

## ENTREGA
Cada parte con PR y plantilla; informe con salidas reales, tabla resumen y hallazgos. No fusiones a `main`.

## REGLAS
Evidencia o no existe · plausibilidad de cada cifra · aserciones duras solo de integridad · los 429 no son impacto de la falla · nada destructivo fuera del proyecto (el borrado de volumen solo con salvaguarda explícita) · no modificar pruebas para que pasen · si cambias arquitectura, propón el ADR y detente.
