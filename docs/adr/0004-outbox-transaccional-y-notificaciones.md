# ADR-0004: Outbox transaccional + inbox idempotente + worker
**Estado:** Propuesto · **Fase:** F2

## Contexto
Una reserva confirmada **nunca** debe cancelarse ni retrasarse porque falle una notificación. Pero tampoco debe perderse el aviso (invariante I6).

## Decisión
- **Outbox en `reservation_db`:** al pasar a `CONFIRMED` (o `CANCELLED`) se inserta el evento en la tabla `outbox` **en la misma transacción** que el cambio de estado.
- **Relay** (worker de `reservation`): lee eventos pendientes (`FOR UPDATE SKIP LOCKED`) y hace `POST /notifications` con `event_id`; reintenta con backoff exponencial + jitter.
- **Inbox idempotente en `notification`:** `UNIQUE(event_id)`. Repetir el evento devuelve el existente. Entrega al menos una vez + deduplicación = efecto único.
- **Worker de entrega de `notification`:** toma `PENDING`, usa un `NotificationChannel` (adapter simulado) y registra `attempts`/`SENT`/`FAILED`.
- Workers = **mismo código/imagen, comando distinto**, en contenedores separados: matar la API no mata al worker y viceversa.
- **RabbitMQ: opcional** (compuerta G1). Solo sustituiría el transporte del relay; no cambia el diseño.

## Alternativas descartadas
| Alternativa | Por qué no |
|---|---|
| Llamar a `notification` dentro de la saga | Acopla el éxito de la reserva a un servicio de baja criticidad |
| Publicar en el broker tras el commit | Ventana de pérdida entre commit y publicación (dual write) |
| RabbitMQ desde el inicio | No elimina duplicados ni sustituye transacciones; añade infraestructura antes de tener resultados |

## Consecuencias
(+) Escenario A demostrable: con `notification` caída las reservas siguen confirmando y los eventos se entregan al volver. (−) Más piezas (2 workers). (−) Latencia de entrega = intervalo de polling del relay (configurable).
