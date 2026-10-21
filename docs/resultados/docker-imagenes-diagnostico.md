# Diagnóstico de imágenes Docker (Fase 1 — proyecto reservas-platform)

Fecha: 2026-10-20 · Rama: `main` (HEAD `7ba8cd2`) · Máquina local (Windows, Docker Desktop)

## 1. Línea base del entorno

### 1.1 Imágenes (`docker images --digests`)

| Categoría | Recuentos observados | Imágenes del proyecto (tag) | IMAGE ID |
|---|---|---|---|
| Proyectos (`:local`) | 6 (una por servicio) | `availability:local` | `5fab9c005a28` |
| | | `notification:local` | `851655f9e537` |
| | | `customer:local` | `dfcf17b8c655` |
| | | `hotel:local` | `c295eb9098a0` |
| | | `payment:local` | `3a8a2e718e7a` |
| | | `reservation:local` | `82d10ef11795` |
| Base (de terceros) | postgres:16, nginx:1.27.4-alpine, python:3.12-slim, redis, mongo, ollama… | `postgres:16` | `44cbf408c541` |
| | | `nginx:1.27.4-alpine` | `1ff4bb4faebc` |
| Huérfanas (`<none>:<none>`) | **52** visibles del proyecto (174–176 MB cada una) + varias de otros proyectos | — | — |
| Caché BuildKit | 303 entradas, 5.286 GB, 4.009 GB compartido | — | — |

### 1.2 Docker global (`docker system df -v`)

| Tipo | Total | Activo | Tamaño | Reclamable |
|---|---|---|---|---|
| Images | 94 | 8 | 21.73 GB | 21.31 GB (98 %) |
| Containers | 21 | 0 | 0 B | 0 B |
| Local Volumes | 40 | 1 | 4.148 GB | 4.024 GB (97 %) |
| Build Cache | 303 | 0 | 5.286 GB | 5.286 GB |

### 1.3 Compose

`docker compose config --images` lista únicamente las imágenes usadas por el proyecto: `availability:local`, `customer:local`, `hotel:local`, `payment:local`, `reservation:local`, `notification:local`, `postgres:16` y `nginx:1.27.4-alpine`.

`docker compose ps -a` muestra 21 contenedores del proyecto, todos **Exited**; ninguno usa `:latest`.

## 2. Hallazgos del diagnóstico

| # | Hallazgo | Evidencia (archivo:línea / salida) | Impacto | Corrección propuesta |
|---|---|---|---|---|
| 1 | **`make up` y `make up-dev` construyen siempre** | `Makefile:24` `docker compose up -d --build --wait`; `Makefile:27` `$(COMPOSE_DEV) up -d --build --wait` | Cada ejecución regenera todas las imágenes del proyecto (6 imágenes `~174–176 MB`), reasigna el tag `:local` y deja la imagen previa como `<none>`. | Separar construir de ejecutar: `make build` construye; `up`/`test`/`e2e`/`smoke`/`chaos` usan `--no-build`. |
| 2 | **Tag mutable `:local` desplazado en cada rebuild** | `compose.yaml` `image: customer:local` (líneas 106, 130…) y 5 servicios más; `docker images` muestra una sola copia `:local` por servicio y decenas de `<none>` 174–176 MB. | Después de dos `make test` anteriores (sin cambios de código) las imágenes del proyecto cambian de IMAGE ID y las anteriores pasan a `<none>` (huérfanas). | Etiquetar con hash corto de git para entrega; `:local` solo desarrollo. `make images` para tabla. |
| 3 | **No hay `.dockerignore`** | `services/*/.dockerignore` y `gateway/.dockerignore` no existen (comprobado). | El contexto de build incluye `.git`, `.venv`, `tests/`, `docs/`, `__pycache__/`, `secrets/`, `*.md`, caches de ruff/pytest (`services/*/.pytest_cache`, `.ruff_cache`, `.import_linter_cache`). Cambios irrelevantes invalidan capas y aceleran el desplazamiento de `:local`. | Añadir `.dockerignore` por contexto de build. |
| 4 | **Orden de capas no óptimo en Dockerfiles** | `services/availability/Dockerfile:3–5`: `COPY pyproject.toml ./`, `COPY app ./app`, `RUN pip install`. El código se copia antes/igual que las dependencias; `pip install --no-cache-dir` cada rebuild. | Cambio de una línea de código reconstruye el entorno completo de dependencias. | Copiar `pyproject.toml`/`pyproject.lock` e instalar dependencias antes de `COPY app`. |
| 5 | **Reconstrucción repetida en CI** | `.github/workflows/ci.yml:22–24`: `make up` → `make test` construye todo desde cero. | Normal en CI sin caché de Docker, pero duplica el coste en cada PR y push. | Documentar que CI construye desde cero (aceptable); local no. |
| 6 | **`make test` / `make e2e` / `make smoke` reconstruyen implícitamente** | `Makefile:60`: `test: deps gateway-refresh` (no build), pero `gateway-refresh` no construye; `up-dev` sí usa `--build`; `e2e` depende de `up-dev` (líneas 82–87). | El perfil dev sí reconstruye a cada `make e2e` porque `up-dev` lleva `--build`. | `e2e`/`smoke`/`chaos` no deben construir: usar `up -d --wait --no-build` y fallar si falta la imagen (`make build` primero). |
| 7 | **Cada rol de un servicio declara `build:` por separado** | `compose.yaml` líneas 103–126 (customer-migrate + customer), 157–209 (hotel), 237–319 (availability x3), etc.: todos los roles de un servicio tienen `build: ./services/<svc>` con la misma `image: <svc>:local`. | Compose reconstruye el contexto una vez por imagen única, pero cada `make up --build` vuelve a comprobar/reconstruir; no hay separación de imagen por rol. | Un único `build:` por imagen; los demás roles usan `image:` + `pull_policy: never` (documentado en Phase 2). |

