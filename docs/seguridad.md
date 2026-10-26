# Seguridad (punto 12 del enunciado)

> Evidencia: `tests/infra/test_gateway.py`, `tests/e2e/test_public_flow.py`,
> `scripts/smoke.py`, `docs/resultados/perf_P4.md`,
> `docs/resultados/seguridad-trivy.txt`, `docs/resultados/gitleaks.json`
> (local, ignorado por git) y `docs/adr/0007`.

## 1. Qué se expone y qué no

| Puerto (host) | Perfil | Quién escucha | Rutas |
|---|---|---|---|
| `127.0.0.1:8088` → `8080` | dev (`make up`/`up-dev`) | gateway nginx | `/`, `/app.js`, `/styles.css`, `/healthz`, `/api/*` |
| `8080` | prod (`make up-prod`) | gateway nginx | igual que arriba (sin el listener admin) |
| `127.0.0.1:8081` | dev | gateway (listener **admin**) | `/healthz`, `/svc/<servicio>/*`, `/api/*` **sin** `limit_*` |
| `127.0.0.1:5433` → `5432` | dev | PostgreSQL | solo loopback, para `make seed`/pruebas |

Rutas públicas (solo `/api/*`):

| Ruta | Métodos | Uso |
|---|---|---|
| `/api/hotels`, `/api/hotels/{id}`, `/api/rooms/{id}` | GET | búsqueda |
| `/api/availability` | GET | disponibilidad |
| `/api/customers`, `/api/customers/{id}` | GET/POST | alta/consulta de cliente |
| `/api/reservations`, `/{id}`, `/{id}/events`, `/{id}/cancel` | GET/POST | reserva y timeline |
| `/api/notifications?reservation_id=` | GET | estado de notificación |

No expuestas: `/svc/*`, holds, pagos, inventario y los POST internos de
hoteles/habitaciones. Evidencia: `test_public_flow.py` comprueba 403/404 para
`/svc/customer/health`, `POST /api/holds`, `GET /api/payments`,
`PUT /api/availability/inventory/...` y `POST /api/hotels`;
`test_gateway.py` comprueba las rutas públicas y los 404;
`scripts/smoke.py` comprueba que `/svc/...` no se sirve.

## 2. Redes y aislamiento

- `edge-net`: solo gateway (salida a host) y servicios que lo necesitan.
- `backend-net` (`internal: true`): gateway ↔ servicios.
- `data-net` (`internal: true`): servicios ↔ PostgreSQL.
- Solo el gateway publica puertos; los demás servicios no tienen `ports:`.
- `availability` corre con 3 réplicas detrás del pool DNS de nginx
  (`resolver 127.0.0.11 valid=1s`, `proxy_next_upstream` solo en idempotentes;
  ADR-0007).

## 3. Secretos y configuración

- Contraseñas de las 6 BDs en archivos (`secrets/*.txt`, ignorados por git),
  montados como **Docker secrets** y leídos con `DB_PASSWORD_FILE`; no hay
  credenciales en imágenes ni en `compose.yaml`.
- `.env` (ignorado) contiene solo valores de entorno; `.env.example` documenta
  los nombres. `scripts/gen_secrets.py` genera los archivos; `make secrets`
  los crea.
- `gitleaks v8.24.0` escaneó **64 commits** (1,39 MB) y reportó **0 hallazgos**
  (`docs/resultados/gitleaks.json`). Imagen usada solo para el escaneo, fuera
  del producto.

## 4. Contenedores

- Servicios de aplicación: `read_only: true`, `cap_drop: [ALL]`,
  `security_opt: no-new-privileges`, `mem_limit` (128–256 MB según el
  servicio), `pids_limit`, usuario no-root (`appuser`, uid 10001) y `/tmp` en
  `tmpfs`.
- Gateway: nginx `nginx:1.27.4-alpine`, usuario `101:101`, `read_only`,
  `mem_limit: 128m`.
- PostgreSQL: no es `read_only` (necesita el volumen `pgdata`), sin puerto
  fuera del loopback en dev y solo en `data-net` en prod.
- `HEALTHCHECK` en los 6 servicios (interval 5 s, timeout 5 s, retries 12,
  start_period 15 s) y en el gateway (`/healthz`).

## 5. Límites del gateway y evidencias

- `limit_req_zone ... rate=50r/s` y `limit_conn` **por IP**; `429` para ambos
  (ADR-0007). `/api/availability`: `burst=40`, `conn 20`;
  `/api/reservations`: `burst=20`, `conn 10`; `/api/customers`: `burst=20`,
  `conn 10`; `/api/hotels` y `/api/rooms`: `burst=40`, `conn 20`.
