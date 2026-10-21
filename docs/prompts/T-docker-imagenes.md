# Prompt para OpenCode: diagnosticar y controlar la creación de imágenes Docker

> Pegar desde "ROL". Rama: `chore/docker-imagenes`. Dos commits: diagnóstico (solo informe) y corrección.

---

## ROL
Ingeniero de plataforma. Tarea: averiguar **por qué se crean y recrean imágenes Docker en cada ejecución de pruebas** y corregirlo sin romper nada. **Primero mide, después cambia.** Si la causa no es la esperada, dilo; no apliques arreglos "por si acaso".

## LEE ANTES DE ACTUAR
`docs/03-estado-del-proyecto.md`, `compose.yaml`, `compose.dev.yaml`, `Makefile`, `.github/workflows/ci.yml`, los `Dockerfile` de `services/*` y `gateway/`, `docs/imagenes.md`, `docs/variables.md`.

## RESTRICCIONES DE SEGURIDAD (obligatorias)
- **Prohibido** `docker system prune -a`, `docker image prune -a`, `docker volume prune` y borrar imágenes/volúmenes que no pertenezcan a este proyecto. Hay otros proyectos en esta máquina.
- Limita toda limpieza a este proyecto con filtros por etiqueta (`label=com.docker.compose.project=reservas-platform`) o por nombre exacto de imagen del proyecto.
- **No** borres el volumen `pgdata` ni `secrets/`.
- No cambies el comportamiento funcional de ningún servicio.

## FASE 1: DIAGNÓSTICO (no modifiques archivos; entrega un informe `docs/resultados/docker-imagenes-diagnostico.md`)
1. **Línea base** (guarda la salida de cada comando):
   `docker images --digests`, `docker images --filter dangling=true`, `docker system df -v`, `docker builder du`, `docker compose config --images`, `docker compose ps -a`.
2. **Cuántas imágenes hay y de qué tipo:** cuenta por repositorio; separa (a) imágenes del proyecto (`availability:local`, …), (b) imágenes base (`postgres`, `nginx`, `python`), (c) **huérfanas `<none>`** (dangling), (d) cachés de BuildKit.
3. **Experimento de reconstrucción** (sin cambiar código): ejecuta **dos veces seguidas** `make test` (y luego `make e2e`) y, antes y después de cada ejecución, registra: nº de imágenes, nº de dangling, `docker system df`, duración, y **si algún IMAGE ID de las imágenes del proyecto cambió**. Un cambio de ID sin cambio de código = la caché no se reutiliza.
4. **Busca la causa en el código** y clasifica cada hallazgo con evidencia (archivo:línea):
   - Objetivos del `Makefile`/scripts de prueba que ejecutan `docker compose up --build`, `build --no-cache`, `--force-recreate`, `down --rmi`, `docker build` o `docker compose build` en cada `test`/`e2e`/`smoke`/`chaos`.
   - Pruebas (pytest/e2e/infra) que **construyen o recrean** imágenes o contenedores como parte del test.
   - `compose.yaml`: varios servicios con `build:` apuntando al **mismo contexto** (p. ej. `availability`, `availability-migrate`, `availability-worker`, `reservation-relay`) y construyéndose por separado en lugar de compartir una sola imagen (`image:` + un único `build:`; los demás solo `image:` con `pull_policy: never`).
   - **Falta de `.dockerignore`** o uno incompleto (`tests/`, `docs/`, `.git/`, `.venv/`, `__pycache__/`, `secrets/`, `backups/`, `*.md`, `node_modules/`): el contexto cambia en cada ejecución e invalida la caché.
   - Orden de capas en los Dockerfile: `COPY` del código **antes** de instalar dependencias (invalida la caché de `pip install` con cada cambio); falta de `pyproject`/lock copiado primero.
   - Argumentos de build que cambian siempre (`ARG BUILD_DATE`, hash de git, `timestamp`) colocados **antes** de capas costosas.
   - Etiquetas mutables (`:local`) que al reconstruirse dejan la imagen anterior como `<none>`.
   - CI: construcciones repetidas sin caché (esto es normal en CI; anótalo, no lo "corrijas" si es solo CI).
   - Si la réplica `availability x3` genera imágenes distintas o solo contenedores (debe ser **una** imagen, tres contenedores).
