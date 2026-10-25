# Prompt para OpenCode: F3b interfaz tipo sitio de reservas (tope 4 h, con regla de descarte)

> Rama: `feat/f3b-ui-reservas`, desde `main` (con F5 fusionada). **Regla de descarte:** si a las 4 h la interfaz no pasa los criterios, **no se fusiona**; el tag `v1.0-entrega` ya existe y es la entrega válida. Dos commits: UI y pruebas/docs.

---

## ROL
Ingeniero front-end pragmático con criterio de producto. Arquitectura y contratos aceptados (ADR-0008). **Sin frameworks, sin build, sin CDN, sin fuentes ni imágenes externas, sin dependencias nuevas.** El backend **no cambia**.

## LEE
`docs/adr/0008`, `docs/05-contratos-api.md` (§2, §3, §4, §5 búsqueda, §6, §8), `gateway/conf.d/default.conf` (rutas públicas y límites), `gateway/html/*` actual, `scripts/smoke.py`, `tests/e2e/test_public_flow.py`, `docs/manual.md`.

## OBJETIVO
Que la aplicación **parezca un sitio real de reservas de alojamiento** (patrones de UX de Airbnb/Booking: buscador destacado, resultados en tarjetas, ficha del alojamiento, pago, confirmación, "mis reservas"), manteniendo la capacidad de **demostrar la saga, la idempotencia y los fallos** en la defensa. Inspírate en los **patrones**, **no copies** marcas, logotipos, textos ni imágenes de terceros: marca propia ficticia **"Reservas UCE"**.

## ALCANCE
**Crear/modificar:** `gateway/html/**` (mantén `index.html`, `app.js` —ahora módulo de entrada— y `styles.css`; añade `js/*.js` y `img/*.svg` si hace falta), `gateway/conf.d/default.conf` (solo tipos MIME/`gzip`/cabeceras si hace falta), `scripts/smoke.py`, `scripts/check_ui_routes.py`, `Makefile` (`check-ui`), `docs/manual.md`, `docs/adr/0008`, `docs/03-estado-del-proyecto.md`.
**Prohibido:** tocar servicios; exponer rutas internas; inventar datos que el backend no tiene (**no** mostrar reseñas, estrellas ni amenidades falsas); `innerHTML` con datos de la API; almacenar nada sensible.

## PANTALLAS (enrutado por hash, `#/…`, sin recargar)
1. **Inicio / búsqueda** (`#/`): cabecera con la marca y navegación (Explorar · Mis reservas), *hero* con buscador (destino = ciudad tomada de `GET /api/hotels`, entrada, salida, huéspedes), y "destinos populares" (ciudades reales de la API) como tarjetas.
2. **Resultados** (`#/buscar?...`): lista de alojamientos en tarjetas con ilustración, nombre, ciudad, **"desde $X por noche"** (mínimo de las habitaciones reales), indicador de cupo real para las fechas ("Quedan N", "Agotado") y total por las noches; **filtros** (ciudad, precio máximo, capacidad mínima) y **orden** (precio) en el cliente; estados de carga (esqueletos), vacío y error.
3. **Ficha del alojamiento** (`#/hotel/<id>?...`): galería de ilustraciones, habitaciones con capacidad, precio por noche, **total calculado** (`noches × precio`, igual que el backend) y botón "Reservar" deshabilitado si no hay cupo.
4. **Reserva y pago** (`#/reservar?...`): resumen (alojamiento, habitación, fechas, noches, total) y **datos del huésped** (nombre, email → `POST /api/customers`; o "continuar con usuario de demostración"). **Pago simulado sin datos de tarjeta:** selector de método en modo demostración con rótulos claros (`Tarjeta aprobada` → `ok`, `Tarjeta rechazada` → `decline`, `Banco sin respuesta` → `process_then_drop_response`, `Pago lento` → `slow`) y aviso "modo demostración: no ingreses datos reales". Confirmar → `POST /api/reservations` con `Idempotency-Key`.
5. **Estado y confirmación** (`#/reserva/<id>`): pantalla "Procesando tu reserva…" con **línea de tiempo animada** de `GET /api/reservations/{id}` y `/events`; al llegar a estado estable: **confirmada** (código corto, datos, estado de la notificación vía `GET /api/notifications`), **rechazada/cancelada** con explicación en lenguaje claro (sin cupo, pago rechazado…), o **en revisión**. Acciones: cancelar (solo `CONFIRMED`), ver mis reservas.
6. **Mis reservas** (`#/mis-reservas`): `GET /api/reservations?customer_id=`, tarjetas con estado (insignias de color), fechas, total y acción de cancelar.
7. **Modo demo técnico** (interruptor en el pie): panel lateral con el **registro de llamadas** (método, ruta, código HTTP, latencia, `request_id`, `Idempotent-Replayed`), la línea de tiempo cruda de estados y el botón **"Reenviar la misma solicitud"** (muestra `200` + `Idempotent-Replayed` y que no se duplica). Oculto por defecto, para que la interfaz parezca un sitio real.

