# Tamaños de imagen (Docker)

Tabla de tamaños, política de construcción y comandos para controlar la
creación de imágenes Docker del proyecto.

## Política de construcción

- **`make build`** construye las 6 imágenes `:local` (los servicios API: customer,
  hotel, availability, payment, reservation, notification). Las capas de dependencias
  quedan cacheadas y no se invalidan al cambiar el código de `app/`.
- **`make up`, `make up-dev`, `make test`, `make e2e`, `make smoke`, `make chaos`,
  `make perf`** **no construyen**: usan `docker compose up -d --no-build --wait` y
  fallan con un mensaje claro que indica `make build` si alguna imagen `:local`
  faltara. El criterio de aceptación es "0 imágenes nuevas" en ciclos repetidos.
- Separación build/run: CI llama explícitamente `make build` antes de `make up`.
- **Una imagen por servicio, compartida por todos sus roles** (api, migrate, worker,
  relay): un único `build:` en el servicio principal y los demás roles con `image:` +
  `pull_policy: never`. `docker compose build <svc>` sigue construyendo un solo
  servicio.
- `pull_policy: never` evita que Compose intente extraer `customer:local` de un
  registro; los roles migrate/worker usan la imagen ya construida localmente.
- La única fuente de verdad para las dependencias es `pyproject.toml` (leída con
  `tomllib` para generar la capa de `pip install -r deps.txt`, cacheada). No hay
  `requirements.txt` duplicado.
- Las imágenes llevan LABEL `com.reservas.project=reservas-platform`, además del
  `com.docker.compose.project=reservas-platform` que Compose añade por defecto.
- `make prune` nunca toca imágenes de otros proyectos: la limpieza se limita a
  imágenes huérfanas (`dangling`) con el label del proyecto.

## Comandos

| Comando | Qué hace |
|---|---|
| `make build` | Construye las 6 imágenes `:local` (cacheadas). |
| `make images` | Tabla de imágenes del proyecto y recuento de huérfanas (`python scripts/docker_images.py`). |
| `make prune` | Elimina imágenes `dangling` del proyecto filtrando por label. No usa `-a` global. |
| `make up` | Levanta el stack sin rebuild; falla si falta alguna imagen (indica `make build`). |
| `make test` / `make e2e` / `make smoke` | No reconstruyen las imágenes `:local`. |

## Tabla de tamaños

2026-10-21 — valores tras la corrección de Phase 2:

| Imagen | Tamaño | ID |
|---|---|---|
| `availability:local` | 174 MB | 63f349a175b0 |
| `customer:local` | 174 MB | b71d779e133b |
| `hotel:local` | 174 MB | e557d1b4a5d9 |
| `payment:local` | 174 MB | 847f1141a291 |
| `reservation:local` | 176 MB | 123889a53a16 |
| `notification:local` | 174 MB | 89aa9b381f3b |
| `nginx:1.27.4-alpine` (gateway) | 47.9 MB | 1ff4bb4faebc |

Huérfanas legacy del proyecto reclamadas por `make prune`: 52. Ninguna nueva
generada por los ciclos repetidos (`make test` x3 + `make e2e` x2).

## Comportamiento verificado

```
make build                       # 6 imágenes construidas, capas CACHED
make test && make test && make test && make e2e =>
                                 0 imágenes nuevas, 0 huérfanas nuevas, IMAGE ID estables
```

Al cambiar `app/<svc>` y ejecutar `make build`, solo cambia esa imagen; la capa de
dependencias (pip install) aparece como `CACHED` en la salida.

## Notas de optimización (los 6 servicios)

- Multistage (`builder` + `runtime` sobre `python:3.12-slim`).
- Capa de dependencias cacheada: `COPY pyproject.toml` + `pip install -r deps.txt`
  va primero; cambiar `app/` no invalida pip.
- La etapa runtime solo copia `app/`, `migrations/`, `alembic.ini` y el prefijo
  instalado.
- Usuario no-root (`appuser`, uid 10001); sin tests ni `pyproject.toml` en la imagen
  final.
