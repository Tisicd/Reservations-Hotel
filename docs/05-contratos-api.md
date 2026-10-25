# 05. Contratos API (v1.0, G0 cerrado el 2026-10-19)

Los contratos son **HTTP/JSON explícitos**. FastAPI generará el OpenAPI de cada servicio; se guardará un snapshot y un test de contrato detectará cambios. Este documento es la fuente de verdad hasta entonces.

## 1. Convenciones transversales
| Tema | Regla |
|---|---|
| IDs | UUID v4 |
| Fechas | `YYYY-MM-DD`; noches = `[check_in, check_out)`; `check_out > check_in` |
| Dinero | enteros en centavos (`amount_cents`) + `currency` (`USD`) |
| Cabeceras | `X-Request-ID` (se genera si falta y se devuelve), `Idempotency-Key` (obligatoria en `POST /reservations` y `POST /payments`) |
| Salud | Todo servicio: `GET /health` (liveness, sin dependencias) y `GET /ready` (BD y dependencias críticas → 200/503). **Aclaración (T1.3):** en `reservation`, `/ready` comprueba solo su BD; `availability`/`payment`/`customer`/`hotel` son degradables (la saga las reintenta) y no deben sacarlo de servicio |
| Errores | `{"error": {"code": "NO_INVENTORY", "message": "…", "request_id": "…", "details": {}}}` |

| HTTP | Uso |
|---|---|
| 200 / 201 / 202 | OK / creado / aceptado (en proceso) |
| 404 | No existe |
| 409 | Conflicto de negocio (`NO_INVENTORY`, `HOLD_CONFLICT`, `HOLD_EXPIRED`, `INVALID_STATE`, `EMAIL_EXISTS`) |
| 422 | Validación o reutilización de `Idempotency-Key` con otro cuerpo (`IDEMPOTENCY_KEY_REUSED`) |
| 429 | Límite del gateway |
| 503 | Dependencia no disponible, **fail-closed** (`DEPENDENCY_UNAVAILABLE`, con `Retry-After`) |
| 504 | Timeout |

## 2. Exposición por el gateway
| Ruta pública (`:8080`) | Servicio | Métodos |
|---|---|---|
| `/` | frontend estático | GET |
| `/api/customers`, `/api/customers/{id}` | customer | POST, GET |
| `/api/hotels`, `/api/hotels/{id}`, `/api/rooms/{id}` | hotel | GET |
| `/api/availability` | availability | GET (búsqueda) |
| `/api/reservations`, `/{id}`, `/{id}/events`, `/{id}/cancel` | reservation | POST, GET |
| `/api/notifications?reservation_id=` | notification | GET |

Todo lo demás (holds, inventario, pagos, `POST /notifications`, altas de hoteles) es **interno**: accesible solo por `backend-net` o por el listener `127.0.0.1:8081` bajo `/svc/<servicio>/…` (semillas y pruebas).

## 3. customer-service
| Método y ruta | Cuerpo → Respuesta |
|---|---|
| `POST /customers` | `{name, email}` → `201 {id, name, email, created_at}` · `409 EMAIL_EXISTS` |
| `GET /customers/{id}` | → `200 {id, name, email}` · `404` |

## 4. hotel-service
| Método y ruta | Cuerpo → Respuesta |
|---|---|
| `GET /hotels?city=` | → `200 [{id, name, city}]` |
| `GET /hotels/{id}` | → `200 {id, name, city, rooms:[{id, name, capacity, price_per_night_cents, currency}]}` |
| `GET /rooms/{id}` | → `200 {id, hotel_id, name, capacity, price_per_night_cents, currency}` · `404` |
| `POST /hotels`, `POST /hotels/{id}/rooms` *(interno)* | alta de datos maestros → `201` |

Los dos `POST` internos aceptan un `id` (UUID) **opcional** para siembras
deterministas: mismo `id` con el mismo contenido → `200`; mismo `id` con otro
contenido → `409 ID_CONFLICT`.

