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
| `LOG_LEVEL` | No | `INFO` | Nivel de log (JSON en stdout) |

`DB_PASSWORD` y `DB_PASSWORD_FILE` son mutuamente excluyentes en la práctica: el
servicio lee `DB_PASSWORD_FILE` si está presente; si no, cae a `DB_PASSWORD`. En
compose se usa el secret (`DB_PASSWORD_FILE`); en las pruebas locales el archivo
`secrets/availability_db_password.txt` (generado por `make secrets`).

## Convenciones

- Los roles y bases se crean en `scripts/init-db.sh`, que solo se ejecuta en el
  primer arranque (volumen `pgdata` vacío). Tras cambiar `*.DB_PASSWORD` hay que
  `make clean && make up` para recrear.
- `CUSTOMER_DB_PASSWORD` y afines solo los consume el script de init; cada
  servicio leerá después su propia variable de conexión (se documenta en F1).
- En Windows, `make` se ejecuta con GNU Make (ezwinports) y `docker compose`;
  el perfil dev publica PostgreSQL solo en `127.0.0.1`.
