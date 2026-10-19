# Registro de decisiones de arquitectura (ADR)

Cada ADR es breve: **contexto → decisión → alternativas → consecuencias**. Regla del repo: *todo cambio de arquitectura se acompaña de un ADR nuevo o de la actualización de uno existente en el mismo PR.*

| ADR | Decisión | Estado |
|---|---|---|
| [0001](0001-microservicios-hexagonal-ligera.md) | Microservicios con arquitectura hexagonal **ligera** | Aceptado |
| [0002](0002-postgresql-compartido-seis-bds.md) | PostgreSQL compartido con 6 BDs y 6 roles | Aceptado |
| [0003](0003-saga-orquestada-y-maquina-de-estados.md) | Saga orquestada + máquina de estados en `reservation` | Aceptado |
| [0004](0004-outbox-transaccional-y-notificaciones.md) | Outbox transaccional + inbox idempotente + worker | Aceptado |
| [0005](0005-availability-atomica-e-idempotente.md) | Inventario con operaciones atómicas e idempotentes | Aceptado |
| [0006](0006-payment-adapter-y-estados-explicitos.md) | Payment: Adapter de proveedor y estados explícitos | Aceptado |
| [0007](0007-gateway-y-exposicion.md) | Gateway nginx: exposición pública vs. administrativa | Aceptado |
| [0008](0008-frontend-minimo.md) | Frontend mínimo en HTML + JS servido por nginx | Aceptado |
| [0009](0009-stack-y-dependencias.md) | Stack y dependencias justificadas | Aceptado |
| [0010](0010-fuente-de-verdad-datos-maestros.md) | Fuente de verdad de datos maestros y validación de hotel/habitación | Aceptado |

Estados: *Propuesto → Aceptado → (Reemplazado por ADR-xxxx)*. ADR 0001-0010 **aceptados** al cerrar la compuerta G0 (2026-10-19).

Plantilla: copiar un ADR existente.
