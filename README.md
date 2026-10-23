# Plataforma de reservas: microservicios, alta disponibilidad y recuperación ante fallos
Caso 2 · Universidad Central del Ecuador · Programación distribuida

**Estado:** F0 (diseño) en revisión. El README completo (instalación, uso, pruebas) se escribe en F5.

## Qué es
Plataforma de reservas de hoteles basada en 6 microservicios Docker, con foco en **integridad del negocio** (sin sobreventa, sin cobros duplicados), **fallos controlados** y **evidencia automatizada** de qué funciona, qué falla y cómo se recupera.

## Por dónde empezar a leer
1. [`docs/01-enunciado.md`](docs/01-enunciado.md): qué se pide.
2. [`docs/fases/F0-negocio-y-resiliencia.md`](docs/fases/F0-negocio-y-resiliencia.md): negocio, invariantes, estados, fallos, RTO/RPO.
3. [`docs/04-arquitectura.md`](docs/04-arquitectura.md) y [`docs/adr/`](docs/adr/README.md): cómo está construido y por qué.
4. [`docs/05-contratos-api.md`](docs/05-contratos-api.md): contratos entre servicios.
5. [`docs/02-plan.md`](docs/02-plan.md) y [`docs/fases/`](docs/fases/README.md): plan y fases.
6. [`docs/informe/ESTRUCTURA.md`](docs/informe/ESTRUCTURA.md): informe escrito de entrega.

## Comandos (disponibles desde F1)
`make up` · `make test` · `make chaos` · `make perf` · `make report` · `make down` · `make clean`

## Despliegue rápido (desde cero)
1. `make build` — construye las 6 imágenes `:local` (aprovecha caché de capas).
2. `make up` — levanta el stack sin reconstruir (falla con `make build` si falta alguna imagen).
3. `make seed` — siembra datos iniciales (`secrets/seed.json`).

Luego `make test`, `make e2e`, `make smoke` o `make invariants`.

## Frontend (F3)

Tras `make up && make seed`, abrir `http://127.0.0.1:8088/`: una pantalla
demuestra búsqueda, cliente, reserva, línea de tiempo, notificación, reenvío
idempotente y cancelación. `make smoke` comprueba el HTML/JS/CSS, las
cabeceras de seguridad y que las rutas internas no estén expuestas. Guion de
la demo y capturas: [`docs/manual.md`](docs/manual.md).
