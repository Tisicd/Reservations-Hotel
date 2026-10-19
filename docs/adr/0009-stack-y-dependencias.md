# ADR-0009: Stack y dependencias justificadas
**Estado:** Propuesto · **Fase:** F0

Principio: **ninguna dependencia sin una razón medible o verificable.**

| Dependencia | Para qué | Por qué no una alternativa más simple |
|---|---|---|
| Python 3.12 + FastAPI + Uvicorn | API, validación, OpenAPI automático | OpenAPI es la base de los contratos y de los tests de contrato |
| Pydantic (incluida en FastAPI) | Esquemas de `api` | Solo en `api`; el dominio usa `dataclasses` |
| SQLAlchemy 2 (Core) + psycopg 3 | Acceso a PostgreSQL en `infrastructure` | SQL explícito/Core para el `UPDATE` atómico; sin ORM mágico en rutas críticas |
| **Síncrono** (no `async`) | Endpoints y clientes | Menos complejidad; `async` no aporta valor medido en este alcance. Se revisa si F4 muestra un cuello atribuible |
| Alembic | Migraciones versionadas por servicio | Esquema reproducible y revisable en PR (con SQL explícito) |
| httpx | Clientes HTTP con timeouts | Timeouts finos y transporte falso para tests |
| pytest | Pruebas | Estándar |
| **import-linter** (solo desarrollo/CI) | Hace cumplir las capas hexagonales y la pureza del dominio | Convierte la arquitectura en una prueba automática y defendible (probado en F0) |
| ruff (solo desarrollo/CI) | Lint + formato | Una herramienta en lugar de varias |
| k6 | Carga | Umbrales y métricas p95/p99 integradas |
| nginx | Gateway, balanceo, límites, estáticos | Evita añadir Traefik/Kong |
| Docker Compose | Orquestación | Requisito del enunciado; Swarm se analiza, no se usa |
| PostgreSQL 16 | Ver ADR-0002 | — |
| RabbitMQ | **Condicional** (ADR-0004, compuerta G1) | — |
| **Sin**: Redis, Kubernetes, testcontainers, ORM de dominio, framework de eventos, Prometheus (inicial) | — | Sin necesidad medida. Las pruebas de integración usan el PostgreSQL de Compose (perfil `dev`, publicado en 127.0.0.1) |

Logs: JSON con la librería estándar (formatter propio de ~20 líneas) y `X-Request-ID` propagado; sin dependencia adicional.
