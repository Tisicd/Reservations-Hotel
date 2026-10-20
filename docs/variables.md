# Variables de entorno por servicio

Toda configuración y secretos viven en variables de entorno (o `*_FILE`). El
archivo `.env` (ignorado por Git) contiene los valores reales; `.env.example`
los nombres con valores de ejemplo. `docs/costos/registro.md` y esta tabla se
actualizan cuando se añade o cambia una variable.

## PostgreSQL (compose)

| Variable | Servicio | Obligatoria | Descripción |
|---|---|---|---|
| `POSTGRES_USER` | postgres | No (default `postgres`) | Superusuario administrativo del contenedor |
| `POSTGRES_PASSWORD` | postgres | Sí | Contraseña del superusuario (no se relaja `scram-sha-256` en conexiones host) |
| `POSTGRES_INITDB_ARGS` | postgres | No | Argumentos de `initdb`; fijado a `--data-checksums` (ADR-0002) |
| `CUSTOMER_DB_PASSWORD` | postgres (init) | Sí | Contraseña del rol `customer` (dueño de `customer_db`) |
| `HOTEL_DB_PASSWORD` | postgres (init) | Sí | Contraseña del rol `hotel` (dueño de `hotel_db`) |
| `AVAILABILITY_DB_PASSWORD` | postgres (init) | Sí | Contraseña del rol `availability` (dueño de `availability_db`) |
| `RESERVATION_DB_PASSWORD` | postgres (init) | Sí | Contraseña del rol `reservation` (dueño de `reservation_db`) |
| `PAYMENT_DB_PASSWORD` | postgres (init) | Sí | Contraseña del rol `payment` (dueño de `payment_db`) |
| `NOTIFICATION_DB_PASSWORD` | postgres (init) | Sí | Contraseña del rol `notification` (dueño de `notification_db`) |
| `POSTGRES_DEV_PORT` | compose (dev) | No (default `5433`) | Puerto loopback del PostgreSQL en el perfil dev (`compose.dev.yaml`) |

## availability-service

| Variable | Obligatoria | Default | Descripción |
|---|---|---|---|
| `DB_HOST` | No | `127.0.0.1` | Host de PostgreSQL (en compose: `postgres`) |
| `DB_PORT` | No | `5433` | Puerto de PostgreSQL (en compose: `5432`) |
| `DB_NAME` | No | `availability_db` | Base de datos |
| `DB_USER` | No | `availability` | Rol dueño de la BD |
| `DB_PASSWORD` | No | (vacío) | Contraseña en texto (solo para pruebas locales) |
| `DB_PASSWORD_FILE` | No | (vacío) | Ruta al archivo con la contraseña (Docker secret `/run/secrets/availability_db_password`) |
| `DB_POOL_SIZE` | No | `5` | Conexiones del pool por réplica/worker |
| `DB_POOL_TIMEOUT` | No | `2` | Segundos de espera por conexión del pool |
| `HOLD_DEFAULT_TTL_SECONDS` | No | `600` | TTL por defecto de un hold (10 min) |
| `HOLD_MAX_TTL_SECONDS` | No | `3600` | TTL máximo aceptado |
| `MAX_NIGHTS` | No | `30` | Noches máximas por rango |
| `MAX_UNITS` | No | `10` | Unidades máximas por hold |
| `EXPIRY_INTERVAL_SECONDS` | No | `5` | Intervalo de barrido del worker de expiración |
| `EXPIRY_BATCH` | No | `100` | Máximo de holds expirados por barrido |
| `WORKER_HEARTBEAT_FILE` | No | `/tmp/heartbeat` | Archivo que el worker toca en cada iteración; el healthcheck falla si tiene más de `3 × EXPIRY_INTERVAL_SECONDS` |
| `LOG_LEVEL` | No | `INFO` | Nivel de log (JSON en stdout) |

`DB_PASSWORD` y `DB_PASSWORD_FILE` son mutuamente excluyentes en la práctica: el
servicio lee `DB_PASSWORD_FILE` si está presente; si no, cae a `DB_PASSWORD`. En
compose se usa el secret (`DB_PASSWORD_FILE`); en las pruebas locales el archivo
`secrets/availability_db_password.txt` (generado por `make secrets`).

## payment-service

| Variable | Obligatoria | Default | Descripción |
|---|---|---|---|
| `DB_HOST` | No | `127.0.0.1` | Host de PostgreSQL (en compose: `postgres`) |
| `DB_PORT` | No | `5433` | Puerto de PostgreSQL (en compose: `5432`) |
| `DB_NAME` | No | `payment_db` | Base de datos |
| `DB_USER` | No | `payment` | Rol dueño de la BD |
| `DB_PASSWORD` | No | (vacío) | Contraseña en texto (solo pruebas locales) |
| `DB_PASSWORD_FILE` | No | (vacío) | Ruta al archivo con la contraseña (Docker secret `/run/secrets/payment_db_password`) |
| `DB_POOL_SIZE` | No | `5` | Conexiones del pool por réplica/worker |
| `DB_POOL_TIMEOUT` | No | `2` | Segundos de espera por conexión del pool |
| `PAYMENT_SIMULATION_ENABLED` | No | `false` | Habilita los modos `simulate` ≠ `ok`. En compose base (despliegue) es `false`; el perfil dev la activa |
| `PROVIDER_TIMEOUT_SECONDS` | No | `3` | Timeout de la llamada al proveedor; al vencer el pago queda `UNKNOWN` |
| `PROVIDER_SLOW_SECONDS` | No | `6` | Duración del modo `slow` (mayor que el timeout para forzar `UNKNOWN`) |
| `RECONCILE_INTERVAL_SECONDS` | No | `5` | Intervalo del worker de reconciliación |
| `RECONCILE_MIN_AGE_SECONDS` | No | `2` | Antigüedad mínima de un `UNKNOWN` para reconciliarlo |
| `RECONCILE_BATCH` | No | `100` | Máximo de pagos `UNKNOWN` por barrido |
| `WORKER_HEARTBEAT_FILE` | No | `/tmp/heartbeat` | Archivo tocado por el worker; el healthcheck falla si tiene más de `3 × RECONCILE_INTERVAL_SECONDS` |
| `LOG_LEVEL` | No | `INFO` | Nivel de log (JSON en stdout) |