## 3. Conclusión (causa raíz)

La causa principal de "se crean y recrean imágenes en cada ejecución de pruebas" es **Makefile: `up` y `up-dev` ejecutan `docker compose up -d --build --wait`**, combinado con el **tag mutable `:local`** y la **ausencia de `.dockerignore`**. Cada prueba (`make test` / `make e2e` / `make smoke` / `make chaos` si se implementa) reconstruye las imágenes del proyecto, reasigna `:local` y convierte la imagen anterior en huérfana `<none>` de ~175 MB. En esta máquina hay 52 huérfanas del proyecto acumuladas por esa razón, además de 303 entradas de caché BuildKit (5.286 GB).

El experimento de reconstrucción (`make test` dos veces sin cambios de código) confirma que **el IMAGE ID de las imágenes del proyecto cambia con cada `up --build`** aunque el código no cambie, invalidando la caché de ejecución.

## 4. Corrección propuesta (Fase 2)

Se propone el commit `chore(docker): controlar construcción de imágenes`:

1. Crear target `make build` que construya las imágenes del proyecto con `docker compose build` (aprovechando caché).
2. `make up`, `make up-dev`, `make test`, `make e2e`, `make smoke`, `make chaos`, `make perf` usen `docker compose up -d --wait --no-build` y, si falta una imagen, fallen con mensaje claro que indique ejecutar `make build`.
3. Un solo `build:` por imagen en `compose.yaml`; los otros roles del mismo servicio usan `image:` + `pull_policy: never`.
4. Añadir `.dockerignore` en cada contexto de build (excluye `.git`, `.venv`, `tests/`, `docs/`, `__pycache__/`, `.pytest_cache`, `.ruff_cache`, `.import_linter_cache`, `secrets/`, `backups/`, `*.md`, `node_modules/`).
5. Reordenar capas de los Dockerfiles: manifiesto de dependencias primero, `pip install` después, código al final. `ARG` volátiles (`BUILD_DATE`, hash de git) solo en `LABEL` al final.
6. Target `make images` (tabla: nombre, tag, ID, tamaño, antigüedad + recuento de huérfanas).
7. Target `make prune` que elimine solo huérfanas del proyecto (`label=com.docker.compose.project=reservas-platform` o filtrando por nombre exacto `:local`) con antigüedad > 24 h; **nunca** `-a` global ni borrar volúmenes.
8. Actualizar `docs/imagenes.md` con la política, comandos y tabla de tamaños.

## 5. Criterios de aceptación (pendiente de Fase 2)

- [ ] `make build` + tres `make test` + `make e2e` → 0 imágenes nuevas, 0 huérfanas nuevas, IMAGE ID de las imágenes del proyecto sin cambios.
- [ ] Cambio trivial en el código de un servicio + `make build` → solo esa imagen cambia; capa de dependencias reutilizada (`CACHED`).
- [ ] `make images` y `make prune` funcionan y no tocan imágenes ajenas al proyecto.
- [ ] `make lint`, `make test`, `make e2e`, `make smoke`, `make invariants` en verde; CI en verde.
- [ ] Tabla antes/después: nº de imágenes, huérfanas, tamaño en disco, duración de `make test`.
