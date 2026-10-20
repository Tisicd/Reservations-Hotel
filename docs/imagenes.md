# Tamaños de imagen (Docker)

Tabla de tamaños de las imágenes construidas. Se actualiza al cerrar cada
servicio con `docker images`.

| Imagen | Tamaño | Comando de medida | Fecha |
|---|---|---|---|
| `availability:local` | 174 MB | `docker images availability:local --format "{{.Size}}"` | 2026-10-19 |

Notas de optimización aplicadas en `services/availability/Dockerfile`:
- Multistage (`builder` + `runtime` sobre `python:3.12-slim`).
- `pip install --prefix=/install .` en la etapa de builder; la runtime solo copia
  el prefijo instalado + `app/`, `migrations/` y `alembic.ini`.
- Usuario no-root (`appuser`, uid 10001); sin archivos de test ni `pyproject.toml`
  en la imagen final.
