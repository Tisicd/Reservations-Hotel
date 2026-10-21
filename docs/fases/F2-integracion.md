# F2: Integración (estado: consolidada)

**Objetivo:** unir los 6 servicios tras un gateway, con notificaciones desacopladas y réplicas de lectura.

## Entregado
- `notification-service`: inbox idempotente (`UNIQUE(event_id)`), worker de entrega con backoff.
- `reservation-relay`: relay del outbox con backoff y *lease* hacia `notification`.
- Gateway nginx: único puerto, balanceo de `availability` x3 con DNS dinámico, `limit_req`, timeouts y reintentos solo en lecturas.
- E2E de notificaciones, smoke y continuidad del gateway. Tests: lint, 251 unit/integración, 2×10 e2e, 3 smoke, **0 violaciones de invariantes**.

## Decisión G1 (propuesta, pendiente de tu confirmación)
| Tema | Decisión | Motivo |
|---|---|---|
| RabbitMQ | **No** | Outbox + relay + inbox cumple I6; sin problema medido. Se documenta como evolución |
| Alcance | Congelado a lo existente + F3 | El colchón de tiempo va a F4 |
| Playwright | Opcional (F3 stretch) | Dependencia pesada; ver F3 |

## Lectura del informe de la consolidación
| Hallazgo | Clasificación | Acción |
|---|---|---|
| Relay sin *dead-letter* (reintenta indefinidamente) | P2 | Fail-open aceptado; **añadir alarma** `OUTBOX_BACKLOG_OLD` al chequeador (F4) |
| nginx no reintenta métodos no idempotentes | **Propiedad de diseño, no riesgo** | Es la política segura; el cliente reintenta con su clave de idempotencia |
| `extend` de hold no reintentable por nginx | P2 solo si pasa por el gateway | Verificar que `reservation → availability` no pase por el balanceador de lectura |
| Sin TLS ni health check activo (nginx OSS) | Limitación documentada | `seguridad.md` y `produccion.md` (F5) |

## Criterio de salida
- [x] `make lint`, `make test`, `make e2e`, `make smoke`, `make invariants` en verde.
- [ ] Confirmar G1 (tabla de arriba).
- [ ] Tag `f2` tras fusionar.
- [ ] Control de imágenes Docker (ver `prompts/T-docker-imagenes.md`) antes de F4.