En las pruebas locales el secreto se lee de `secrets/payment_db_password.txt`
(generado por `make secrets`).

## reservation-service

| Variable | Obligatoria | Default | Descripción |
|---|---|---|---|
| `DB_HOST` | No | `127.0.0.1` | Host de PostgreSQL (en compose: `postgres`) |
| `DB_PORT` | No | `5433` | Puerto de PostgreSQL (en compose: `5432`) |
| `DB_NAME` | No | `reservation_db` | Base de datos |
| `DB_USER` | No | `reservation` | Rol dueño de la BD |
| `DB_PASSWORD` | No | (vacío) | Contraseña en texto (solo pruebas locales) |
| `DB_PASSWORD_FILE` | No | (vacío) | Ruta al archivo con la contraseña (Docker secret `/run/secrets/reservation_db_password`) |
| `DB_POOL_SIZE` | No | `5` | Conexiones del pool por réplica/worker |
| `DB_POOL_TIMEOUT` | No | `2` | Segundos de espera por conexión del pool |
| `AVAILABILITY_URL` | No | `http://127.0.0.1:8101` | Base URL de availability (compose: `http://availability:8000`) |
| `PAYMENT_URL` | No | `http://127.0.0.1:8102` | Base URL de payment (compose: `http://payment:8000`) |
| `CUSTOMER_URL` | No | `http://127.0.0.1:8080` | Base URL de customer (compose: `http://customer:8000`) |
| `HOTEL_URL` | No | `http://127.0.0.1:8080` | Base URL de hotel (compose: `http://hotel:8000`) |
| `HTTP_CONNECT_TIMEOUT_SECONDS` | No | `1` | Timeout de conexión de los clientes |
| `HTTP_READ_TIMEOUT_SECONDS` | No | `2` | Timeout de lectura (availability/customer/hotel) |
| `PAYMENT_READ_TIMEOUT_SECONDS` | No | `5` | Timeout de lectura del cliente de payment |
| `SAGA_SYNC_WAIT_SECONDS` | No | `5` | Espera máxima del `POST /reservations` antes de responder 202 |
| `HOLD_TTL_SECONDS` | No | `600` | TTL del hold al crearlo/extenderlo |
| `SAGA_HOLD_DEADLINE_SECONDS` | No | `60` | Plazo para conseguir el hold desde `RECEIVED` |
| `PAYMENT_MAX_TECHNICAL_RETRIES` | No | `3` | Intentos técnicos antes de `PAYMENT_DECLINED(TECHNICAL)` |
| `PAYMENT_RECONCILE_DEADLINE_SECONDS` | No | `900` | Plazo de reconciliación de `PAYMENT_UNKNOWN` |
| `CONFIRM_DEADLINE_SECONDS` | No | `120` | Plazo para confirmar el hold estando `PAID` |
| `MANUAL_REVIEW_HOLD_TTL_SECONDS` | No | `86400` | Extensión del hold al pasar a `MANUAL_REVIEW` |
| `BACKOFF_BASE_SECONDS` | No | `0.5` | Base del backoff exponencial |
| `BACKOFF_MAX_SECONDS` | No | `30` | Tope del backoff |
| `LEASE_SECONDS` | No | `15` | Vigencia del lease de `claim`/`claim_due` |
| `RECOVERY_INTERVAL_SECONDS` | No | `2` | Intervalo del worker de recuperación |
| `RECOVERY_BATCH` | No | `20` | Máximo de reservas por barrido |
| `MAX_NIGHTS` | No | `30` | Noches máximas por reserva |
| `WORKER_HEARTBEAT_FILE` | No | `/tmp/heartbeat` | Archivo tocado por el worker; el healthcheck falla si tiene más de `3 × RECOVERY_INTERVAL_SECONDS` |
| `LOG_LEVEL` | No | `INFO` | Nivel de log (JSON en stdout) |

En las pruebas locales el secreto se lee de `secrets/reservation_db_password.txt`
(generado por `make secrets`).

## Convenciones

- Los roles y bases se crean en `scripts/init-db.sh`, que solo se ejecuta en el
  primer arranque (volumen `pgdata` vacío). Tras cambiar `*.DB_PASSWORD` **o los
  timeouts por rol** (`ALTER ROLE … SET`) hay que `make clean && make up` para
  recrear: el script no se re-ejecuta sobre un volumen existente.
- Los timeouts de BD son **por rol** (`statement_timeout=5s`, `lock_timeout=2s`,
  `idle_in_transaction_session_timeout=10s`, ADR-0002); el servidor no fija
  valores globales. Así un `lock_timeout` no excede la espera síncrona de la saga
  (5 s).
- `CUSTOMER_DB_PASSWORD` y afines solo los consume el script de init; cada
  servicio leerá después su propia variable de conexión (se documenta en F1).
- En Windows, `make` se ejecuta con GNU Make (ezwinports) y `docker compose`;
  el perfil dev publica PostgreSQL solo en `127.0.0.1`.