- `HEALTHCHECK` contra `/ready`.
- `.dockerignore` por servicio: excluye `.git`, `.venv/`, `__pycache__/`,
  `tests/`, `docs/`, `*.md`, `secrets/`, `backups/`, caches de herramientas.

## Perfiles de despliegue (F4b)

- `make up` levanta el perfil **dev** (publica admin `8081` y público `8088`);
  `make up-prod` levanta solo el perfil público. El perfil no cambia las
  imágenes: siguen siendo las 6 `:local` + `postgres:16` + `nginx:1.27.4-alpine`.
- La imagen de carga `grafana/k6` (Parte 2) se ejecuta con `docker run --rm` y
  se documenta aparte; no entra en las imágenes del producto.

## Mediciones (2026-10-23)

### Imágenes del producto

| Imagen | Tag | ID | Tamaño | Shared Size | Unique Size |
|---|---|---|---|---|---|
| availability | `local` | `63f349a175b0` | 174 MB | 119.5 MB | 54.65 MB |
| customer | `local` | `b71d779e133b` | 174 MB | 119.5 MB | 54.59 MB |
| hotel | `local` | `e557d1b4a5d9` | 174 MB | 119.5 MB | 54.61 MB |
| payment | `local` | `847f1141a291` | 174 MB | 119.5 MB | 54.66 MB |
| notification | `local` | `89aa9b381f3b` | 174 MB | 119.5 MB | 54.62 MB |
| reservation | `local` | `123889a53a16` | 176 MB | 119.4 MB | 56.29 MB |
| postgres | `16` | `44cbf408c541` | **451 MB** | 78.63 MB | 372.4 MB |
| nginx | `1.27.4-alpine` | `1ff4bb4faebc` | 47.9 MB | 0 B | 47.9 MB |
| python (base) | `3.12-slim` | `df18428df8a0` | 119 MB | 119.4 MB | 0 B |

Fuente: `docker images` y `docker system df -v` (Shared/Unique). Las 6
imágenes comparten la base `python:3.12-slim` (119 MB) y las capas de
dependencias; por eso el tamaño por servicio es 174–176 MB aunque el
incremento único respecto de la base sea ~55 MB.

Imágenes **fuera del producto** usadas para pruebas/escaneo:
`grafana/k6:0.54.0` (72 MB), `aquasec/trivy:0.58.1` (152 MB) y
`zricethezav/gitleaks:v8.24.0` (45.3 MB). No entran en `make images` ni en
`compose.yaml`.

### Multistage vs monoetapa (customer)

Medición única con un `Dockerfile.mono` **temporal, no commiteado** (misma
base y mismas dependencias, una sola etapa sin `COPY --from`):

| Variante | Tamaño |
|---|---|
| Multistage actual | **174 MB** |
| Monoetapa temporal | **198 MB** |

La monoetapa es **24 MB (+13,8 %)** más grande: conserva la caché de pip y
los artefactos de build en la misma imagen, mientras que la multistage copia
solo `/install` a la etapa runtime y descarta el *builder*. El build temporal
requirió `--trusted-host` por el proxy TLS local; la medición de tamaño no se
ve afectada. El Dockerfile temporal se eliminó y la imagen `customer:mono-test`
se borró.

### Contexto de build con y sin `.dockerignore`

Método: `Dockerfile.ctx` temporal (`FROM scratch` + `COPY . /ctx`) y BuildKit
(`transferring context`) con y sin `.dockerignore` del servicio `customer`:

| Contexto | Tamaño |
|---|---|
| Con `.dockerignore` | **1,73 kB** |
| Sin `.dockerignore` | **60,76 kB** |

El `.dockerignore` reduce el contexto **~35×** al excluir `tests/`, caches
(`__pycache__`, `.pytest_cache`, `.ruff_cache`) y metadatos. Los archivos
temporales se borraron; no hay cambios commiteados.

### CVEs

El escaneo de las 6 imágenes está en `docs/resultados/seguridad-trivy.txt`
(47 HIGH / 0 CRITICAL por imagen; 44 de la base Debian y 3 de `starlette`).
Ver `docs/seguridad.md` para el detalle y los pendientes.
