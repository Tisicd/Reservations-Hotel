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

## Convenciones

- Los roles y bases se crean en `scripts/init-db.sh`, que solo se ejecuta en el
  primer arranque (volumen `pgdata` vacío). Tras cambiar `*.DB_PASSWORD` hay que
  `make clean && make up` para recrear.
- `CUSTOMER_DB_PASSWORD` y afines solo los consume el script de init; cada
  servicio leerá después su propia variable de conexión (se documenta en F1).
- En Windows, `make` se ejecuta con GNU Make (ezwinports) y `docker compose`;
  el perfil dev publica PostgreSQL solo en `127.0.0.1`.
