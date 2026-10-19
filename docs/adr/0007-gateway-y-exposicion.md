# ADR-0007: Gateway nginx: exposición pública vs. administrativa
**Estado:** Propuesto · **Fase:** F2

## Decisión
- nginx es la **única** entrada: sirve el frontend estático, enruta `/api/*`, balancea `availability` (DNS de Docker, `resolver 127.0.0.11`, `proxy_next_upstream` solo para lecturas), aplica `limit_req`, `limit_conn` y timeouts.
- **Dos listeners:** `:8080` público (rutas mínimas) y `127.0.0.1:8081` **administrativo/dev** (solo loopback) para semillas, pruebas y caos; se desactiva en el perfil de despliegue online.
- Redes: `edge-net` (gateway), `backend-net` (`internal: true`), `data-net` (`internal: true`).
- Públicas: clientes (alta/consulta), hoteles/habitaciones (lectura), búsqueda de disponibilidad, reservas (crear/consultar/cancelar/eventos), notificaciones (lectura). **No públicas:** holds, inventario, pagos, creación de notificaciones, PostgreSQL.

## Consecuencias
(+) Superficie mínima y demostrable (`docker compose ps`/`nmap` local). (−) nginx OSS solo hace health check **pasivo**. (−) El rate limiting no frena DDoS volumétrico: eso requiere CDN/WAF (documentado).
