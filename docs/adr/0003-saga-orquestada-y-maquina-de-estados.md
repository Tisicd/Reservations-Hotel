# ADR-0003: Saga orquestada + máquina de estados en `reservation`
**Estado:** Aceptado · **Fase:** F0/F1

## Contexto
Una reserva toca tres servicios (`availability`, `payment`, y `customer`/`hotel` para validar). No existe una transacción distribuida: cada paso puede fallar o repetirse. El pago puede quedar en resultado **incierto**.

## Decisión
1. **Orquestación** (no coreografía): `reservation` dirige el flujo; los demás servicios no se llaman entre sí.
2. **Máquina de estados pura** en `domain` (sin I/O): define estados, transiciones válidas y estados terminales. Transiciones ilegales lanzan un error de dominio.
3. **Una sola función `advance(reservation_id)`** ejecuta el siguiente paso según el estado persistido. La usan **tanto la petición HTTP** (en bucle hasta estado estable o plazo) **como el worker de recuperación**. Así recuperar tras un crash es el mismo código que el camino normal.
4. **Persistir antes de actuar:** el estado se guarda antes de cada llamada externa. Cada paso externo es idempotente (clave = `reservation_id`), así que repetirlo es seguro.
5. **Validación previa, sin efectos:** (a) buscar `Idempotency-Key`; (b) validar cliente y habitación (solo lecturas; si fallan, 4xx/503 sin registro); (c) persistir `RECEIVED` con **instantánea** (precio, cliente, habitación) y el evento.
6. **Respuesta HTTP:** `201` si llega a un estado estable dentro de `SAGA_SYNC_WAIT_SECONDS` (por defecto 5 s); `202` + `Location` si no. Repetir con la misma clave devuelve `200` con el estado actual y `Idempotent-Replayed: true`.

| Estado persistido | Acción | Resultado → siguiente estado |
|---|---|---|
| `RECEIVED` | `availability.create_hold` | OK → `HELD` · sin cupo → `REJECTED_NO_INVENTORY` · 503/timeout → permanece y reintenta con backoff; al vencer el plazo → `FAILED_TECHNICAL` |
| `HELD` | (transición inmediata) | → `PAYMENT_PENDING` |
| `PAYMENT_PENDING` | `payment.create` (misma clave) | `SUCCEEDED` → `PAID` · `DECLINED` → `PAYMENT_DECLINED` · técnico → reintento acotado, luego `PAYMENT_DECLINED` (`reason=TECHNICAL`) · timeout/`UNKNOWN` → `PAYMENT_UNKNOWN` |
| `PAYMENT_UNKNOWN` | consultar pago por `reservation_id` + extender hold | resuelto → `PAID` / `PAYMENT_DECLINED` · plazo agotado → `MANUAL_REVIEW` |
| `PAID` | `availability.confirm` | OK → `CONFIRMED` + evento en outbox (misma TX) · hold vencido → `REFUND_REQUIRED` · 503 → reintenta |
| `PAYMENT_DECLINED` | `availability.release` | → `CANCELLED` |
| `REFUND_REQUIRED` | `payment.refund` | → `CANCELLED` |
| `CONFIRMED` + cancelar | persistir `CANCELLING` → release + refund | → `CANCELLED` |
| `CANCELLING` | release (idempotente) + refund | OK → `CANCELLED` + evento outbox; al vencer `CANCEL_DEADLINE_SECONDS` → `MANUAL_REVIEW` (`reason=CANCEL_TIMEOUT`): **no** se asume si hubo reembolso |

Nota (PASO 0 de T1.4): todo plazo agotado con dinero o inventario en duda
termina en `MANUAL_REVIEW`; es el único estado estable que admite un hold
extendido y una resolución humana. Aplica a `PAYMENT_UNKNOWN`,
`REFUND_REQUIRED`, `PAID` (confirmación) y `CANCELLING`.

Cambios respecto a F0: se elimina `HOLD_REQUESTED` (es `RECEIVED`: el estado se persiste antes de llamar y la llamada es idempotente) y se añade `CANCELLING`.

## Alternativas descartadas
| Alternativa | Por qué no |
|---|---|
| Coreografía por eventos | Flujo difuso, difícil de probar y de explicar; exigiría el broker desde el inicio |
| 2PC / transacción distribuida | No disponible entre servicios HTTP; bloquea y no es resiliente |
| Orquestador externo (Temporal, etc.) | Dependencia pesada, curva de aprendizaje; fuera de alcance |

## Consecuencias
(+) Un solo camino de código para operar y recuperar. (+) La saga se prueba con dobles en memoria, incluyendo "crash entre pasos". (−) La consistencia es **eventual** entre servicios: durante la saga hay estados intermedios visibles. (−) `MANUAL_REVIEW` requiere intervención humana (se documenta; el hold se extiende para no perder el inventario).
