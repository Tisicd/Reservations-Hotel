# Evidencias de bases de datos — reservas-platform

Recursos para **ver, explicar y evidenciar** las seis bases PostgreSQL del
proyecto sin tocar la lógica de negocio ni los datos. Todo lo de esta carpeta
se generó o verificó contra el esquema **real** del stack dev.

Inspección realizada el **2026-10-25/26 (UTC)** con el perfil dev levantado
(`make up`): PostgreSQL 16.14 en `127.0.0.1:5433`.

## Contenido

| Archivo | Qué es | Estado |
|---|---|---|
| `inventory.md` | Inventario real: bases, dueños, tamaño, tablas, columnas, PK/FK/UQ/CHECK, índices, filas | generado |
| `schema/<db>.sql` | DDL real de cada base (`pg_dump --schema-only`, sin datos ni credenciales) | generado |
| `diagrams/<db>.md` | Diagrama ER Mermaid por base (renderiza en GitHub) | generado |
| `diagrams/logical-global.md` | Diagrama lógico: 6 servicios, 6 bases y referencias entre servicios | curado |
| `integrity.md` | Integridad física (FK) y lógica (referencias sin FK) | generado |
| `queries.sql` | Consultas de demostración, solo lectura, con datos enmascarados | verificado |
| `demo-results.md` | Salida íntegra de `queries.sql` contra el stack real | verificado |
| `dbeaver.md` | Guía para conectar DBeaver Community y exportar diagramas | documentado |
| `informe.md` | Sección lista para el informe académico | curado |
| `evidencias.md` | Checklist de capturas manuales para la defensa | curado |
| `generate.py` | Regenera inventario, DDL, ER e integridad | verificado |

## Las seis bases (verificado)

| Base | Rol dueño | Tablas de dominio | Filas | Tamaño |
|---|---|---|---:|---:|
| `customer_db` | `customer` | `customers`, `sessions` | 17 | 7767 kB |
| `hotel_db` | `hotel` | `hotels`, `rooms` | 20 | 7671 kB |
| `availability_db` | `availability` | `inventory`, `holds` | 972 | 7983 kB |
| `payment_db` | `payment` | `payments`, `payment_attempts`, `ledger`, `sim_provider_charges` | 163 | 8039 kB |
| `reservation_db` | `reservation` | `reservations`, `reservation_events`, `outbox` | 465 | 8383 kB |
| `notification_db` | `notification` | `notifications` | 29 | 7791 kB |

Las 6 tienen además `alembic_version` (control de migraciones), que se omite
del inventario detallado y de los diagramas.

Hay **5 FK físicas** en total (todas dentro de una misma base) y
**11 referencias lógicas** entre servicios, sin FK, por diseño (ADR-0002).
El detalle está en `integrity.md` y `diagrams/logical-global.md`.

## Inicialización y persistencia (leído en `compose.yaml`/`init-db.sh`)

- `postgres` monta el volumen `pgdata` en `/var/lib/postgresql/data` y arranca
  con `--data-checksums`; los datos sobreviven a `make down` + `make up`.
- En el **primer** arranque (volumen vacío), `scripts/init-db.sh` se ejecuta
  desde `/docker-entrypoint-initdb.d`: crea los 6 roles, las 6 bases, revoca
  `CONNECT` de `PUBLIC` y fija los timeouts por rol. Si cambias ese script,
  necesitas un volumen nuevo (`make clean`); no se re-ejecuta.
- Las tablas las crea **Alembic** en los servicios `*-migrate`
  (`alembic upgrade head`), que corren antes de cada servicio y terminan en
  `Exited (0)`.
- `make clean` ejecuta `docker compose down -v` y borra el volumen;
  `make clean-all` además borra `secrets/seed.json`.
- Comandos de inspección que ya existían en el repo: `make invariants`
  (`tests/invariants/checker.py`), `make report` (`scripts/report.py`),
  `make images` (`scripts/docker_images.py`) y `make backup` / `make restore`
  (`scripts/backup.py`, `scripts/restore.py`).

## Conexión local (verificado)

El perfil dev publica PostgreSQL **solo en loopback**:

| Parámetro | Valor |
|---|---|
| Host | `127.0.0.1` |
| Puerto | `5433` (`POSTGRES_DEV_PORT`, verificado con conexión real) |
| Base | `postgres` (o cualquiera de las 6) |
| Usuario admin | `postgres` (`POSTGRES_USER`) |
| Contraseña | valor de `POSTGRES_PASSWORD` en `reservas-platform/.env` |

