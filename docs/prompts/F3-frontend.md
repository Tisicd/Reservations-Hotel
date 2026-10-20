# F3 — Frontend estático (una pantalla, solo gateway)

**Estado:** preparado, no implementado. Sirve como especificación para la
siguiente tarea. No se modifica el gateway ni los servicios.

## Flujo de pantalla (única)

1. **Búsqueda**: campos `city`, `check_in`, `check_out`, `guests`.
   Botón "Busca hoteles".
2. **Lista de hoteles**: `GET /api/hotels?city=<city>` → muestra cada hotel
   (`id`, `name`, `city`). Al seleccionar: `GET /api/hotels/{id}` →
   `rooms:[{id, name, capacity, price_per_night_cents, currency}]`.
3. **Disponibilidad**: al elegir una habitación, `GET /api/availability?
   hotel_id=<id>&check_in=<ci>&check_out=<co>` → `rooms:[{room_id, available}]`.
   Solo muestra habitaciones con `available > 0`. Si la respuesta es 503
   (`DEPENDENCY_UNAVAILABLE` con `Retry-After`), esperar y reintentar.
4. **Cliente**: formulario `name`, `email` → `POST /api/customers` →
   `201 {id}`. Si `409 EMAIL_EXISTS`, pedir otro email.
5. **Reserva**: `POST /api/reservations` con cuerpo:
   ```json
   { "customer_id": "<id>", "hotel_id": "<id>", "room_id": "<id>",
     "check_in": "YYYY-MM-DD", "check_out": "YYYY-MM-DD",
     "payment": { "method": "card", "token": "tok_demo", "simulate": "ok" } }
   ```
   Cabecera `Idempotency-Key` generada con `crypto.randomUUID()`.
   - `201` / `202` → ir al paso 6.
   - `422 IDEMPOTENCY_KEY_REUSED` → generar una nueva clave y reintentar.
   - `409` → mostrar `error.message` (NO_INVENTORY, HOLD_CONFLICT, …).
   - `503` → esperar `Retry-After` y reintentar.
6. **Consulta del estado**: `GET /reservations/{id}` cada 1 s, hasta 10 s.
   Muestra `status` y, si se desea, `GET /reservations/{id}/events`
   (línea de tiempo). Si `202` (aún en proceso), seguir consultando.
7. **Resultado**: pantalla de confirmación con `id`, `status`,
   `check_in/out`, `amount_cents`, `currency` y `payment.status`.
   Botón "Nueva búsqueda" vuelve al paso 1.

## Restricciones

- **Solo gateway**: todas las llamadas van a `http://<gateway>/api/...`
  (en dev `127.0.0.1:8088`, en despliegue `:8080`). Nada de puertos
  internos, `backend-net` o `/svc/...`.
- **No expone**: holds, inventario, pagos (solo el resultado final), ledger,
  endpoints de notificación internos, secrets ni variables de entorno.
- **HTML/JS vanilla** (sin build, sin dependencias): sirve desde nginx en
  `/` (`root /usr/share/nginx/html`, `try_files $uri /index.html`).
- **Conservar `/healthz`** y el 404 actual de rutas desconocidas.
- **Timeouts**: cada petición HTTP con timeout explícito (p. ej. 10 s) y
  manejo visible de red/5xx.
- **Idempotencia**: `Idempotency-Key` siempre nuevo; si el navegador
  recarga la página, la clave debe regenerarse (o guardarse en
  `sessionStorage` para la misma carga).

## Pruebas de aceptación (cuando el frontend exista)

- `make smoke` ampliado: `GET /` → `200` y el HTML contiene `<!doctype html>`.
- Un E2E de API (httpx) que repite el flujo completo (hotel →
  disponibilidad → cliente → reserva → consulta estado) ya existe en
  `tests/e2e/test_flows.py`; no se necesita Playwright salvo petición
  expresa.

## Siguiente tarea concreta

Implementar `gateway/html/index.html` + `app.js` + `styles.css` según esta
especificación, ajustar `gateway/nginx.conf` para servir `/` y ejecutar
`make smoke` ampliado.