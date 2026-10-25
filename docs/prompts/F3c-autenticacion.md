# Prompt para OpenCode: F3c autenticación básica (reservar exige iniciar sesión)

> Rama: `feat/f3c-auth`, desde `main` **con F3b ya fusionada y el tag `v1.0.1-entrega` creado** (línea base segura). **Tope duro: 5 h.** Si no queda verde y verificada, **no se fusiona** y la entrega es `v1.0.1-entrega`. Commits por hito. Explorar el sitio **sigue siendo público**; solo **reservar** exige sesión.

---

## ROL
Ingeniero de software con criterio de seguridad. Arquitectura aceptada. Esta tarea es **transversal** (customer, gateway, reservation, UI): cambia lo mínimo, prueba todo y no rompas el flujo interno de pruebas.

## LEE
`docs/03-estado-del-proyecto.md`, `docs/adr/0001`, `0007`, `0008`, `docs/05-contratos-api.md` (§1, §3, §6), `services/customer/**`, `services/reservation/app/api/**`, `gateway/conf.d/default.conf`, `gateway/html/**`, `docs/seguridad.md`, `tests/e2e/test_public_flow.py`, `scripts/smoke.py`, `scripts/check_ui_routes.py`.

## DECISIONES DE DISEÑO (no las cambies sin avisar; documéntalas en **ADR-0012**)
1. **Las cuentas viven en `customer-service`** (cuenta = cliente). Sin servicio nuevo.
2. **Contraseñas con `hashlib.scrypt` (biblioteca estándar, sin dependencias)**, sal aleatoria de 16 bytes, formato autodescriptivo `scrypt$N$r$p$sal_b64$hash_b64` (los parámetros viajan en el hash para poder subirlos). Parámetros por entorno (`SCRYPT_N`, `SCRYPT_R`, `SCRYPT_P`); **calibra** en esta máquina para ~100–250 ms por hash y respeta `maxmem`. Comparación con `hmac.compare_digest`. Concurrencia de hashing limitada (semáforo) para que el login no sea un vector de agotamiento de CPU.
3. **Sesiones opacas** (no JWT): token aleatorio de 32 bytes (`secrets.token_urlsafe`); en la BD **solo el hash SHA-256** del token, con `expires_at` (`AUTH_SESSION_TTL_SECONDS`, 8 h por defecto) y borrado en el *logout*. Sin clave de firma que gestionar y con revocación real.
4. **El token viaja como `Authorization: Bearer`** y la SPA lo guarda en `sessionStorage` (se borra al cerrar la pestaña). Es inmune a CSRF y la CSP estricta reduce el riesgo de XSS; en producción: cookie `HttpOnly` + TLS + CSRF (documéntalo).
5. **El gateway aplica la autenticación** con `auth_request` hacia `GET /auth/validate` (ruta **interna**, `internal;` en nginx, nunca pública), que responde `204` con `X-User-Id` o `401`. nginx **inyecta** `X-User-Id` hacia `reservation` y **lo elimina/sobrescribe en toda ruta pública** (no se puede falsificar desde fuera). **Antes de empezar verifica con `nginx -V` que el módulo `auth_request` está compilado en la imagen fijada;** si no, plan B: `reservation` valida el token llamando a `customer-service` (cliente HTTP propio) y se documenta.
6. **Frontera de confianza:** `reservation` confía en `X-User-Id` solo porque el único camino público pasa por el gateway. Los listeners de **desarrollo/admin** (loopback) no inyectan la cabecera y conservan el comportamiento actual, para no romper e2e, caos ni carga.

## ALCANCE
**Crear/modificar:** `services/customer/**`, `services/reservation/app/api/**` (solo identidad), `gateway/conf.d/default.conf`, `gateway/html/**`, `compose.yaml`/`compose.dev.yaml` (variables), `scripts/seed.py`, `scripts/smoke.py`, `scripts/check_ui_routes.py`, `tests/**`, `docs/**`, `Makefile`.
**Prohibido:** dependencias nuevas, servicio nuevo, recuperación de contraseña, verificación de email, MFA, OAuth, *roles* (todo eso queda fuera y se documenta como evolución).

