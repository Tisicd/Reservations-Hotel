# Evidencias visuales para el informe y la defensa

Lo que ya está generado **no necesita captura** (renderiza desde el repo).
Lo que sí hay que capturar se indica con el comando exacto y qué debe verse.

## A. Evidencias ya generadas (sin captura)

| Evidencia | Archivo | Cómo mostrarla |
|---|---|---|
| Inventario real de las 6 bases | `inventory.md` | GitHub/VS Code (tabla) |
| DDL real | `schema/<db>.sql` | abrir el archivo |
| ER por base (6) | `diagrams/<db>.md` | GitHub renderiza Mermaid |
| Diagrama lógico global | `diagrams/logical-global.md` | GitHub renderiza Mermaid |
| Integridad física/lógica | `integrity.md` | tabla |
| Consultas y resultados | `queries.sql`, `demo-results.md` | salida real de psql |

Para exportar los Mermaid a PNG/SVG: copia el bloque `mermaid` en
<https://mermaid.live> → `Actions` → `Download PNG/SVG`.

## B. Capturas manuales (checklist)

Guarda las imágenes en `docs/resultados/` o en una carpeta de tu presentación,
con nombres `ev-01-…png`, `ev-02-…png`, etc.

| # | Evidencia | Comando / URL | Qué debe verse |
|---|---|---|---|
| 1 | Stack completo sano | `docker compose -f compose.yaml -f compose.dev.yaml ps` o Docker Desktop | 15 contenedores `healthy`, `postgres` en `127.0.0.1:5433` |
| 2 | Las 6 bases en GUI | <http://127.0.0.1:8082> (Adminer) | selector de base con `customer_db`, `hotel_db`, `availability_db`, `payment_db`, `reservation_db`, `notification_db` |
| 3 | Conexión DBeaver | DBeaver → `Test Connection` | “Connected”, host `127.0.0.1`, puerto `5433`, 6 bases en el navegador |
| 4 | ER `customer_db` | `diagrams/customer_db.md` o DBeaver | `customers 1—N sessions` |
| 5 | ER `hotel_db` | ídem | `hotels 1—N rooms` |
| 6 | ER `availability_db` | ídem | `inventory` con PK compuesta `(room_id, night)`; `holds` |
| 7 | ER `reservation_db` | ídem | `reservations 1—N reservation_events`; `outbox` |
| 8 | ER `payment_db` | ídem | `payments 1—N ledger` y `1—N payment_attempts` |
| 9 | ER `notification_db` | ídem | `notifications` con `event_id` UNIQUE |
| 10 | Diagrama lógico global | `diagrams/logical-global.md` | 6 servicios, 6 bases, flechas punteadas sin FK |
| 11 | Tamaño de las bases | ver comando abajo | 6 filas con tamaño en kB/MB |
| 12 | Conteos por tabla | `inventory.md` o comando abajo | filas por tabla |
| 13 | Aislamiento de roles | comando abajo | error `permission denied for database "hotel_db"` |
| 14 | Revisión de migraciones | comando abajo | `0002` en customer, `0001` en el resto |
| 15 | Volumen persistente | comando abajo | `reservas-platform_pgdata` montado |
| 16 | Flujo real (opcional) | reservar en <http://127.0.0.1:8088> y repetir Q18–Q27 | una reserva nueva y sus eventos/outbox/notificación |

### Comandos para las capturas 11–15

```powershell
# 11. Tamaño de las 6 bases
docker exec reservas-platform-postgres-1 psql -U postgres -c `
  "select datname, pg_size_pretty(pg_database_size(datname)) as tamano
     from pg_database where datname like '%\_db' order by datname;"

# 12. Conteo por tabla (ejemplo)
docker exec reservas-platform-postgres-1 psql -U postgres -d reservation_db -c `
  "select 'reservations' t, count(*) from reservations
   union all select 'reservation_events', count(*) from reservation_events
   union all select 'outbox', count(*) from outbox;"

# 13. Aislamiento de roles (no muestra la contraseña)
$p = (Get-Content secrets/customer_db_password.txt -Raw).Trim()
docker exec -e PGPASSWORD=$p reservas-platform-postgres-1 `
  psql -U customer -d hotel_db -c "select 1;"

# 14. Versión de Alembic por base
foreach ($db in 'customer_db','hotel_db','availability_db','payment_db','reservation_db','notification_db') {
  docker exec reservas-platform-postgres-1 psql -U postgres -d $db -Atc "select '$db', version_num from alembic_version"
}

# 15. Volumen y punto de montaje
docker volume ls | Select-String pgdata
docker volume inspect reservas-platform_pgdata
```

## C. Privacidad: qué NO capturar

- `.env`, `secrets/`, variables de entorno de `docker inspect`.
- La pantalla de login de Adminer con la contraseña escrita.
- `customers.password_hash`, `sessions.token_hash`,
  `reservations.payment_token`, `request_hash`, `provider_ref`, payloads de
  `outbox`/`notifications`.
- Emails completos de clientes. Usa `queries.sql` (enmascara) o recorta la
  columna antes de la captura.
- Datos de tarjeta: el proyecto usa un proveedor **simulado**; aun así no
  muestres `payment_token`.

## D. Guion sugerido de 3 minutos

1. `ev-01`: stack sano y una sola entrada pública (gateway); PostgreSQL solo en loopback.
2. `ev-02` + `ev-03`: las 6 bases y la conexión.
3. `ev-10`: separación servicio↔base y referencias sin FK.
4. `ev-04`–`ev-09`: un ER por base, señalando PK/FK/UNIQUE/CHECK.
5. `ev-13`: el rol `customer` no puede abrir `hotel_db`.
6. `demo-results.md`: reserva → `reservation_events` → `outbox` → `notifications` → `payments`/`ledger`.
7. Cierre: integridad física 0 huérfanos; los huérfanos lógicos son residuo de E2E y la saga es la que garantiza la coherencia.

## E. Si algo falla al capturar

| Problema | Causa probable |
|---|---|
| Adminer no conecta | usaste `localhost` en vez de `host.docker.internal` |
| DBeaver no ve las 6 bases | activa `Show all databases` |
| `psql` pide contraseña dentro del contenedor | usa `-U postgres` por socket local (funciona sin contraseña) |
| Datos “raros” (hoteles sin habitaciones) | residuo de E2E; no afecta al esquema |
| Quieres una demo limpia | `make clean && make build && make up && make seed` (destructivo) |