## 5. availability-service
**Lectura** (escala con réplicas, tolera datos ligeramente desactualizados):
| Método y ruta | Respuesta |
|---|---|
| `GET /availability?hotel_id&check_in&check_out` | `200 {hotel_id, check_in, check_out, rooms:[{room_id, available}]}` donde `available = min por noche (total − held − confirmed)` |

**Escritura** (interna, fail-closed, atómica, idempotente):
| Método y ruta | Cuerpo → Respuesta |
|---|---|
| `PUT /inventory/{room_id}` | `{hotel_id, from, to, total}` → `200` · `409` si `total < held + confirmed` |
| `POST /holds` | `{hold_id, room_id, check_in, check_out, units, ttl_seconds?}` → `201` nuevo / `200` repetido idéntico: `{hold_id, status:"HELD", expires_at}` · `409 NO_INVENTORY` · `409 HOLD_CONFLICT` (mismo `hold_id`, otros parámetros) · `503` |
| `POST /holds/{id}/extend` | `{ttl_seconds}` → `200 {expires_at}` · `409 HOLD_EXPIRED` |
| `POST /holds/{id}/confirm` | → `200 {status:"CONFIRMED"}` (idempotente) · `409 HOLD_EXPIRED` |
| `POST /holds/{id}/release` | → `200 {status:"RELEASED"}` (idempotente; libera un hold `HELD` o `CONFIRMED`) |
| `GET /holds/{id}` | → `200 {hold_id, status, expires_at, …}` |

Estados del hold: `HELD → CONFIRMED | RELEASED | EXPIRED`.

## 6. reservation-service
**`POST /reservations`** — cabecera `Idempotency-Key` obligatoria.
```json
{
  "customer_id": "uuid", "hotel_id": "uuid", "room_id": "uuid",
  "check_in": "2026-11-10", "check_out": "2026-11-13",
  "payment": { "method": "card", "token": "tok_demo", "simulate": "ok" }
}
```
`simulate` ∈ `ok | decline | error_before_processing | process_then_drop_response | slow` (solo si la simulación está habilitada).

| Resultado | Código |
|---|---|
| Estado estable alcanzado dentro de `SAGA_SYNC_WAIT_SECONDS` | `201` + representación |
| Aún en proceso | `202` + `Location: /reservations/{id}` + representación |
| Misma clave y mismo cuerpo (replay) | `200` + representación + `Idempotent-Replayed: true` |
| Misma clave, cuerpo distinto | `422 IDEMPOTENCY_KEY_REUSED` |
| Cliente/habitación inexistentes | `404` (sin registro) |
| `customer`/`hotel` no disponibles | `503 DEPENDENCY_UNAVAILABLE` (sin registro) |

Representación:
```json
{
  "id": "uuid", "status": "CONFIRMED", "status_reason": null,
  "customer_id": "uuid", "hotel_id": "uuid", "room_id": "uuid",
  "check_in": "2026-11-10", "check_out": "2026-11-13", "nights": 3,
  "amount_cents": 30000, "currency": "USD",
  "payment": { "payment_id": "uuid", "status": "SUCCEEDED" },
  "created_at": "…", "updated_at": "…"
}
```
Estados: `RECEIVED, HELD, PAYMENT_PENDING, PAYMENT_UNKNOWN, PAID, CONFIRMED, PAYMENT_DECLINED, REFUND_REQUIRED, CANCELLING, CANCELLED, REJECTED_NO_INVENTORY, FAILED_TECHNICAL, MANUAL_REVIEW` (transiciones en ADR-0003). `status_reason`: `DECLINED | TECHNICAL | NO_INVENTORY | …`.

| Método y ruta | Respuesta |
|---|---|
| `GET /reservations/{id}` | `200` representación · `404` |
| `GET /reservations/{id}/events` | `200 [{from, to, reason, at}]` (línea de tiempo para la demo) |
| `GET /reservations?customer_id=` | `200 [representación]` |
| `POST /reservations/{id}/cancel` | `200/202` → `CANCELLING/CANCELLED` · `409 INVALID_STATE` si no está `CONFIRMED` |