## HITO A: backend de cuentas (commit `feat(customer): registro, login y sesiones`)
Migración `0002` en `customer_db`: `customers` + `password_hash text`, `failed_attempts int default 0`, `locked_until timestamptz`, `last_login_at timestamptz`; tabla `sessions(token_hash text pk, customer_id uuid fk, created_at, expires_at)` con índice por `customer_id` y `expires_at`. Mantén el índice único sobre `lower(email)`.
**Endpoints** (`docs/05-contratos-api.md` §3 se actualiza):
| Ruta | Comportamiento |
|---|---|
| `POST /auth/register` `{name,email,password}` | `201 {id,name,email}`; email normalizado (`strip` + minúsculas, ≤ 254); **duplicado ⇒ `409 EMAIL_EXISTS`** (también bajo concurrencia: 10 registros simultáneos del mismo email ⇒ 1 creado); política de contraseña: **mínimo 10 caracteres, máximo 128**, distinta del email y del nombre, **no** en una lista embebida de ~100 contraseñas comunes ⇒ `422 WEAK_PASSWORD` |
| `POST /auth/login` `{email,password}` | `200 {access_token, token_type:"Bearer", expires_in, customer:{id,name,email}}`; **error genérico idéntico** (`401 INVALID_CREDENTIALS`, mismo cuerpo y casi el mismo tiempo) para usuario inexistente, contraseña errónea o cuenta bloqueada: si el usuario no existe se verifica contra un **hash ficticio** para igualar el coste; **bloqueo temporal** tras `LOGIN_MAX_FAILURES=5` fallos seguidos durante `LOGIN_LOCK_SECONDS=300`; el éxito reinicia el contador; `Cache-Control: no-store` |
| `POST /auth/logout` (Bearer) | `204`, idempotente; elimina la sesión |
| `GET /auth/me` (Bearer) | `200 {id,name,email}` o `401` |
| `GET /auth/validate` (interna) | `204` + `X-User-Id` si el token es válido y no ha expirado; `401` si no |
**Reglas:** nunca registrar contraseñas ni tokens en logs ni en respuestas de error; solo el hash del token en BD; limpieza oportunista de sesiones expiradas; `POST /customers` y `GET /customers/{id}` quedan **solo internos** (semillas y pruebas).
**Pruebas (primero):** *unit* de `security.py` (hash/verify correctos e incorrectos, parámetros autodescriptivos, política de contraseña, hash ficticio para usuario inexistente, uso de comparación en tiempo constante); *integración con PostgreSQL real*: registro, duplicado (insensible a mayúsculas), concurrencia, login correcto/incorrecto con respuesta idéntica, bloqueo y desbloqueo por tiempo, expiración, logout invalida, **la BD no contiene el token en claro ni la contraseña**; ninguna traza de contraseña/token en los logs capturados durante las pruebas.

## HITO B: gateway e identidad en `reservation` (commit `feat(gateway,reservation): reservar exige sesión`)
- **Rutas públicas de autenticación** (listas cerradas): `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me` ⇒ `customer`; `/auth/validate` solo interna. **Cierra** `/api/customers*` en el listener público (403/404).
- **Límites propios:** zona `auth` estricta (p. ej. `limit_req` ≈ 20/min por IP con ráfaga 10 para *login* y ≈ 10/min con ráfaga 5 para *register*; ajusta con datos; respuesta **429**).
- **Autenticación obligatoria solo para reservar:** `POST /api/reservations` y `POST /api/reservations/{id}/cancel` ⇒ sin token o con token inválido/expirado **`401`** (cuerpo en el formato de error del contrato); los `GET` de exploración siguen públicos. Implementa la exigencia **por método** de forma segura (p. ej. `location` interna alcanzada por `rewrite … last`) y pruébala.
- **Identidad:** nginx hace `proxy_set_header X-User-Id $user_id_autenticado` en rutas protegidas y `proxy_set_header X-User-Id ""` en **todas** las demás rutas públicas hacia `reservation`.
- **`reservation`:** si llega `X-User-Id`, el `customer_id` del cuerpo **debe coincidir** (si no, `403 FORBIDDEN` con formato de error) y la reserva se hace a nombre de esa cuenta; si no llega (listeners de desarrollo/admin e internos), comportamiento actual. Sin cambios en la máquina de estados ni en el esquema.
**Pruebas (primero):** por el listener **público**: sin token ⇒ 401; token inválido ⇒ 401; token válido ⇒ 201 y la reserva queda a nombre de la cuenta; **falsificación:** enviar `X-User-Id` de otra cuenta con token válido ⇒ se usa la identidad del token (o 403 si el cuerpo no coincide) y **sin token ⇒ 401 aunque se envíe la cabecera**; rutas internas (`/auth/validate`, `/svc/...`, holds, pagos) no accesibles desde fuera; límite de *login* ⇒ 429; `/api/customers*` cerrado; los listeners de admin/dev siguen sirviendo e2e, caos y carga **sin cambios**.

