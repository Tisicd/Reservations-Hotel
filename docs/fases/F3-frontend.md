# F3: Frontend mínimo (timebox 4 h)

**Objetivo:** una pantalla que demuestre el flujo completo y **los estados** de la saga; sirve para la defensa. No importa la estética. Spec detallada: `docs/prompts/F3-frontend.md`. Decisión: ADR-0008.

## Alcance
HTML + JS vanilla + CSS servidos por nginx en `/`. Solo llama a `/api/*` por el gateway.
1. **Buscar:** `GET /api/hotels`, `GET /api/hotels/{id}`, `GET /api/availability` con fechas.
2. **Cliente:** `POST /api/customers` (o elegir uno de la semilla).
3. **Reservar:** `POST /api/reservations` con `Idempotency-Key` (`crypto.randomUUID()`) y selector de **simulación de pago** (`ok`, `decline`, `process_then_drop_response`, `slow`).
4. **Resultado:** polling de `GET /api/reservations/{id}` y `/events` hasta estado estable; **línea de tiempo** de transiciones y estado de la notificación (`GET /api/notifications?reservation_id=`).
5. Extras baratos y útiles para la defensa: botón **reenviar con la misma clave** (muestra el *replay*) y botón **cancelar**.

## Fuera de alcance
React/Vite, autenticación, paginación, diseño, exponer holds/pagos/internos.

## Criterios de aceptación
- [ ] `make smoke` exige `GET /` → 200 HTML (`<!doctype html>`).
- [ ] Con `make up && make seed`: buscar → reservar → `CONFIRMED` con línea de tiempo visible; con `decline` → `CANCELLED(DECLINED)`; con `process_then_drop_response` → pasa por `PAYMENT_UNKNOWN` y termina `CONFIRMED`.
- [ ] Sin `innerHTML` con datos de la API (evitar XSS); sin dependencias externas ni CDN.
- [ ] Lista de comprobación manual de 10 pasos en `docs/manual.md` (borrador).
- [ ] *(Stretch)* una prueba Playwright del flujo feliz en un contenedor de pruebas **fuera de las imágenes del producto**; requiere enmienda de ADR-0009. Solo si F4 va holgada.

## Calidad mínima
Manejo de errores visible (`503`, `429`, `422` con `request_id`), botón de reintento, sin recarga completa.
