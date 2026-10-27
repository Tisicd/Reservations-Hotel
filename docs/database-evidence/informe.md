# Sección para el informe — separación de datos en reservas-platform

> Material listo para copiar/adaptar al informe académico. Los números
> corresponden a la inspección del **2026-10-26 (UTC)** sobre el stack dev;
> se pueden recalcular con `generate.py`. Las evidencias visuales están en
> `evidencias.md` y los resultados de consultas en `demo-results.md`.

## 1. Objetivo y método

Se inspeccionó el esquema **real** de las seis bases PostgreSQL del proyecto
(no solo las migraciones) usando `information_schema`, `pg_catalog`,
`pg_dump --schema-only` y consultas de conteo de solo lectura sobre el stack
levantado con Docker Compose. El repositorio y la base se contrastaron entre
sí; no se modificó ninguna tabla ni dato.

## 2. Separación de datos: una base por servicio

La plataforma usa **una instancia PostgreSQL 16 compartida** con **seis bases
lógicas independientes** y **seis roles propietarios** (ADR-0002):

| Base | Rol dueño | Servicio |
|---|---|---|
| `customer_db` | `customer` | cuentas, login y sesiones |
| `hotel_db` | `hotel` | hoteles y habitaciones (datos maestros) |
| `availability_db` | `availability` | inventario por noche y holds |
| `reservation_db` | `reservation` | reservas, eventos de estado y outbox |
| `payment_db` | `payment` | pagos, intentos, ledger y proveedor simulado |
| `notification_db` | `notification` | outbox de notificaciones |

Cada rol es dueño de su base y **no puede conectarse a las demás**:
`scripts/init-db.sh` revoca `CONNECT` de `PUBLIC` y asigna un dueño por base.
Esto se verificó en vivo:

```
customer → customer_db : OK
customer → hotel_db    : FATAL: permission denied for database "hotel_db"
```

El aislamiento es **lógico, no físico**: las seis bases viven en el mismo
contenedor y volumen `pgdata`, pero ningún servicio lee ni escribe la base de
otro. La comunicación entre servicios es HTTP (`docs/05-contratos-api.md`),
nunca SQL cruzado.

## 3. Modelo físico por base

| Base | Tablas de dominio | Rol en el negocio |
|---|---|---|
| `customer_db` | `customers`, `sessions` | identidad, credenciales y sesiones |
| `hotel_db` | `hotels`, `rooms` | catálogo maestro; precios y capacidad |
| `availability_db` | `inventory`, `holds` | disponibilidad atómica por `(room_id, night)` |
| `payment_db` | `payments`, `payment_attempts`, `ledger`, `sim_provider_charges` | cobro idempotente y conciliación |
| `reservation_db` | `reservations`, `reservation_events`, `outbox` | saga, máquina de estados, eventos |
| `notification_db` | `notifications` | outbox de entrega al menos una vez |

Todas incluyen `alembic_version`, que registra la migración aplicada
(`customer_db` va por `0002`, el resto por `0001`). El inventario completo
—columnas, tipos, nulabilidad, defaults, PK/FK/UQ/CHECK e índices— está en
`inventory.md` y el DDL en `schema/`.

Observaciones de diseño visibles en el esquema:

- **Claves UUID generadas por la aplicación** en todas las tablas de dominio,
  lo que evita colisiones entre servicios. La única secuencia es
  `reservation_events_id_seq` (`BIGINT`), usada para dar orden total al log de
  transiciones de una reserva.
- **Idempotencia persistida**: `reservations.idempotency_key` y
  `payments.idempotency_key` son `UNIQUE`; `payments.reservation_id` también es
  `UNIQUE`, de modo que una reserva no puede tener dos pagos.
- **Máquina de estados en la base**: `reservations.status` admite 13 estados
  (`RECEIVED`, `HELD`, `PAYMENT_PENDING`, `PAYMENT_UNKNOWN`, `PAID`,
  `CONFIRMED`, `PAYMENT_DECLINED`, `REFUND_REQUIRED`, `CANCELLING`,
  `CANCELLED`, `REJECTED_NO_INVENTORY`, `FAILED_TECHNICAL`, `MANUAL_REVIEW`) y
  `holds.status` cuatro (`HELD`, `CONFIRMED`, `RELEASED`, `EXPIRED`), todos con
  `CHECK`. Cada transición queda auditada en `reservation_events`
  (`from_status`, `to_status`, `reason`).
- **Disponibilidad como invariante física**: `inventory` tiene PK
  `(room_id, night)` y `CHECK (held + confirmed <= total)` (ADR-0005). La
  condición se refuerza además con `UPDATE … WHERE` atómico en la capa de
  aplicación.
- **Pago con estados explícitos**: `payments.status` distingue `DECLINED`,
  `FAILED_TECHNICAL` y `UNKNOWN` (ADR-0006); `ledger` restringe
  `(payment_id, kind)` a un `CHARGE` y un `REFUND` por pago, y
  `sim_provider_charges` usa la `idempotency_key` como PK para simular la
  idempotencia del proveedor.
- **Outbox e índices parciales**: `outbox.status` solo admite `PENDING`/`SENT`
  y el índice `idx_outbox_pending` filtra por `status = 'PENDING'`; lo mismo
  ocurre con `idx_notifications_pending`, `idx_holds_expires_held`,
  `idx_payments_unknown` e `idx_reservations_due`. Son índices operativos para
  los workers, no para consultas de usuario.