## HITO C: interfaz (commit `feat(ui): inicio de sesión y registro`)
- Vistas `#/login` y `#/registro`; la cabecera muestra "Iniciar sesión / Crear cuenta" o el nombre con menú (Mis reservas · Cerrar sesión). **Explorar, resultados y fichas siguen sin sesión.**
- Al pulsar "Reservar" sin sesión ⇒ redirige a `#/login` con `returnTo` y, tras autenticarse, **vuelve al paso de reserva conservando la selección**. Se **elimina** la creación de huéspedes al vuelo y el "usuario demo".
- Formularios con `label`, `autocomplete="email"|"current-password"|"new-password"`, mostrar/ocultar contraseña, ayuda de política (≥ 10 caracteres), errores claros: login genérico, `409` "ese correo ya está registrado", `422 WEAK_PASSWORD`, `429` con espera, bloqueo temporal; sin `innerHTML` con datos de la API; CSP intacta.
- Token en `sessionStorage` y cabecera `Authorization` en las llamadas protegidas; un `401` en una llamada protegida ⇒ limpiar sesión y volver al login. **El registro de llamadas del modo demo técnico enmascara `Authorization` y cualquier campo de contraseña.**
- `scripts/check_ui_routes.py`: añade las rutas de `/api/auth/*`, verifica que **no** se usen `/api/customers*` y que ninguna llamada protegida omita el token.
- `scripts/seed.py`: crea una **cuenta de demostración** con contraseña tomada de `DEMO_USER_PASSWORD` (solo desarrollo, definida en `.env`/override; **no** hay valor por defecto en el perfil de producción).
- `tests/e2e/test_public_flow.py` se reescribe: **registro → login → reservar → sondear → eventos → notificaciones → reenviar con la misma clave → cancelar → logout**, más el caso negativo (reservar sin sesión ⇒ 401).

## HITO D (opcional; si hay tiempo): propiedad de las reservas (commit `feat(reservation): solo el dueño ve y cancela`)
Con `X-User-Id` presente: `GET /reservations/{id}`, `/events`, `/cancel` y `GET /reservations` (la lista usa la identidad, no `customer_id` del cliente) solo para el **dueño** (otro usuario ⇒ `404`). Esto cierra la limitación "cualquiera con un UUID lee reservas ajenas". Pruebas con dos cuentas.

## DOCUMENTACIÓN (commit `docs: ADR-0012 y seguridad de autenticación`)
ADR-0012 (alternativas: JWT, cookies `HttpOnly`, Keycloak/OIDC, bcrypt/argon2; decisión y consecuencias), actualización de `docs/05-contratos-api.md`, `seguridad.md` (amenazas: fuerza bruta, enumeración, robo de sesión, XSS, CSRF, abuso de registro; lo que **no** resuelve: sin verificación de email, sin recuperación, sin MFA, sin TLS, sin anti-bot, enumeración residual por el registro), `produccion.md`, `variables.md` (nuevas variables) con `make check-docs` en verde, `manual.md` y `RELEASE.md`.

## CRITERIOS DE ACEPTACIÓN (muestra salidas)
- [ ] `nginx -V` confirma `auth_request` (o plan B documentado).
- [ ] Hitos A, B, C en verde: `make lint`, `make test`, `make e2e`, `make smoke`, `make check-ui`, `make check-docs`, `make invariants` ⇒ 0.
- [ ] **Regresión de lo interno:** `make chaos SCEN=A` y `make perf PERF=P1` (versión corta) siguen funcionando por el listener admin.
- [ ] Reservar sin sesión ⇒ 401; con sesión ⇒ flujo completo; falsificación de `X-User-Id` rechazada; `/api/customers*` cerrado; 429 en *login*.
- [ ] Sin contraseñas ni tokens en BD (solo hashes), en logs ni en el registro del modo demo técnico (demuéstralo con `grep`).
- [ ] Sin dependencias nuevas; imágenes del producto: las mismas 6, 0 huérfanas.
- [ ] **Ensayo desde cero reducido** en clon nuevo (proyecto aislado): `make build && make up && make seed && make test && make e2e && make smoke && make check-ui && make check-docs && make invariants`; cronometrado en `docs/resultados/ensayo-desde-cero.md`.
- [ ] Informe con archivos, salidas, desviaciones y los **`PENDIENTE`**.
**Recortes (en orden):** D, el bloqueo por intentos fallidos (documentar), mejoras de UX de formularios. **Obligatorios:** A, B y C con las pruebas negativas de seguridad. **Si B no queda sólida, no fusionar.**

## ENTREGA
PR con la plantilla; propón el tag `v1.1.0-entrega` (los tags anteriores quedan como respaldo). No fusiones a `main`.

## REGLAS
Sin dependencias nuevas · nunca registrar secretos · respuestas de error indistinguibles en el login · nada interno expuesto · lo interno de pruebas no se rompe · si cambias arquitectura más allá de lo indicado, propón el ADR y detente.
