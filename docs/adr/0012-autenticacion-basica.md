# ADR-0012: autenticación básica (reservar exige sesión)

**Estado:** Aceptado · **Fase:** F3c

## Contexto

Explorar hoteles, fechas y precios sigue siendo público. Reservar y cancelar
son operaciones con impacto económico y deben quedar ligadas a una cuenta.
No hay servicio de identidad ni presupuesto para uno nuevo; las cuentas ya
existen como clientes en `customer-service`.

## Decisión

1. **Cuenta = cliente** en `customer-service`. Se añaden `password_hash`,
   intentos fallidos, bloqueo y `last_login_at`; tabla `sessions` con solo el
   **hash SHA-256** del token, `expires_at` e índice por cliente/expiración.
2. **Contraseñas con `hashlib.scrypt`** (stdlib, sin dependencias): sal de 16
   bytes y formato autodescriptivo `scrypt$N$r$p$sal_b64$hash_b64`.
   Parámetros por entorno (`SCRYPT_N/R/P`); por defecto N=32768 (~200 ms en el
   entorno de medida). Comparación con `hmac.compare_digest`; semáforo para
   limitar el hashing concurrente. Usuario inexistente se compara contra un
   **hash ficticio** para igualar el coste.
3. **Sesiones opacas**: token de 32 bytes (`secrets.token_urlsafe`), en BD solo
   su SHA-256, TTL 8 h (`AUTH_SESSION_TTL_SECONDS`), revocación real en
   logout. Sin JWT ni clave de firma.
4. **Bearer + `sessionStorage`** en la SPA; se borra al cerrar la pestaña. La
   CSP estricta reduce XSS; el token no se registra en logs ni en el panel
   técnico. En producción: cookie `HttpOnly` + `Secure` + TLS + CSRF.
5. **El gateway autentica con `auth_request`** (`--with-http_auth_request_module`
   confirmado en `nginx:1.27.4-alpine`) contra `/_auth` → `GET /auth/validate`
   interno. El endpoint responde `204` + `X-User-Id` o `401`. nginx inyecta
   `X-User-Id` solo en `POST /api/reservations` y `POST …/cancel`, y lo vacía
   en el resto de rutas públicas; el cliente no puede falsificarlo.
6. **Frontera de confianza:** `reservation` confía en `X-User-Id` solo desde el
   gateway público. En `POST /reservations`, si llega, debe coincidir con
   `customer_id` (si no, `403 FORBIDDEN`); en cancelación se comprueba el
   dueño (`404` si no). Los listeners admin/dev **no** inyectan la cabecera y
   conservan el comportamiento para e2e, caos y carga.
7. **Límites**: zonas `auth_login` (20 r/m, burst 10) y `auth_register`
   (10 r/m, burst 5) por IP, respuesta **429**; bloqueo tras
   `LOGIN_MAX_FAILURES=5` durante `LOGIN_LOCK_SECONDS=300`.

## Alternativas descartadas

- **JWT**: no hay clave de firma ni revocación inmediata; una sesión opaca con
  hash en BD permite logout real y no añade una dependencia.
- **Cookie `HttpOnly`**: más segura frente a XSS, pero exige CSRF y TLS; en la
  demo local (HTTP) se prefiere Bearer en `sessionStorage`, documentando la
  evolución a cookie+TLS.
- **Keycloak/OIDC**: sobredimensionado para una demo de un host y añade un
  servicio/operación que no se puede mantener en el plazo.
- **bcrypt/argon2**: buenas alternativas, pero requieren dependencias; scrypt
  está en la stdlib y cumple el coste objetivo.

## Consecuencias

(+) Sin dependencias nuevas; revocación real; el cliente no puede falsificar
la identidad; los tests internos no cambian.
(+) Login genérico, bloqueo temporal y rate limit disminuyen fuerza bruta y
enumeración por tiempo.
(−) Sin verificación de email, recuperación de contraseña, MFA, roles ni
anti-bot; el registro aún puede enumerar correos por `409` (se documenta).
(−) `sessionStorage` es vulnerable si hay XSS; la CSP y el uso de
`textContent`/`createElement` lo mitigan, no lo eliminan.
(−) Los `GET` de reservas siguen siendo públicos por UUID (Hito D no
implementado); solo la cancelación comprueba dueño.
(−) Sin TLS, el token viaja en claro en una red no confiable; fuera del
alcance local.

## Evidencia

`services/customer/app/security.py`, `auth_service.py`, migración `0002`,
`gateway/conf.d/default.conf`, `tests/customer/...`, `tests/e2e/test_public_flow.py`,
`docs/seguridad.md`, `docs/05-contratos-api.md`.