5. **Conclusión del diagnóstico:** tabla `causa → evidencia → impacto (imágenes/tiempo) → corrección propuesta`, ordenada por impacto. **Detente aquí y entrega el informe** antes de la fase 2.

## FASE 2: CORRECCIÓN (tras el informe; commit `chore(docker): controlar construcción de imágenes`)
Aplica **solo** lo que el diagnóstico justifique. Criterios de diseño:
1. **Separar construir de ejecutar.** `make build` construye las imágenes (aprovechando caché). `make up`, `make test`, `make e2e`, `make smoke`, `make chaos` y `make perf` **no construyen**: usan `docker compose up -d --wait --no-build` y, si falta una imagen, fallan con un mensaje claro que indica `make build`. (Si prefieres que `make up` construya solo lo que falta, documenta por qué.)
2. **Una imagen por servicio compartida por sus roles** (api, migrate, worker, relay): un único `build:` por imagen y el resto con `image:` + `pull_policy: never`.
3. **`.dockerignore`** por contexto de build, excluyendo todo lo que no entra en la imagen.
4. **Dockerfiles con capas estables:** manifiesto de dependencias primero → instalar → código al final; sin `ARG` volátiles antes de las capas costosas (si necesitas metadatos de versión, ponlos en `LABEL` **al final**).
5. **Limpieza controlada:** objetivo `make prune` que elimina **solo** imágenes huérfanas (`dangling`) y caché de build de **este proyecto** con antigüedad > 24 h (`docker image prune -f --filter "label=com.docker.compose.project=reservas-platform"` si las imágenes llevan esa etiqueta; si no, etiqueta las imágenes del proyecto con `LABEL com.reservas.project=reservas-platform` y filtra por ella). **Nunca** `-a` global.
6. **`make images`:** tabla de las imágenes del proyecto (nombre, tag, ID, tamaño, antigüedad) y recuento de huérfanas.
7. **Pruebas que construyen:** si un test necesita recrear contenedores (p. ej. persistencia/caos), que use `rm -sf` + `up --no-build`, nunca `--build`.
8. Mantener el tag `:local` solo para desarrollo; en CI y en la entrega, documentar el tag con el hash corto de git **sin** que invalide caché local.
9. Documentar en `docs/imagenes.md`: política de construcción, comandos (`make build|images|prune`) y tabla actual de tamaños.

## CRITERIOS DE ACEPTACIÓN (muestra la salida, antes y después)
- [ ] Informe de diagnóstico con la causa raíz y evidencia.
- [ ] **Experimento repetido tras la corrección:** `make build` seguido de **tres** `make test` + `make e2e` ⇒ **0 imágenes nuevas, 0 huérfanas nuevas, IMAGE ID de las imágenes del proyecto sin cambios**.
- [ ] Tras un cambio trivial en el código de **un** servicio y `make build`, solo **esa** imagen cambia (las demás conservan su ID); la capa de dependencias se reutiliza (`CACHED` en la salida).
- [ ] `make images` y `make prune` funcionan y **no tocan** imágenes ajenas al proyecto (demuéstralo listando antes/después).
- [ ] `make lint`, `make test`, `make e2e`, `make smoke`, `make invariants` en verde; CI en verde.
- [ ] Tabla final antes/después: nº de imágenes, huérfanas, tamaño en disco, duración de `make test`.

## ENTREGA
PR con la plantilla; informe de diagnóstico y tabla antes/después. No fusiones a `main`.

## REGLAS
Medir antes de cambiar · cambios mínimos · nada destructivo fuera del proyecto · si algo es ambiguo, pregunta.
