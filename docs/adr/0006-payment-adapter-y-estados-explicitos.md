# ADR-0006: Payment: Adapter de proveedor y estados explícitos
**Estado:** Aceptado · **Fase:** F1

## Contexto
No hay pasarela real, pero hay que poder probar rechazos, errores técnicos y, sobre todo, **resultados inciertos** sin cobrar dos veces.

## Decisión
- Puerto `PaymentProvider` (`charge`, `lookup`, `refund`) con un adapter `SimulatedProvider` que **persiste sus cargos** (`sim_provider_charges`) para poder consultarlos después.
- Modos de simulación por solicitud (`simulate`: `ok`, `decline`, `error_before_processing`, `process_then_drop_response`, `slow`), aceptados solo si `PAYMENT_SIMULATION_ENABLED=true`. Así la demo y los tests no necesitan endpoints de administración.
- Estados: `INITIATED → SUCCEEDED | DECLINED | FAILED_TECHNICAL | UNKNOWN`, y `SUCCEEDED → REFUNDED`. `UNKNOWN` se resuelve consultando al proveedor por la clave de idempotencia.
- `UNIQUE(idempotency_key)`; clave = `reservation_id`. Registro append-only en `ledger`.
- `reservation` **nunca** crea un segundo cobro con otra clave; reintenta con la misma o consulta.

## Alternativas descartadas
Mockear el proveedor solo en tests (no sirve para la demo ni para el caos), integrar una pasarela de sandbox (dependencia externa y red).

## Consecuencias
(+) Se demuestra I3 (sin cobro doble) y el caso `UNKNOWN`. (−) Un proveedor real exigiría conciliación y garantías propias; se documenta en `produccion.md`.
