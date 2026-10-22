# Entorno de medición (F4b Parte 2)

Fecha: 2026-10-22 · Commit base: `7cf7a1a` (tag `f4b1`)

## Hardware y virtualización

| Elemento | Valor |
|---|---|
| Equipo | PC local (Windows 11 Pro) |
| CPU | AMD Ryzen 5 5600G with Radeon Graphics · 6 núcleos / 12 hilos |
| RAM total | 15,4 GB (16 GB) |
| RAM asignada a Docker | 7.995.179.008 bytes ≈ **7,45 GiB** (`docker info .MemTotal`) |
| CPUs visibles a Docker | 12 (`docker info .NCPU`) |
| SO | Microsoft Windows 11 Pro 10.0.26200 build 26200 |
| Docker Desktop | **4.48.0** (207573) |
| Docker Engine | **28.5.1** (cliente y servidor) |
| Docker Compose | v2.40.2-desktop.1 |
| Backend de contenedores | WSL2, kernel 6.18.54.1-microsoft-standard-WSL2 |

## Software de prueba

| Elemento | Versión |
|---|---|
| k6 | `grafana/k6:0.54.0` (contenedor; ver `docs/imagenes.md`) |
| Python (arnés) | 3.13 (venv del repo) |
| PostgreSQL | 16 (contenedor `postgres`) |

## Advertencia

k6, los servicios y PostgreSQL **comparten la misma máquina**. Las cifras son
**comparativas** (1 vs 3 réplicas, V1 vs V2, antes/después) y **no absolutas**:
el techo observado puede ser de la máquina anfitriona y no del diseño.

## Reproducción

```
make build && make up && make seed
make invariants
make perf            # todas las pruebas
make perf PERF=P1    # una prueba
```