- **Deduplicación de notificaciones**: `notifications.event_id` es `UNIQUE`,
  lo que materializa la entrega “al menos una vez” sin duplicar avisos
  (ADR-0004).
- **Restricciones de dominio**: `rooms.price_per_night_cents > 0`,
  `capacity` entre 1 y 10, moneda `USD`; en reservas, `check_out > check_in`,
  `nights > 0` y `amount_cents > 0`.

## 4. Relaciones físicas y relaciones lógicas

Hay que distinguir dos niveles, y el proyecto los separa a propósito:

**Relaciones físicas (5 FK, todas dentro de una misma base).** PostgreSQL las
garantiza:

| Base | FK | Semántica |
|---|---|---|
| `customer_db` | `sessions.customer_id → customers.id` | sesiones de un cliente (CASCADE) |
| `hotel_db` | `rooms.hotel_id → hotels.id` | habitaciones de un hotel (RESTRICT) |
| `payment_db` | `ledger.payment_id → payments.id` | asientos de un pago |
| `payment_db` | `payment_attempts.payment_id → payments.id` | intentos de un pago |
| `reservation_db` | `reservation_events.reservation_id → reservations.id` | historial de una reserva |

**Relaciones lógicas (11 referencias, sin FK).** Cruzan bases y se sostienen
por la aplicación:

| Origen | Destino |
|---|---|
| `reservations.customer_id` | `customers.id` |
| `reservations.hotel_id` | `hotels.id` |
| `reservations.room_id` | `rooms.id` |
| `reservations.payment_id` | `payments.id` |
| `inventory.room_id` | `rooms.id` |
| `inventory.hotel_id` | `hotels.id` |
| `holds.room_id` | `rooms.id` |
| `payments.reservation_id` | `reservations.id` |
| `notifications.reservation_id` | `reservations.id` |
| `notifications.customer_id` | `customers.id` |
| `notifications.event_id` | `outbox.id` |

El diagrama global está en `diagrams/logical-global.md` y las 11
comprobaciones en `integrity.md`.

### ¿Por qué no hay FK entre bases?

Porque una FK entre bases obligaría a que el motor de una base conozca y
bloquee filas de otra, acoplando el despliegue y rompiendo la propiedad
exclusiva por servicio. En su lugar:

1. la **saga orquestada** y la máquina de estados de `reservations` mantienen
   la coherencia (ADR-0003);
2. el **outbox transaccional** + relay desacopla las notificaciones (ADR-0004);
3. la **idempotencia** (`idempotency_key`, `reservation_id UNIQUE`,
   `event_id UNIQUE`) evita duplicados ante reintentos;
4. la integridad lógica se comprueba por software (`generate.py` →
   `integrity.md`), no por el motor.

## 5. Seguridad y datos sensibles

- `customers.password_hash` guarda el hash **scrypt** (parámetros
  `SCRYPT_N/R/P` en `compose.yaml`); nunca la contraseña.
- `sessions.token_hash` guarda el hash del token de sesión, no el token; la
  sesión expira (`expires_at`, TTL 8 h) y hay bloqueo tras 5 fallos durante
  300 s (`failed_attempts`, `locked_until`).
- `reservations.payment_token` es el token de pago del cliente: **no** debe
  aparecer en capturas.
- `sim_provider_charges.provider_ref` pertenece al proveedor simulado y
  tampoco se muestra.
- Los roles tienen `statement_timeout` (5 s), `lock_timeout` (2 s) e
  `idle_in_transaction_session_timeout` (10 s) definidos en `init-db.sh`, lo
  que limita el impacto de una conexión lenta.
- Los artefactos de esta carpeta no contienen contraseñas, hashes ni tokens;
  `queries.sql` enmascara el email y excluye esas columnas.

## 6. Integridad observada

- **Física**: 0 huérfanos en las 5 FK (verificado con anti-join).
- **Lógica**: se detectaron **huérfanos de pruebas E2E**, no violaciones del
  esquema: 2 filas de `inventory` y 2 `holds` con `room_id` inexistente en
  `hotel_db`, y 1 notificación con `reservation_id`/`event_id`/
  `customer_id` inexistentes. Son residuo de pruebas que simulan servicios
  externos sin pasar por el dueño de la base. Se limpian con un entorno
  nuevo (`make clean && … && make seed`), no con escrituras manuales.
- **Reglas de negocio**: 0 reservas con `nights` inconsistente, 0 pagos
  `SUCCEEDED` sin asiento `CHARGE`, 0 notificaciones `SENT` sin `sent_at`,
  0 reservas sin evento inicial.

Este hallazgo es didáctico: demuestra que **el motor no puede sustituir a la
saga**. La integridad entre servicios es una responsabilidad de la aplicación
y debe verificarse con consultas explícitas.

## 7. Conclusión

El esquema refleja las decisiones de arquitectura: bases separadas por
servicio con roles aislados, UUIDs para desacoplar, `CHECK` para invariantes
de negocio, índices parciales para workers, outbox y claves de idempotencia
para tolerar reintentos, y cero FK entre bases para preservar la autonomía de
los microservicios. La separación física (una instancia, seis bases) reduce el
costo operativo; la separación lógica (seis dueños, sin acceso cruzado) es la
que sostiene el diseño. Las relaciones entre servicios existen, pero son
**lógicas y verificables**, no constraints del motor.
