# Tamaños de imagen (Docker)

Tabla de tamaños de las imágenes construidas. Se actualiza al cerrar cada
servicio con `docker images`.

| Imagen | Tamaño | Comando de medida | Fecha |
|---|---|---|---|
| `availability:local` | 174 MB | `docker images availability:local --format "{{.Size}}"` | 2026-10-19 |
| `payment:local` | 174 MB | `docker images payment:local --format "{{.Size}}"` | 2026-10-20 |
| `reservation:local` | 176 MB | `docker images reservation:local --format "{{.Size}}"` | 2026-10-20 |
| `customer:local` | 174 MB | `docker images customer:local --format "{{.Size}}"` | 2026-10-20 |
| `hotel:local` | 174 MB | `docker images hotel:local --format "{{.Size}}"` | 2026-10-20 |
| `notification:local` | 174 MB | `docker images notification:local --format "{{.Size}}"` | 2026-10-20 |
| `nginx:1.27.4-alpine` (gateway) | 47.9 MB | `docker images nginx:1.27.4-alpine --format "{{.Size}}"` | 2026-10-20 |

Notas de optimización aplicadas en `services/availability/Dockerfile`:
- Multistage (`builder` + `runtime` sobre `python:3.12-slim`).
- `pip install --prefix=/install .` en la etapa de builder; la runtime solo copia
  el prefijo instalado + `app/`, `migrations/` y `alembic.ini`.
- Usuario no-root (`appuser`, uid 10001); sin archivos de test ni `pyproject.toml`
  en la imagen final.

Notas de optimización aplicadas en `services/payment/Dockerfile`:
- Mismo patrón multistage (`builder` + `runtime` sobre `python:3.12-slim`).
- `pip install --prefix=/install .` en la etapa de builder; la runtime solo copia
  el prefijo instalado + `app/`, `migrations/` y `alembic.ini`.
- Usuario no-root (`appuser`, uid 10001); sin archivos de test ni `pyproject.toml`
  en la imagen final.

Notas de optimización aplicadas en `services/reservation/Dockerfile`:
- Mismo patrón multistage (`builder` + `runtime` sobre `python:3.12-slim`).
- `pip install --prefix=/install .` en el builder; la runtime solo copia el prefijo instalado + `app/`, `migrations/` y `alembic.ini`.
- Usuario no-root (`appuser`, uid 10001); sin tests ni `pyproject.toml` en la imagen final.

Notas de optimización aplicadas en `services/customer/Dockerfile` y `services/hotel/Dockerfile`:
- Mismo patrón multistage (`builder` + `runtime` sobre `python:3.12-slim`), usuario no-root (uid 10001) y `HEALTHCHECK` contra `/ready`.
- La runtime copia solo el prefijo instalado + `app/`, `migrations/` y `alembic.ini`.