- P4 (`docs/resultados/perf_P4.md`): 200 peticiones en fase de tasa → **141
  respuestas 429**; 60 conexiones simultáneas → **45 respuestas 429**; el
  canario por el admin no recibió 429 (p95 32 → 95 ms, < 300 ms) y la
  recuperación fue de **10 ms**.
- 429 (límite del gateway) no se mezcla con 503 (fail-closed) ni 502/504
  (upstream). En la UI, 429 espera y reintenta; 503 reintenta con la misma
  clave.
- Los límites son por IP: con muchas IPs de origen no frenan un DDoS
  volumétrico; para eso se propone CDN/WAF en `produccion.md`.

## 6. Frontend

- CSP `default-src 'self'`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control:
  no-cache` (nginx, `gateway/conf.d/default.conf`).
- JS/CSS externos (sin inline), sin `innerHTML` con datos de la API
  (`textContent`/`createElement`), estáticos montados **ro**.
- `scripts/smoke.py` verifica las cabeceras, los tipos MIME y ausencia de
  scripts/estilos inline.

## 7. Integridad como control

- `Idempotency-Key` obligatoria en reservas y pagos; el replay devuelve **200**
  con `Idempotent-Replayed: true` y la misma reserva
  (`tests/e2e/test_public_flow.py`, ADR-0003).
- Escritura de inventario atómica y fail-closed (ADR-0005): P3/P3b confirman
  exactamente K unidades y 0 sobreventa (`perf_P3.md`, `perf_P3b.md`).
- El gateway no reintenta POST no idempotentes (`proxy_next_upstream off`).

## 8. Tabla de amenazas

| Amenaza | Qué se implementó | Evidencia | Qué NO resuelve |
|---|---|---|---|
| DNS / DDoS volumétrico | Nada en Compose; límites por IP | `perf_P4.md` (429 al saturar una IP) | No frena muchas IPs; requiere CDN/WAF/rate-limit distribuido |
| Saturación de conexiones | `limit_conn`/`limit_req` y 429; canario admin sin límites | P4: 141/45 429, canario estable | Límites por IP, no por usuario; el admin no debe exponerse |
| Agotamiento de recursos | `mem_limit`, `pids_limit`, `read_only`, `cap_drop`; sin CPU limits | `compose.yaml` | Host único; sin CPU limits ni cuotas por inquilino |
| Credenciales | Docker secrets por archivo, `.env` ignorado, gitleaks 0 | `secrets/`, `gen_secrets.py`, `gitleaks.json` | Sin rotación ni Vault; `.env` en disco local |
| Dependencias/imágenes | Tags fijados, multistage, non-root; trivy | `seguridad-trivy.txt`: 47 HIGH/0 CRITICAL por imagen | 44 CVEs de la base Debian sin fix + 3 de `starlette 0.41.3` (fix disponible); sin firma/SBOM/escaneo en CI |
| Inyección | SQLAlchemy parametrizado, Pydantic, sin `eval`/shell | Código + `make test`/`lint` | Sin pentest ni WAF; validación de negocio es la principal defensa |
| Autenticación/autorización | **No implementada** (demo) | — | Cualquiera con acceso al puerto público puede reservar; producción requiere auth |
| TLS | **No** en local (HTTP) | — | Credenciales/tokens en claro si se expone; producción requiere TLS |
| Exposición interna | Redes internal, rutas mínimas, 403/404 | `test_public_flow.py`, `test_gateway.py`, `smoke.py` | El listener admin en dev queda en loopback; no debe publicarse |

## 9. Escaneos ejecutados

- `aquasec/trivy:0.58.1` (fuera del producto), 6 imágenes `:local`,
  `--severity HIGH,CRITICAL`: **47 HIGH / 0 CRITICAL en cada imagen**
  (44 de la base Debian 13 + 3 de `starlette 0.41.3`). Detalle y CVEs en
  `docs/resultados/seguridad-trivy.txt`.
- `zricethezav/gitleaks:v8.24.0`: **0 leaks** en 64 commits.
- El build de la variante monoetapa requirió `--trusted-host` por el proxy TLS
  local; no afecta a las imágenes del producto (medición en `imagenes.md`).

## 10. Pendientes de seguridad (declarados)

- Actualizar `starlette` (y revisar FastAPI) para cerrar CVE-2025-62727,
  CVE-2026-48818 y CVE-2026-54283; reconstruir y re-escanear.
- Reconstruir la base (`python:3.12-slim`) cuando Debian publique fixes de los
  44 CVEs o fijar una base con soporte.
- Añadir autenticación, TLS, rotación de secretos, WAF/CDN, límites de CPU y
  escaneo en CI (ver `produccion.md` y `RELEASE.md`).

## Autenticación (F3c)

- **Cuentas en `customer-service`** (`password_hash` + bloqueo + sesiones). No
  hay servicio de identidad nuevo.
- **Contraseñas:** `hashlib.scrypt` con sal de 16 B y formato
  `scrypt$N$r$p$sal$hash`; `hmac.compare_digest`; parámetros por entorno
  (`SCRYPT_N/R/P`, por defecto 32768/8/1, ~200 ms medidos). Semáforo para
  limitar el coste concurrente y hash ficticio para usuarios inexistentes
  (mismo tiempo).
- **Sesiones opacas:** token de 32 B; en BD solo **SHA-256**; `expires_at`
  (8 h); logout borra; sin JWT ni clave de firma.
- **Transporte:** `Authorization: Bearer`; la SPA guarda el token en
  `sessionStorage` (no en localStorage); no se registra en logs ni en el panel
  demo. En producción: cookie `HttpOnly`/`Secure` + TLS + CSRF (ADR-0012).
- **Gateway:** `auth_request` contra `/_auth` → `GET /auth/validate` interno
  (204 + `X-User-Id` o 401). `X-User-Id` se inyecta **solo** en
  `POST /api/reservations` y `POST …/cancel`; en el resto de rutas públicas se
  vacía para impedir falsificación. `/api/customers*` cerrado (404).
  `/auth/validate` no es público.
- **Fuerza bruta / enumeración:** login genérico idéntico para usuario
  inexistente, clave errónea o bloqueo; 5 fallos → 300 s de bloqueo; rate limit
  `auth_login` 20 r/m (burst 10) y `auth_register` 10 r/m (burst 5) → 429.
  El registro aún devuelve `409` si el correo existe (enumeración residual,
  documentada).
- **Sesión robada / XSS:** hash en BD, expiración y revocación; CSP
  `default-src 'self'`, sin `innerHTML` con datos de la API, JS externo. El
  token en `sessionStorage` es accesible ante XSS: mitigado, no eliminado.
- **CSRF:** el token va en `Authorization`, no en cookie; no hay CSRF en el
  esquema actual. Al pasar a cookie `HttpOnly` hará falta token CSRF.
- **Abuso de registro:** rate limit y política de contraseñas; **no** hay
  verificación de email ni anti-bot/captcha.
- **Demo:** `admin`/dev sigue sin auth para e2e/caos/carga; la cuenta
  `demo@reservas-uce.test` se crea solo si `DEMO_USER_PASSWORD` está definida
  (dev) y no hay valor por defecto en el perfil de producción.
- **No resuelto:** TLS, MFA, recuperación de contraseña, verificación de
  email, roles, anti-bot, revocación global, y propiedad de los `GET` de
  reservas (Hito D no implementado; solo cancelar comprueba dueño).

Evidencia: ADR-0012, `services/customer/app/security.py`,
`auth_service.py`, migración `0002`, `gateway/conf.d/default.conf`,
`tests/customer/tests/...`, `tests/e2e/test_public_flow.py`.


## Rutas públicas finales (tag `v1.1.0-entrega`)

| Método | Ruta | Auth | Notas |
|---|---|---|---|
| GET | `/`, `/app.js`, `/styles.css`, `/js/*`, `/img/*` | — | estáticos con CSP; solo lectura |
| GET | `/healthz` | — | liveness del gateway |
| GET | `/api/hotels`, `/api/hotels/{id}`, `/api/rooms/{id}` | — | explorar |
| GET | `/api/availability` | — | buscar disponibilidad |
| GET | `/api/reservations`, `/api/reservations/{id}`, `/api/reservations/{id}/events` | — | lectura por UUID; propiedad pendiente (Hito D) |
| GET | `/api/notifications?reservation_id=` | — | lectura |
| GET | `/api/auth/me` | **Bearer** | cuenta actual |
| POST | `/api/auth/register`, `/api/auth/login` | — | límites `auth_register`/`auth_login`; 429 |
| POST | `/api/auth/logout` | **Bearer** | idempotente |
| POST | `/api/reservations` | **Bearer** | `X-User-Id` inyectado por el gateway |
| POST | `/api/reservations/{id}/cancel` | **Bearer** | comprueba dueño (404) |
| — | `/api/customers*`, `/api/auth/validate`, `/svc/*`, holds, pagos, inventario | **cerrado** | 403/404; `/auth/validate` solo interno |

El listener admin `:8081` es **loopback de desarrollo** (sin auth) para
e2e/caos/carga; no se publica en `up-prod`. `X-User-Id` se borra en el admin y
en el resto de rutas públicas.
