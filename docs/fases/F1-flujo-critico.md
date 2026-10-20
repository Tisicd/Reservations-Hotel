# F1: Flujo crítico (19–21 oct)

**Objetivo:** que el camino que no puede fallar (disponibilidad → reserva → pago) preserve las invariantes I1–I5 antes de añadir nada más.
**Método:** para cada tarea, el test se escribe primero. Cada tarea es un PR pequeño (≤ 1–2 h para el agente).

## Tareas

| ID | Tarea | Pruebas que la definen (criterio de aceptación) |
|---|---|---|
| **T1.0** | Bootstrap: `compose.yaml` (postgres, redes `internal`), script `init` que crea 6 BDs y 6 roles, `Makefile` (`up/down/test/lint`), `.env.example`, CI (ruff + import-linter + tests), perfil `dev` con PostgreSQL en `127.0.0.1` | `make up` deja PostgreSQL `healthy`; test: el rol de una BD **no** puede leer otra |
| **T1.1** | `availability`: migraciones, dominio (`DateRange`, `Hold`), casos de uso (`create_hold`, `confirm`, `release`, `extend`, `search`, `expire`), SQL atómico (ADR-0005), API | **Integración (PostgreSQL real):** 50 solicitudes concurrentes por 5 cupos → exactamente 5 `HELD`; `hold_id` repetido → mismo hold; `HOLD_CONFLICT`; `confirm`/`release` idempotentes; expiración libera cupo; `CHECK` rechaza inventario negativo. **Unit:** dominio |
| **T1.2** | `payment`: dominio (estados), `SimulatedProvider` (persistente), casos de uso (`create`, `get`, `refund`, reconciliación), API | Todos los modos de `simulate`; misma clave ×5 → 1 cobro; `process_then_drop_response` → `UNKNOWN` y luego `SUCCEEDED` al consultar; reembolso idempotente |
| **T1.3** | `reservation`: máquina de estados (dominio puro), `advance`, `create_reservation` (idempotencia), repositorio, clientes HTTP, worker de recuperación | **Unit con dobles:** camino feliz; sin cupo; pago rechazado → libera hold; `UNKNOWN` → reconcilia; crash simulado entre **cada par** de pasos → la recuperación termina bien; hold vencido tras pago → `REFUND_REQUIRED`; transición ilegal → error; misma clave concurrente → 1 reserva |
| **T1.4** | `customer` y `hotel` (CRUD modular) + semilla (`make seed`) | Pruebas de API; semilla idempotente |
| **T1.5** | **Chequeador de invariantes** (`tests/invariants/`): consultas I1–I5 sobre las BDs; se ejecuta al final de cada prueba e2e | Detecta una violación sembrada a propósito (prueba del chequeador); verde en el flujo normal |
| **T1.6** | e2e por HTTP interno: reserva completa, pago rechazado, doble envío, carrera por el último cupo | Pasan y el chequeador queda verde |

## Criterio de salida de F1
- [x] Todos los tests anteriores en verde (231 passed, 0 skipped; ver `docs/resultados/F1.md`).
- [x] `import-linter` en verde en availability, reservation y payment (3 contratos); notification es de F2.
- [x] I1–I5 verificadas automáticamente tras los e2e (el chequeador cubre I1–I7).
- [x] ADR-0003/0005/0006 aceptados en G0 (2026-10-19).
- [x] Registro de tiempo/costos al día; tag `f1`.