- La contraseña **no se copia aquí**. Ábrela en tu editor local
  (`reservas-platform/.env`) y pégala solo en la herramienta gráfica.
- En `compose.yaml` (perfil público/prod) PostgreSQL **no publica puertos**;
  el `5433` viene de `compose.dev.yaml`. Si no aparece, comprueba que
  levantaste con `make up`/`make up-dev`.
- Roles de servicio: cada uno es dueño de su base y **no puede conectarse a
  las demás**. Contraseñas en `secrets/<servicio>_db_password.txt`.

### Aislamiento de roles (verificado)

Con la contraseña de `customer`:

```powershell
$env:PGPASSWORD = (Get-Content secrets/customer_db_password.txt -Raw).Trim()
docker exec -e PGPASSWORD=$env:PGPASSWORD reservas-platform-postgres-1 `
  psql -U customer -d customer_db -c "select current_user, current_database();"
# OK: customer | customer_db

docker exec -e PGPASSWORD=$env:PGPASSWORD reservas-platform-postgres-1 `
  psql -U customer -d hotel_db -c "select 1;"
# FATAL: permission denied for database "hotel_db"
```

## Ver las bases

### Opción rápida: Adminer (GUI web, un contenedor)

```powershell
docker run -d --rm --name adminer -p 127.0.0.1:8082:8080 adminer:4
```

Abre <http://127.0.0.1:8082>: sistema **PostgreSQL**, servidor
`host.docker.internal:5433`, usuario `postgres`, contraseña de `.env`, base
vacía para ver las 6. Para apagarlo: `docker stop adminer`.

### Opción de escritorio: DBeaver

Ver `dbeaver.md`. DBeaver permite ER por base y exportar PNG/SVG; no instalado
en este entorno, por lo que esos pasos están documentados, no ejecutados.

### Línea de comandos

```powershell
# shell interactivo dentro del contenedor
docker exec -it reservas-platform-postgres-1 psql -U postgres

# una consulta
docker exec reservas-platform-postgres-1 psql -U postgres -d reservation_db -c "\dt"
```

## Reproducir los artefactos

Desde `reservas-platform/`, con el stack dev levantado:

```powershell
# 1. Inventario + DDL + ER + integridad
.venv\Scripts\python.exe docs/database-evidence/generate.py

# 2. Consultas de demostración (solo lectura)
Get-Content -Raw docs/database-evidence/queries.sql |
  docker exec -i reservas-platform-postgres-1 psql -U postgres
```

`generate.py` solo lee `information_schema`/`pg_catalog`, hace `count(*)` y usa
`pg_dump --schema-only`. No escribe en las bases, no reinicia servicios y no
toca `pgdata`.

## Datos sensibles

No se incluyen en los artefactos: `customers.password_hash`,
`sessions.token_hash`, `reservations.payment_token`, `payment_token` en
general, `request_hash`, `idempotency_key`, `provider_ref` ni payloads de
`outbox`/`notifications`. `customers.email` se muestra enmascarado (`e***@…`).

Para capturas: usa `queries.sql` (ya enmascara) o limita columnas a mano. No
captures `.env`, `secrets/`, `docker inspect` ni la salida de `\d+ customers`.

## Limitaciones y notas

- **No hay FK entre bases** de servicios distintos (ADR-0002). `integrity.md`
  comprueba esas referencias por software; un huérfano lógico es un dato a
  revisar, no una violación del esquema.
- Los datos actuales contienen **residuo de pruebas E2E**: 2 filas de
  `inventory` y 2 `holds` con `room_id` que no existe en `hotel_db`, y 1
  notificación con `reservation_id`/`event_id`/`customer_id` inexistentes. Se
  explica en `integrity.md`.
  Para una demo limpia: `make clean && make build && make up && make seed`
  (destructivo; no lo ejecutes sin querer perder los datos actuales).
- DBeaver no está instalado: `dbeaver.md` son pasos manuales. Mermaid se
  renderiza en GitHub; para PNG/SVG usa <https://mermaid.live>.
- El tamaño en disco y los conteos cambian con el uso; vuelve a ejecutar
  `generate.py` antes de la entrega.
