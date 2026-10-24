# Prompt para OpenCode: F5 documentación, trazabilidad, ensayo desde cero y entrega

> Rama: `docs/f5-entrega`, desde `main` con `feat/f4c-carga-cierre` y `feat/f3-frontend` ya fusionadas (CI verde). **Tres hitos con commit propio.** Tope orientativo: 4 h. **Regla central: no inventes cifras ni hechos.** Toda cifra, resultado o afirmación técnica debe enlazar a su archivo de evidencia (`docs/resultados/...`, ADR, código). Si falta un dato, escribe `PENDIENTE: <qué falta y dónde obtenerlo>` y avísame al final; no lo rellenes.

---

## ROL
Ingeniero de software con rol de redactor técnico y de verificador. Arquitectura, pruebas y resultados ya existen; tu trabajo es **ordenarlos, completarlos con rigor y comprobar que todo se reproduce desde cero**.

## LEE
`docs/03-estado-del-proyecto.md`, `docs/01-enunciado.md` (14 puntos), `docs/fases/F5-entrega.md`, `docs/informe/ESTRUCTURA.md`, `docs/adr/*`, `docs/resultados/REPORTE.md` y los informes individuales, `docs/imagenes.md`, `docs/variables.md`, `docs/manual.md` (borrador de F3), `docs/proceso/*`, `compose.yaml`, `Makefile`.

## HITO A: documentos técnicos (commit `docs: manual, seguridad, producción, swarm, imágenes, variables`)
1. **`docs/manual.md`** (completo, para un tercero): requisitos (WSL2/Docker Desktop con ≥ 6 GB asignados, `make`, `git`, Python para las pruebas), instalación desde cero, `make build && make up && make seed`, tabla de **todos** los comandos (`up`, `up-prod`, `test`, `e2e`, `smoke`, `invariants`, `chaos`, `perf`, `report`, `backup`, `restore`, `images`, `prune`, `clean`, `clean-all`), uso del frontend (los 3 flujos de demo), cómo leer los reportes, **solución de problemas** (puertos ocupados, imagen faltante ⇒ `make build`, arranque en frío ≈ 2 min, 429 por límites, memoria de Docker, `make clean-all`), y estructura del repositorio. **Cada comando que documentes debe haberse ejecutado en el Hito C.**
2. **`docs/seguridad.md`** (punto 12): qué se expone y qué no (tabla de puertos y rutas del gateway, con la prueba que lo demuestra), redes `internal`, secretos por archivo (`*_FILE`), contenedores no-root/`read_only`/`cap_drop`/límites, límites del gateway (**con la evidencia de P4**), cabeceras y CSP del frontend, idempotencia como control de integridad. **Tabla de amenazas** con columnas `amenaza | qué se implementó | evidencia | qué NO resuelve`: DNS/DDoS volumétrico (no lo resuelve Compose ni escalar réplicas), saturación de conexiones, agotamiento de recursos, credenciales, dependencias/imágenes, inyección. Si hay red, ejecuta **una vez** un escaneo de imágenes (`docker run aquasec/trivy:<tag fijado>`) y un escaneo de secretos en el repo (`gitleaks` en contenedor) y reporta los **conteos reales**; ambas herramientas quedan **fuera** de las imágenes del producto. Si no hay red, decláralo.
3. **`docs/produccion.md`**: tabla `limitación observada → cambio para producción → por qué`, apoyada en hallazgos medidos (PostgreSQL único y TTD ≈ 93 s por `retries=12`; backup por BD no consistente entre servicios y RPO dependiente de backup manual; saga síncrona de `reservation` que domina la latencia ⇒ `202` inmediato; cola durable con *dead-letter* y alarma; réplicas de BD y PITR; multinodo; observabilidad (métricas, trazas, alertas por SLO); TLS y autenticación; WAF/CDN; gestión de secretos).
4. **`docs/swarm.md`** (punto 10): análisis, **no implementado salvo que lo pruebes**. Qué servicios serían candidatos a réplicas y por qué (availability ya x3; `reservation` API; `payment`; `notification`; `customer`/`hotel`), qué workers admiten varias réplicas (leases y `SKIP LOCKED`) y cuáles necesitan cuidado, por qué **no** `postgres`; qué cambia al migrar (sin `build:`, registro de imágenes, `deploy.replicas`/`update_config`/`restart_policy`/`resources`, secretos de Swarm, redes *overlay*, `depends_on` no aplica ⇒ la resiliencia ya depende de reintentos y `/ready`). Incluye un fragmento ilustrativo marcado **"no ejecutado"**.
5. **`docs/imagenes.md`**: completa lo `_completar_` con mediciones: tag exacto y tamaño de `postgres`, *Shared/Unique Size* de `docker system df -v`, y una **única medición** de la variante monoetapa de un servicio contra la multistage actual (Dockerfile temporal **sin commitear**) y del contexto de build con y sin `.dockerignore`.
6. **`docs/variables.md` verificable:** crea `scripts/check_vars.py` (biblioteca estándar) que compara las variables de entorno leídas por `config.py` de cada servicio y las del `compose.yaml` con las documentadas y falla si falta alguna; añade `make check-docs`. Corrige lo que revele.
7. **ADR:** todos en estado coherente (Aceptado/Implementado). Añade **ADR-0011** que registra la decisión G1 (**RabbitMQ no se implementa**: outbox + relay + inbox cumple I6, sin problema medido; se documenta como evolución) y las enmiendas ya hechas (plazo de `CANCELLING`, 429 del gateway, listener admin sin límites).

