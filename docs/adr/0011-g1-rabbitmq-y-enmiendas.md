# ADR-0011: G1 (RabbitMQ no se implementa) y enmiendas de cierre

**Estado:** Aceptado · **Fase:** F5

## Contexto

La compuerta G1 dejó abierta la posibilidad de introducir RabbitMQ si el
outbox no bastaba. Tras F4 no hay evidencia de pérdida de eventos ni de
bloqueo por notificaciones; el outbox + relay + inbox idempotente cumplió I6
en los escenarios A, C, E1 y E2. Además, durante F1–F4 se hicieron tres
enmiendas que conviene registrar en un solo ADR: el plazo de `CANCELLING`,
el `429` del gateway y el listener admin sin límites para las pruebas de
carga.

## Decisión

1. **No se implementa RabbitMQ.** El outbox transaccional, el relay con
   leases y el inbox idempotente cubren la entrega al menos una vez y el
   dedupe por `event_id` (ADR-0004). Se documenta como evolución si aparecen
   requisitos de *fan-out* o *dead-letter* (ver `produccion.md`).
2. **`CANCELLING` tiene plazo**: `CANCEL_DEADLINE_SECONDS=120`; si vence sin
   completar release/refund, la reserva pasa a `MANUAL_REVIEW` con
   `reason=CANCEL_TIMEOUT` y **no** se asume que el reembolso ocurrió
   (ADR-0003, `docs/fallos.md`).
3. **Gateway**: `limit_req`/`limit_conn` responden **429** (no 503), y el
   listener administrativo `:8081` sirve `/svc/*` y `/api/*` **sin** límites
   para medir capacidad; solo P4 usa el público (ADR-0007, `perf_P4.md`).

## Evidencia

- A (fail-open) y C/E1/E2 (notificaciones y estados) en
  `docs/resultados/chaos_A_*.md`, `chaos_C_*.md`, `chaos_E1_*.md`,
  `chaos_E2_*.md`; `make invariants` ⇒ 0.
- `CANCELLING`: ADR-0003 y la tabla de estados de `05-contratos-api.md`.
- `429` y listener admin: ADR-0007, `tests/infra/test_gateway.py`,
  `docs/resultados/perf_P4.md` (141/45 respuestas 429; canario admin estable).

## Alternativas consideradas

- **RabbitMQ ahora**: añade un componente operado más (alta disponibilidad,
  colas, credenciales, backup) sin un problema medido. Se pospone.
- **Mantener 503 para los límites**: impedía distinguir límite del gateway de
  fail-closed; se descartó.
- **No exponer `/api/*` en el admin**: imposibilitaba medir capacidad sin
  chocar con `limit_*` por IP; se documenta que el admin es solo dev.

## Consecuencias

(+) Menos superficie operativa y una latencia de notificación aceptable.
(+) El 429 ya no se confunde con un fallo de servicio.
(−) Sin *dead-letter* nativo; se mitiga con alarma de backlog y se propone en
producción.
(−) El listener admin no debe publicarse fuera de dev; `up-prod` no lo expone.
