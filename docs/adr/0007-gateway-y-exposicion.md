# ADR-0007: Gateway nginx: exposición pública vs. administrativa
**Estado:** Aceptado · **Fase:** F2

## Decisión
- nginx es la **única** entrada: sirve el frontend estático, enruta `/api/*`, balancea `availability` (DNS de Docker, `resolver 127.0.0.11`, `proxy_next_upstream` solo en operaciones idempotentes), aplica `limit_req`, `limit_conn` y timeouts.
- **Dos listeners:** `:8080` público (rutas mínimas) y `:8081` **administrativo/dev** (Compose lo publica solo en `127.0.0.1`) para semillas, pruebas y caos; se desactiva en el perfil de despliegue online. En dev el público se publica en `127.0.0.1:${GATEWAY_DEV_PORT:-8088}` para no chocar con otros procesos locales; el despliegue usa `8080`.
- **DNS dinámico para todos los servicios:** cada destino tiene un `upstream` con `resolve` y `zone`, no solo `availability`. Un `proxy_pass` con nombre estático resolvía una sola vez al arrancar y podía quedar apuntando a la IP de un contenedor recreado.
- **Reintentos seguros:** `proxy_next_upstream` solo en operaciones idempotentes: lecturas (`/api/availability`, `/api/hotels`, `/api/rooms`, `/api/notifications`) y escrituras de availability (inventario absoluto y holds por `hold_id`). En el resto de escrituras (`/api/reservations`, `/api/customers`, admin de payment/hotel/customer/reservation) se fija `proxy_next_upstream off` para no repetir un POST sin idempotencia demostrada. El resolver usa TTL de 2 s.
- Redes: `edge-net` (gateway), `backend-net` (`internal: true`), `data-net` (`internal: true`).
- Públicas: clientes (alta/consulta), hoteles/habitaciones (lectura), búsqueda de disponibilidad, reservas (crear/consultar/cancelar/eventos), notificaciones (lectura). **No públicas:** holds, inventario, pagos, creación de notificaciones, PostgreSQL.

## Consecuencias
(+) Superficie mínima y demostrable (`docker compose ps`/`nmap` local). (−) nginx OSS solo hace health check **pasivo**. (−) El rate limiting no frena DDoS volumétrico: eso requiere CDN/WAF (documentado).