## HITO B: trazabilidad, README e informe borrador (commit `docs: trazabilidad, README e informe borrador`)
1. **Trazabilidad** en `docs/01-enunciado.md`: tabla de los **14 puntos** → evidencia concreta (archivo, comando, informe), con ✔ solo si existe y se ejecutó.
2. **`README.md` final:** qué es, diagrama de arquitectura (texto/mermaid), *quickstart* de 5 líneas, tabla de comandos, resumen de hallazgos clave con enlaces, mapa de documentación, limitaciones.
3. **`docs/informe/INFORME.md` (borrador)** siguiendo `docs/informe/ESTRUCTURA.md`. Redacta **solo** las secciones que se apoyan en evidencia existente: 2 (negocio), 4 (arquitectura), 5 (decisiones tecnológicas), 6 (contratos y flujo), 7 (resiliencia y fallos: tablas y hallazgos reales), 8 (rendimiento: hipótesis vs resultado, limitaciones), 9 (seguridad), 11 (manual: resumen y enlace), 12 (evolución), 13 (limitaciones) y el anexo de trazabilidad. **Deja con `PENDIENTE (persona)`** las secciones 1 (resumen), 3 (matriz de alternativas), 10 (costos) y 14 (conclusión): requieren juicio y precios vigentes. Cada afirmación numérica lleva su enlace.
4. **`docs/RELEASE.md`:** contenido de la entrega, cómo reproducirla y **lista honesta de limitaciones y hallazgos abiertos** (B intermitente de 2,41 s; objetivo de TTD de S no cumplido; P2 y P5 no ejecutados; resultados comparativos de una sola máquina; backup en caliente sin garantía de consistencia entre servicios; RPO dependiente de ejecutar `make backup`).

## HITO C: ensayo desde cero y entrega (commit `docs(resultados): ensayo desde cero` + tag)
1. Detén y limpia el stack actual (`make down`; **no** borres nada fuera del proyecto). Clona el repositorio en un **directorio temporal nuevo** (otro nombre ⇒ otro `COMPOSE_PROJECT_NAME`, así que el borrado de volúmenes del escenario E3 solo afecta a esa copia).
2. En esa copia, **sin intervención manual**, ejecuta en orden y cronometra: `make build && make up && make seed && make test && make e2e && make smoke && make invariants && make check-docs && CHAOS_ALLOW_VOLUME_DELETE=1 make chaos && make perf && make report`. Si `make perf` completo no cabe en el tiempo, ejecuta `PERF=P1` y `PERF=P3b` y declara el recorte.
3. Registra en `docs/resultados/ensayo-desde-cero.md`: comandos, duración de cada paso, salida resumida, **cualquier paso manual que hizo falta** y cualquier fallo. **Si algo falla, corrígelo y repite desde el principio** hasta lograr una pasada limpia (o declara la causa si es ajena al proyecto).
4. Con una pasada limpia y CI verde en `main`: propón el tag **`v1.0-entrega`**, un `git archive` (zip) sin `secrets/`, `backups/`, `.env` ni `.venv`, y comprueba con `gitleaks` que no hay secretos en el repo ni en el zip.

## CRITERIOS DE ACEPTACIÓN (muestra salidas)
- [ ] `make check-docs` en verde (variables documentadas = variables usadas).
- [ ] Todos los comandos del manual aparecen en el log del ensayo.
- [ ] Tabla de trazabilidad con los 14 puntos y evidencia real.
- [ ] `INFORME.md` con `PENDIENTE (persona)` solo en las secciones 1, 3, 10 y 14, y **cero cifras sin enlace**.
- [ ] Ensayo desde cero completo y documentado, con duraciones.
- [ ] Lista de `PENDIENTE` restantes entregada al final.
- [ ] `make invariants` ⇒ 0; `make images`: mismas imágenes del producto, 0 huérfanas.

## ENTREGA
PR con la plantilla; informe con archivos, salidas y los `PENDIENTE`. No fusiones a `main`.

## REGLAS
No inventar cifras · enlazar la evidencia · declarar lo no hecho · nada destructivo fuera del proyecto · sin dependencias nuevas en imágenes del producto · si cambias arquitectura, propón el ADR y detente.
