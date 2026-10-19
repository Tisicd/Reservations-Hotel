# Registro de decisiones de arquitectura (ADR)

Cada ADR es breve: **contexto → decisión → alternativas → consecuencias**. Regla del repo: *todo cambio de arquitectura se acompaña de un ADR nuevo o de la actualización de uno existente en el mismo PR.*

| ADR | Decisión | Estado |
|---|---|---|
| [0001](0001-microservicios-hexagonal-ligera.md) | Microservicios con arquitectura hexagonal **ligera** | Propuesto |
| [0002](0002-postgresql-compartido-seis-bds.md) | PostgreSQL compartido con 6 BDs y 6 roles | Propuesto |
| [0003](0003-saga-orquestada-y-maquina-de-estados.md) | Saga orquestada + máquina de estados en `reservation` | Propuesto |
| [0004](0004-outbox-transaccional-y-notificaciones.md) | Outbox transaccional + inbox idempotente + worker | Propuesto |
| [0005](0005-availability-atomica-e-idempotente.md) | Inventario con operaciones atómicas e idempotentes | Propuesto |
| [0006](0006-payment-adapter-y-estados-explicitos.md) | Payment: Adapter de proveedor y estados explícitos | Propuesto |
| [0007](0007-gateway-y-exposicion.md) | Gateway nginx: exposición pública vs. administrativa | Propuesto |
| [0008](0008-frontend-minimo.md) | Frontend mínimo en HTML + JS servido por nginx | Propuesto |
| [0009](0009-stack-y-dependencias.md) | Stack y dependencias justificadas | Propuesto |

Estados: *Propuesto → Aceptado → (Reemplazado por ADR-xxxx)*. Pasan a **Aceptado** al cerrar la compuerta G0.

Plantilla: copiar un ADR existente.