## REQUISITOS TRANSVERSALES
- **Diseño:** *mobile-first* y responsivo (probar 375 px y 1280 px), rejilla de tarjetas, tipografía del sistema, variables CSS, esquema oscuro con `prefers-color-scheme`, estados de foco visibles, contraste suficiente, `aria-live` para cambios de estado, formularios con `label`.
- **Ilustraciones sin archivos externos de terceros:** genera con JavaScript (`createElementNS`) **SVG deterministas por id de alojamiento** (degradados y siluetas) o usa SVG propios en `img/`. Sin imágenes de stock.
- **Formato:** moneda con `Intl.NumberFormat("es-EC", {style:"currency", currency:"USD"})`; fechas en español.
- **Seguridad:** `textContent`/`createElement` (un helper `h()`), CSP actual sin relajar (`img-src` solo `self`), sin `eval`, sin scripts *inline*.
- **Respetar los límites del gateway:** concurrencia ≤ 2 solicitudes, caché en memoria de hoteles y habitaciones, *backoff* en 429/503 (reintento con la **misma** clave de idempotencia en `POST /api/reservations`) y mensajes comprensibles con `request_id`.
- **Rendimiento:** peso total de estáticos ≤ 150 kB sin comprimir; `gzip` en nginx para texto.
- **Idempotencia visible y correcta:** una clave por intento de reserva; reintentos y "reenviar" usan la misma clave; una nueva reserva genera una nueva.
- **Persistencia mínima:** el `customer_id` del huésped en `sessionStorage` (no sensible) para "Mis reservas".

## PRUEBAS
1. **`make smoke`** (actualizado): `/` 200 HTML con doctype; `app.js`, `styles.css` y cada módulo de `js/` 200 con tipo MIME de JavaScript/CSS; cabeceras de seguridad; sin *inline*; rutas internas no expuestas.
2. **`scripts/check_ui_routes.py`** (`make check-ui`, solo biblioteca estándar): extrae todas las rutas `/api/...` y métodos usados por el JS y comprueba contra el listener público que **ninguna ruta usada está bloqueada** y que ninguna ruta interna (`/svc`, holds, pagos, inventario) aparece en el código.
3. `tests/e2e/test_public_flow.py` y todo `make e2e` **sin cambios y en verde**; `make invariants` ⇒ 0.
4. **Comprobación manual guiada** (actualiza `docs/manual.md`): los **tres flujos de demo** (`ok`, `decline`, `process_then_drop_response` que pasa por `PAYMENT_UNKNOWN` y termina `CONFIRMED`), cancelar, "Mis reservas", error 429/503 y el modo demo técnico, en 375 px y 1280 px. Lista de **8 capturas** que hará la persona (inicio, resultados, ficha, pago, "procesando", confirmada, mis reservas, panel técnico con `Idempotent-Replayed`) con el nombre de archivo para `docs/resultados/ui/`.

## CRITERIOS DE ACEPTACIÓN (muestra salidas)
- [ ] `make build && make up && make seed` y luego `make smoke`, `make check-ui`, `make e2e`, `make lint`, `make invariants` en verde.
- [ ] Los tres flujos de demo funcionan de principio a fin en la UI.
- [ ] Ninguna ruta interna expuesta; sin `innerHTML` con datos de la API; CSP intacta.
- [ ] Sin dependencias nuevas; **servicios e imágenes del producto sin cambios** (`make images`).
- [ ] Peso de estáticos ≤ 150 kB; sin recursos externos (verifica en la red del navegador o con `grep` de URLs absolutas).
- [ ] Informe con archivos, salidas, decisiones y la lista de 8 capturas.
**Orden de prioridad si falta tiempo:** (1) resultados + ficha + reserva y pago + estado/confirmación; (2) mis reservas; (3) filtros y orden; (4) modo demo técnico; (5) esquema oscuro. **Si (1) no queda sólido en 4 h, no fusionar.**

## ENTREGA
PR con la plantilla. No fusiones a `main`. Si se aprueba, propón el tag `v1.0.1-entrega` (la entrega ya etiquetada permanece como respaldo).

## REGLAS
Sin dependencias nuevas · sin datos inventados · sin recursos externos · nada interno expuesto · idempotencia y límites respetados · si cambias arquitectura, propón el ADR y detente.