## 7. payment-service (interno)
**`POST /payments`** — `Idempotency-Key` obligatoria (= `reservation_id`).
```json
{ "reservation_id": "uuid", "amount_cents": 30000, "currency": "USD",
  "method": "card", "token": "tok_demo", "simulate": "ok" }
```
→ `200/201 {id, reservation_id, status, provider_ref?, updated_at}` con `status ∈ SUCCEEDED | DECLINED | FAILED_TECHNICAL | UNKNOWN`. Repetir con la misma clave devuelve el mismo pago, sin nuevo cobro.

| Método y ruta | Respuesta |
|---|---|
| `GET /payments/{id}` | `200` pago · `404` |
| `GET /payments?reservation_id=` | `200` pago actual (resuelve `UNKNOWN` consultando al proveedor) |
| `POST /payments/{id}/refund` | `200 {status:"REFUNDED"}` (idempotente; solo desde `SUCCEEDED`) |

## 8. notification-service
| Método y ruta | Cuerpo → Respuesta |
|---|---|
| `POST /notifications` *(interno)* | `{event_id, type, reservation_id, customer_id, payload}` → `202 {id, status:"PENDING"}` · repetido (`event_id`) → `200` el existente |
| `GET /notifications?reservation_id=` *(público, solo lectura)* | `200 [{id, event_id, type, status, attempts, sent_at}]` con `status ∈ PENDING | SENT | FAILED` |

Tipos de evento: `reservation.confirmed`, `reservation.cancelled`.

## 9. Flujo de llamadas permitido
`reservation → customer, hotel, availability, payment` y `reservation-worker → notification`. Ningún otro servicio llama a otro. Cualquier servicio → BD ajena: **prohibido**.

`hotel` es la fuente de verdad de hoteles, habitaciones y precios (ADR-0010); `reservation` la consulta por HTTP para validar antes de persistir. `availability` gestiona exclusivamente inventario, disponibilidad y holds, y no accede a datos maestros.

## 10. Autenticaci?n (F3c)

Cuenta = cliente en `customer-service`. Las cuentas y sesiones **no** exponen
contrase?as ni tokens almacenados (solo hashes).

| M?todo y ruta | Cuerpo ? Respuesta |
|---|---|
| `POST /auth/register` | `{name,email,password}` ? `201 {id,name,email}` ? `409 EMAIL_EXISTS` ? `422 WEAK_PASSWORD` |
| `POST /auth/login` | `{email,password}` ? `200 {access_token, token_type:"Bearer", expires_in, customer}` ? `401 INVALID_CREDENTIALS` gen?rico (usuario inexistente, clave err?nea o bloqueo) |
| `POST /auth/logout` (Bearer) | `204` idempotente; borra la sesi?n |
| `GET /auth/me` (Bearer) | `200 {id,name,email}` ? `401` |
| `GET /auth/validate` (interno) | `204` + `X-User-Id` si el Bearer es v?lido ? `401` |

- `Cache-Control: no-store` en login/register.
- Contrase?a: 10?128 caracteres, distinta del email/nombre y fuera de una lista
  de claves comunes; hash `scrypt$N$r$p$sal$hash` con par?metros por entorno.
- Sesi?n: token opaco de 32 bytes; en BD solo SHA-256; TTL 8 h; logout revoca.
- **P?blico:** `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`,
  `/api/auth/me`. **`/api/customers*` queda cerrado** (404); `POST /customers`
  y `GET /customers/{id}` son internos (semilla/pruebas).
- **Protecci?n:** `POST /api/reservations` y `POST /api/reservations/{id}/cancel`
  exigen `Authorization: Bearer`; sin token/ inv?lido ? `401`. El gateway
  inyecta `X-User-Id` y **borra** cualquier valor del cliente en el resto de
  rutas. En `POST /reservations`, si `X-User-Id` llega debe coincidir con
  `customer_id` (si no, `403 FORBIDDEN`); la cancelaci?n comprueba due?o
  (`404` si no). Los listeners admin/dev no inyectan la cabecera.
- **L?mites:** `auth_login` 20 r/m (burst 10), `auth_register` 10 r/m
  (burst 5), 429; bloqueo tras 5 fallos durante 300 s.

