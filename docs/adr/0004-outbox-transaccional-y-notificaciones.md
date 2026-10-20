# ADR-0004: Outbox transaccional + inbox idempotente + worker
**Estado:** Aceptado · **Fase:** F2

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

## Decisi?n F2 sobre RabbitMQ (medida)

Se mantiene **HTTP + outbox** y **no se introduce RabbitMQ**. Criterios y
evidencia (2026-10-20, stack dev con `notification` y relay reales):

| Criterio | Resultado |
|---|---|
| Entrega normal (reserva -> inbox `SENT`) | 0.088-0.223 s con un solo intento (7 eventos); media 0.84 s en el lote de 26, incluida la recuperación |
| Ca?da de `notification` (3 s) sin afectar la reserva | Reserva `CONFIRMED`; el evento qued? `PENDING` y se entreg? al volver: 5 intentos, 8.4 s desde `created_at` hasta `SENT` |
| Duplicados | `UNIQUE(event_id)`; segundo `POST` devuelve `200` con el mismo `id` y no crea fila |
| P?rdida de eventos | 0: el evento vive en `reservation_db` hasta `SENT`; el relay reintenta con backoff capado |

RabbitMQ no elimina duplicados (habr?a que mantener el inbox igual), a?ade una
pieza operativa (broker, cuotas, persistencia) y no mejora la garant?a que ya
da el outbox. Se reconsiderar? si aparece m?s de un consumidor por evento, si
se necesita fan-out entre servicios, o si la tasa sostenida supera lo que un
relay por polling puede entregar (medir en F4 con k6 antes de decidir).
