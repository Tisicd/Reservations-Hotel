# Prompt para OpenCode: F3 frontend mínimo (tope 4 h)

> Rama: `feat/f3-frontend`, desde `main`. Spec previa: `docs/prompts/F3-frontend.md`; **si discrepa con esta lista, prevalece esta**. Objetivo: una pantalla que demuestre el flujo completo y **los estados de la saga** en la defensa. No importa la estética. Dos commits: UI + pruebas/gateway.

---

## ROL
Ingeniero full-stack pragmático. Arquitectura y contratos aceptados (ADR-0008). **Sin frameworks, sin build, sin CDN, sin dependencias nuevas.**

## LEE
`docs/fases/F3-frontend.md`, `docs/05-contratos-api.md` (§1, §2, §6, §8), `docs/adr/0007`, `docs/adr/0008`, `gateway/conf.d/default.conf` (límites vigentes: `limit_req`, `limit_conn`), `docs/03-estado-del-proyecto.md`.

## ALCANCE
**Crear/modificar:** `gateway/html/{index.html,app.js,styles.css}`, `gateway/conf.d/default.conf` (servir `/`, cabeceras), `tests/e2e/test_public_flow.py`, `Makefile` (smoke), `docs/manual.md` (borrador), `docs/adr/0008` (estado), `docs/03-estado-del-proyecto.md`, README (comandos).
**Prohibido:** exponer holds, pagos, inventario ni nada interno; tocar servicios; React/Vite/Playwright; librerías externas.

## FUNCIONALIDAD (una pantalla, llamadas solo a `/api/*` del gateway)
1. **Buscar:** `GET /api/hotels`, `GET /api/hotels/{id}`, `GET /api/availability?hotel_id&check_in&check_out` (fechas con validación `check_out > check_in`, `check_in ≥ hoy`). Mostrar habitaciones con precio y cupo disponible.
2. **Cliente:** elegir uno existente de la semilla o crear con `POST /api/customers`.
3. **Reservar:** `POST /api/reservations` con `Idempotency-Key` UUID v4 **con respaldo** si `crypto.randomUUID` no existe (HTTP sin TLS fuera de `localhost`: usar `crypto.getRandomValues`). Selector de **simulación de pago** (`ok`, `decline`, `process_then_drop_response`, `slow`); si el backend responde 422 `SIMULATION_DISABLED`, mostrar el mensaje.
4. **Resultado en vivo:** *polling* de `GET /api/reservations/{id}` y `/events` hasta estado estable; **línea de tiempo** de transiciones (estado, motivo, hora, tiempo transcurrido) y estado de la notificación (`GET /api/notifications?reservation_id=`).
5. **Demostración:** botón **"Reenviar con la misma clave"** (muestra que devuelve 200 con `Idempotent-Replayed` y **no** duplica la reserva), botón **Cancelar** (solo `CONFIRMED`), y un recuadro con el último `request_id` y código HTTP.
6. **Errores visibles y útiles:** `429` ("demasiadas solicitudes; reintentando en X s", con espera y reintento acotado), `503` ("servicio no disponible, no se perdió nada: se reintenta con la misma clave"), `422`, `404`; siempre con `request_id`.
7. **Polling responsable:** intervalo ≥ 1 s con *backoff*, **máx. 2 solicitudes simultáneas**, y por debajo de los límites del gateway (léelos del `default.conf`); detener al llegar a estado estable o tras un tiempo máximo.

## SEGURIDAD
Sin `innerHTML` con datos de la API (usar `textContent`/`createElement`); JS y CSS en archivos externos (sin *inline*) para permitir CSP. En nginx para `/`: `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-cache` en el HTML. Los estáticos se montan **solo lectura**. No almacenar nada sensible (sin `localStorage` de tokens; es un demo).

## PRUEBAS
1. `make smoke` exige: `GET /` ⇒ 200, `text/html`, empieza por `<!doctype html>`; `app.js` y `styles.css` ⇒ 200 con `Content-Type` correcto; cabeceras de seguridad presentes.
2. **`tests/e2e/test_public_flow.py`** reproduce **exactamente las llamadas de la UI contra el listener público** (sin el admin) y verifica que ninguna ruta necesaria esté bloqueada por el gateway: buscar → crear cliente → reservar (`ok`) → polling hasta `CONFIRMED` → `/events` → `/api/notifications` → reenviar con la misma clave (200 + `Idempotent-Replayed`, sin duplicados) → cancelar. Respetando los límites. Luego `make invariants` ⇒ 0.
3. Comprobación **negativa**: desde el listener público, `/svc/...`, holds, pagos e inventario devuelven 404/403 (no expuestos).
4. Lista de comprobación manual de 10 pasos en `docs/manual.md` (borrador) para los tres flujos de demo: `ok`, `decline`, `process_then_drop_response` (pasa por `PAYMENT_UNKNOWN` y termina `CONFIRMED`).

## CRITERIOS DE ACEPTACIÓN (muestra salidas)
- [ ] `make build && make up && make seed` y `make smoke` en verde; `make test`/`make e2e` sin regresiones; `make lint` en verde.
- [ ] `test_public_flow.py` ×10 sin fallos; rutas internas no expuestas.
- [ ] La UI cubre los tres flujos de demo y los errores 429/503 (**la persona** hará las capturas de pantalla para `docs/resultados/ui/`; indica los 5 momentos a capturar).
- [ ] Sin dependencias nuevas ni cambios en servicios; imágenes del producto sin cambios.
**Recorte:** si te acercas a las 4 h, entrega búsqueda → reserva → línea de tiempo → reenvío; cancelar y estilos pasan a opcionales.

## ENTREGA
PR con la plantilla; informe con archivos, salidas y desviaciones justificadas. No fusiones a `main`.

## REGLAS
Test primero cuando sea posible · sin dependencias nuevas · sin secretos · nada interno expuesto · si cambias arquitectura, propón el ADR y detente.
