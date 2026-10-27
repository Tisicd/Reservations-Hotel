# Inventario real de las bases de datos

Generado por `generate.py` el 2026-10-26 04:48 UTC contra PostgreSQL 16 en el perfil dev.
Solo lectura: `information_schema`, `pg_catalog` y `count(*)`. Sin credenciales.

> `alembic_version` existe en las 6 bases (control de migraciones); se omite
> del inventario detallado y de los diagramas para no ensuciarlos.

## Resumen

| Base | Rol dueño | Tamaño | Tablas | Filas | Revisión Alembic |
|---|---|---|---:|---:|---|
| `customer_db` | `customer` | 7767 kB | 2 | 17 | `0002` |
| `hotel_db` | `hotel` | 7671 kB | 2 | 20 | `0001` |
| `availability_db` | `availability` | 7983 kB | 2 | 972 | `0001` |
| `payment_db` | `payment` | 8039 kB | 4 | 163 | `0001` |
| `reservation_db` | `reservation` | 8383 kB | 3 | 465 | `0001` |
| `notification_db` | `notification` | 7791 kB | 1 | 29 | `0001` |

Filas = suma de tablas de dominio (excluye `alembic_version`).

## `customer_db`

Dueño: `customer` · Tamaño: 7767 kB · Revisión Alembic: `0002`

### Tablas

| Tabla | Filas |
|---|---:|
| `customers` | 16 |
| `sessions` | 1 |

### Columnas

| Tabla | # | Columna | Tipo | Nulo | Default | Sensible |
|---|---:|---|---|---|---|---|
| `customers` | 1 | `id` | uuid | no | - | - |
| `customers` | 2 | `name` | character varying | no | - | - |
| `customers` | 3 | `email` | character varying | no | - | PII |
| `customers` | 4 | `created_at` | timestamp with time zone | no | now() | - |
| `customers` | 5 | `password_hash` | text | sí | - | secreto |
| `customers` | 6 | `failed_attempts` | integer | no | 0 | - |
| `customers` | 7 | `locked_until` | timestamp with time zone | sí | - | - |
| `customers` | 8 | `last_login_at` | timestamp with time zone | sí | - | - |
| `sessions` | 1 | `token_hash` | character varying | no | - | secreto |
| `sessions` | 2 | `customer_id` | uuid | no | - | - |
| `sessions` | 3 | `created_at` | timestamp with time zone | no | now() | - |
| `sessions` | 4 | `expires_at` | timestamp with time zone | no | - | - |

### Claves y restricciones

| Tabla | Nombre | Tipo | Columnas | Referencia | Definición |
|---|---|---|---|---|---|
| `customers` | `customers_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `sessions` | `sessions_customer_id_fkey` | FK | `customer_id` | `customers(id)` | `FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE` |
| `sessions` | `sessions_pkey` | PK | `token_hash` | - | `PRIMARY KEY (token_hash)` |

### Índices

| Tabla | Índice | Definición |
|---|---|---|
| `customers` | `customers_email_lower_key` | `CREATE UNIQUE INDEX customers_email_lower_key ON public.customers USING btree (lower((email)::text))` |
| `customers` | `customers_pkey` | `CREATE UNIQUE INDEX customers_pkey ON public.customers USING btree (id)` |
| `sessions` | `sessions_customer_id_idx` | `CREATE INDEX sessions_customer_id_idx ON public.sessions USING btree (customer_id)` |
| `sessions` | `sessions_expires_at_idx` | `CREATE INDEX sessions_expires_at_idx ON public.sessions USING btree (expires_at)` |
| `sessions` | `sessions_pkey` | `CREATE UNIQUE INDEX sessions_pkey ON public.sessions USING btree (token_hash)` |

### Secuencias

Sin secuencias propias: las PK son UUID generados por la aplicación.

## `hotel_db`

Dueño: `hotel` · Tamaño: 7671 kB · Revisión Alembic: `0001`

### Tablas

| Tabla | Filas |
|---|---:|
| `hotels` | 4 |
| `rooms` | 16 |

### Columnas

| Tabla | # | Columna | Tipo | Nulo | Default | Sensible |
|---|---:|---|---|---|---|---|
| `hotels` | 1 | `id` | uuid | no | - | - |
| `hotels` | 2 | `name` | character varying | no | - | - |
| `hotels` | 3 | `city` | character varying | no | - | - |
| `hotels` | 4 | `created_at` | timestamp with time zone | no | now() | - |
| `rooms` | 1 | `id` | uuid | no | - | - |
| `rooms` | 2 | `hotel_id` | uuid | no | - | - |
| `rooms` | 3 | `name` | character varying | no | - | - |
| `rooms` | 4 | `capacity` | integer | no | - | - |
| `rooms` | 5 | `price_per_night_cents` | integer | no | - | - |
| `rooms` | 6 | `currency` | character varying | no | - | - |
| `rooms` | 7 | `created_at` | timestamp with time zone | no | now() | - |

### Claves y restricciones

| Tabla | Nombre | Tipo | Columnas | Referencia | Definición |
|---|---|---|---|---|---|
| `hotels` | `hotels_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `rooms` | `rooms_capacity_check` | CHECK | `capacity` | - | `CHECK (((capacity >= 1) AND (capacity <= 10)))` |
| `rooms` | `rooms_currency_check` | CHECK | `currency` | - | `CHECK (((currency)::text = 'USD'::text))` |
| `rooms` | `rooms_hotel_id_fkey` | FK | `hotel_id` | `hotels(id)` | `FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE RESTRICT` |
| `rooms` | `rooms_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `rooms` | `rooms_price_check` | CHECK | `price_per_night_cents` | - | `CHECK ((price_per_night_cents > 0))` |

### Índices

| Tabla | Índice | Definición |
|---|---|---|
| `hotels` | `hotels_pkey` | `CREATE UNIQUE INDEX hotels_pkey ON public.hotels USING btree (id)` |
| `rooms` | `rooms_hotel_id_idx` | `CREATE INDEX rooms_hotel_id_idx ON public.rooms USING btree (hotel_id)` |
| `rooms` | `rooms_pkey` | `CREATE UNIQUE INDEX rooms_pkey ON public.rooms USING btree (id)` |

### Secuencias

Sin secuencias propias: las PK son UUID generados por la aplicación.

## `availability_db`

Dueño: `availability` · Tamaño: 7983 kB · Revisión Alembic: `0001`

### Tablas

| Tabla | Filas |
|---|---:|
| `holds` | 29 |
| `inventory` | 943 |

### Columnas

| Tabla | # | Columna | Tipo | Nulo | Default | Sensible |
|---|---:|---|---|---|---|---|
| `holds` | 1 | `hold_id` | uuid | no | - | - |
| `holds` | 2 | `room_id` | uuid | no | - | - |
| `holds` | 3 | `check_in` | date | no | - | - |
| `holds` | 4 | `check_out` | date | no | - | - |
| `holds` | 5 | `units` | integer | no | - | - |
| `holds` | 6 | `status` | text | no | - | - |
| `holds` | 7 | `expires_at` | timestamp with time zone | no | - | - |
| `holds` | 8 | `created_at` | timestamp with time zone | no | now() | - |
| `holds` | 9 | `updated_at` | timestamp with time zone | no | now() | - |
| `inventory` | 1 | `room_id` | uuid | no | - | - |
| `inventory` | 2 | `hotel_id` | uuid | no | - | - |
| `inventory` | 3 | `night` | date | no | - | - |
| `inventory` | 4 | `total` | integer | no | - | - |
| `inventory` | 5 | `held` | integer | no | 0 | - |
| `inventory` | 6 | `confirmed` | integer | no | 0 | - |

### Claves y restricciones

| Tabla | Nombre | Tipo | Columnas | Referencia | Definición |
|---|---|---|---|---|---|
| `holds` | `holds_check` | CHECK | `check_out,check_in` | - | `CHECK ((check_out > check_in))` |
| `holds` | `holds_pkey` | PK | `hold_id` | - | `PRIMARY KEY (hold_id)` |
| `holds` | `holds_status_check` | CHECK | `status` | - | `CHECK ((status = ANY (ARRAY['HELD'::text, 'CONFIRMED'::text, 'RELEASED'::text, 'EXPIRED'::text])))` |
| `holds` | `holds_units_check` | CHECK | `units` | - | `CHECK ((units > 0))` |
| `inventory` | `inventory_check` | CHECK | `held,confirmed,total` | - | `CHECK (((held + confirmed) <= total))` |
| `inventory` | `inventory_confirmed_check` | CHECK | `confirmed` | - | `CHECK ((confirmed >= 0))` |
| `inventory` | `inventory_held_check` | CHECK | `held` | - | `CHECK ((held >= 0))` |
| `inventory` | `inventory_pkey` | PK | `room_id,night` | - | `PRIMARY KEY (room_id, night)` |
| `inventory` | `inventory_total_check` | CHECK | `total` | - | `CHECK ((total >= 0))` |

### Índices

| Tabla | Índice | Definición |
|---|---|---|
| `holds` | `holds_pkey` | `CREATE UNIQUE INDEX holds_pkey ON public.holds USING btree (hold_id)` |
| `holds` | `idx_holds_expires_held` | `CREATE INDEX idx_holds_expires_held ON public.holds USING btree (expires_at) WHERE (status = 'HELD'::text)` |
| `inventory` | `idx_inventory_hotel_night` | `CREATE INDEX idx_inventory_hotel_night ON public.inventory USING btree (hotel_id, night)` |
| `inventory` | `inventory_pkey` | `CREATE UNIQUE INDEX inventory_pkey ON public.inventory USING btree (room_id, night)` |

### Secuencias

Sin secuencias propias: las PK son UUID generados por la aplicación.

## `payment_db`

Dueño: `payment` · Tamaño: 8039 kB · Revisión Alembic: `0001`

### Tablas

| Tabla | Filas |
|---|---:|
| `ledger` | 28 |
| `payment_attempts` | 27 |
| `payments` | 27 |
| `sim_provider_charges` | 81 |

### Columnas

| Tabla | # | Columna | Tipo | Nulo | Default | Sensible |
|---|---:|---|---|---|---|---|
| `ledger` | 1 | `id` | uuid | no | - | - |
| `ledger` | 2 | `payment_id` | uuid | no | - | - |
| `ledger` | 3 | `kind` | text | no | - | - |
| `ledger` | 4 | `amount_cents` | integer | no | - | - |
| `ledger` | 5 | `currency` | text | no | - | - |
| `ledger` | 6 | `created_at` | timestamp with time zone | no | now() | - |
| `payment_attempts` | 1 | `id` | uuid | no | - | - |
| `payment_attempts` | 2 | `payment_id` | uuid | no | - | - |
| `payment_attempts` | 3 | `attempt_no` | integer | no | - | - |
| `payment_attempts` | 4 | `simulate` | text | sí | - | - |
| `payment_attempts` | 5 | `outcome` | text | sí | - | - |
| `payment_attempts` | 6 | `error` | text | sí | - | - |
| `payment_attempts` | 7 | `started_at` | timestamp with time zone | no | now() | - |
| `payment_attempts` | 8 | `finished_at` | timestamp with time zone | sí | - | - |
| `payments` | 1 | `id` | uuid | no | - | - |
| `payments` | 2 | `reservation_id` | uuid | no | - | - |
| `payments` | 3 | `idempotency_key` | text | no | - | - |
| `payments` | 4 | `request_hash` | text | no | - | - |
| `payments` | 5 | `amount_cents` | integer | no | - | - |
| `payments` | 6 | `currency` | text | no | - | - |
| `payments` | 7 | `method` | text | no | - | - |
| `payments` | 8 | `status` | text | no | - | - |
| `payments` | 9 | `provider_ref` | text | sí | - | - |
| `payments` | 10 | `created_at` | timestamp with time zone | no | now() | - |
| `payments` | 11 | `updated_at` | timestamp with time zone | no | now() | - |
| `sim_provider_charges` | 1 | `idempotency_key` | text | no | - | - |
| `sim_provider_charges` | 2 | `provider_ref` | text | no | - | - |
| `sim_provider_charges` | 3 | `status` | text | no | - | - |
| `sim_provider_charges` | 4 | `amount_cents` | integer | no | - | - |
| `sim_provider_charges` | 5 | `currency` | text | no | - | - |
| `sim_provider_charges` | 6 | `created_at` | timestamp with time zone | no | now() | - |
| `sim_provider_charges` | 7 | `refunded_at` | timestamp with time zone | sí | - | - |

### Claves y restricciones

| Tabla | Nombre | Tipo | Columnas | Referencia | Definición |
|---|---|---|---|---|---|
| `ledger` | `ledger_kind_check` | CHECK | `kind` | - | `CHECK ((kind = ANY (ARRAY['CHARGE'::text, 'REFUND'::text])))` |
| `ledger` | `ledger_payment_id_fkey` | FK | `payment_id` | `payments(id)` | `FOREIGN KEY (payment_id) REFERENCES payments(id)` |
| `ledger` | `ledger_payment_id_kind_key` | UNIQUE | `payment_id,kind` | - | `UNIQUE (payment_id, kind)` |
| `ledger` | `ledger_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `payment_attempts` | `payment_attempts_payment_id_attempt_no_key` | UNIQUE | `payment_id,attempt_no` | - | `UNIQUE (payment_id, attempt_no)` |
| `payment_attempts` | `payment_attempts_payment_id_fkey` | FK | `payment_id` | `payments(id)` | `FOREIGN KEY (payment_id) REFERENCES payments(id)` |
| `payment_attempts` | `payment_attempts_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `payments` | `payments_amount_cents_check` | CHECK | `amount_cents` | - | `CHECK ((amount_cents > 0))` |
| `payments` | `payments_idempotency_key_key` | UNIQUE | `idempotency_key` | - | `UNIQUE (idempotency_key)` |
| `payments` | `payments_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `payments` | `payments_reservation_id_key` | UNIQUE | `reservation_id` | - | `UNIQUE (reservation_id)` |
| `payments` | `payments_status_check` | CHECK | `status` | - | `CHECK ((status = ANY (ARRAY['INITIATED'::text, 'SUCCEEDED'::text, 'DECLINED'::text, 'FAILED_TECHNICAL'::text, 'UNKNOWN'::text, 'REFUNDED'::text])))` |
| `sim_provider_charges` | `sim_provider_charges_pkey` | PK | `idempotency_key` | - | `PRIMARY KEY (idempotency_key)` |
| `sim_provider_charges` | `sim_provider_charges_status_check` | CHECK | `status` | - | `CHECK ((status = ANY (ARRAY['APPROVED'::text, 'DECLINED'::text])))` |

### Índices

| Tabla | Índice | Definición |
|---|---|---|
| `ledger` | `ledger_payment_id_kind_key` | `CREATE UNIQUE INDEX ledger_payment_id_kind_key ON public.ledger USING btree (payment_id, kind)` |
| `ledger` | `ledger_pkey` | `CREATE UNIQUE INDEX ledger_pkey ON public.ledger USING btree (id)` |
| `payment_attempts` | `payment_attempts_payment_id_attempt_no_key` | `CREATE UNIQUE INDEX payment_attempts_payment_id_attempt_no_key ON public.payment_attempts USING btree (payment_id, attempt_no)` |
| `payment_attempts` | `payment_attempts_pkey` | `CREATE UNIQUE INDEX payment_attempts_pkey ON public.payment_attempts USING btree (id)` |
| `payments` | `idx_payments_unknown` | `CREATE INDEX idx_payments_unknown ON public.payments USING btree (updated_at) WHERE (status = 'UNKNOWN'::text)` |
| `payments` | `payments_idempotency_key_key` | `CREATE UNIQUE INDEX payments_idempotency_key_key ON public.payments USING btree (idempotency_key)` |
| `payments` | `payments_pkey` | `CREATE UNIQUE INDEX payments_pkey ON public.payments USING btree (id)` |
| `payments` | `payments_reservation_id_key` | `CREATE UNIQUE INDEX payments_reservation_id_key ON public.payments USING btree (reservation_id)` |
| `sim_provider_charges` | `sim_provider_charges_pkey` | `CREATE UNIQUE INDEX sim_provider_charges_pkey ON public.sim_provider_charges USING btree (idempotency_key)` |

### Secuencias

Sin secuencias propias: las PK son UUID generados por la aplicación.

## `reservation_db`

Dueño: `reservation` · Tamaño: 8383 kB · Revisión Alembic: `0001`

### Tablas

| Tabla | Filas |
|---|---:|
| `outbox` | 28 |
| `reservation_events` | 320 |
| `reservations` | 117 |

### Columnas

| Tabla | # | Columna | Tipo | Nulo | Default | Sensible |
|---|---:|---|---|---|---|---|
| `outbox` | 1 | `id` | uuid | no | - | - |
| `outbox` | 2 | `aggregate_id` | uuid | no | - | - |
| `outbox` | 3 | `type` | text | no | - | - |
| `outbox` | 4 | `payload` | jsonb | no | - | - |
| `outbox` | 5 | `status` | text | no | 'PENDING'::text | - |
| `outbox` | 6 | `attempts` | integer | no | 0 | - |
| `outbox` | 7 | `next_attempt_at` | timestamp with time zone | no | now() | - |
| `outbox` | 8 | `created_at` | timestamp with time zone | no | now() | - |
| `outbox` | 9 | `sent_at` | timestamp with time zone | sí | - | - |
| `reservation_events` | 1 | `id` | bigint | no | nextval('reservation_events_id_seq'::regclass) | - |
| `reservation_events` | 2 | `reservation_id` | uuid | no | - | - |
| `reservation_events` | 3 | `from_status` | text | sí | - | - |
| `reservation_events` | 4 | `to_status` | text | no | - | - |
| `reservation_events` | 5 | `reason` | text | sí | - | - |
| `reservation_events` | 6 | `created_at` | timestamp with time zone | no | now() | - |
| `reservations` | 1 | `id` | uuid | no | - | - |
| `reservations` | 2 | `idempotency_key` | text | no | - | - |
| `reservations` | 3 | `request_hash` | text | no | - | - |
| `reservations` | 4 | `customer_id` | uuid | no | - | - |
| `reservations` | 5 | `hotel_id` | uuid | no | - | - |
| `reservations` | 6 | `room_id` | uuid | no | - | - |
| `reservations` | 7 | `check_in` | date | no | - | - |
| `reservations` | 8 | `check_out` | date | no | - | - |
| `reservations` | 9 | `nights` | integer | no | - | - |
| `reservations` | 10 | `amount_cents` | integer | no | - | - |
| `reservations` | 11 | `currency` | text | no | - | - |
| `reservations` | 12 | `payment_method` | text | no | - | - |
| `reservations` | 13 | `payment_token` | text | no | - | token |
| `reservations` | 14 | `payment_simulate` | text | no | - | - |
| `reservations` | 15 | `payment_id` | uuid | sí | - | - |
| `reservations` | 16 | `payment_status` | text | sí | - | - |
| `reservations` | 17 | `status` | text | no | - | - |
| `reservations` | 18 | `status_reason` | text | sí | - | - |
| `reservations` | 19 | `attempts` | integer | no | 0 | - |
| `reservations` | 20 | `next_attempt_at` | timestamp with time zone | sí | - | - |
| `reservations` | 21 | `phase_started_at` | timestamp with time zone | no | - | - |
| `reservations` | 22 | `locked_until` | timestamp with time zone | sí | - | - |
| `reservations` | 23 | `version` | integer | no | 0 | - |
| `reservations` | 24 | `created_at` | timestamp with time zone | no | now() | - |
| `reservations` | 25 | `updated_at` | timestamp with time zone | no | now() | - |

### Claves y restricciones

| Tabla | Nombre | Tipo | Columnas | Referencia | Definición |
|---|---|---|---|---|---|
| `outbox` | `outbox_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `outbox` | `outbox_status_check` | CHECK | `status` | - | `CHECK ((status = ANY (ARRAY['PENDING'::text, 'SENT'::text])))` |
| `reservation_events` | `reservation_events_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `reservation_events` | `reservation_events_reservation_id_fkey` | FK | `reservation_id` | `reservations(id)` | `FOREIGN KEY (reservation_id) REFERENCES reservations(id)` |
| `reservations` | `reservations_amount_cents_check` | CHECK | `amount_cents` | - | `CHECK ((amount_cents > 0))` |
| `reservations` | `reservations_check` | CHECK | `check_out,check_in` | - | `CHECK ((check_out > check_in))` |
| `reservations` | `reservations_idempotency_key_key` | UNIQUE | `idempotency_key` | - | `UNIQUE (idempotency_key)` |
| `reservations` | `reservations_nights_check` | CHECK | `nights` | - | `CHECK ((nights > 0))` |
| `reservations` | `reservations_payment_simulate_check` | CHECK | `payment_simulate` | - | `CHECK ((payment_simulate = ANY (ARRAY['ok'::text, 'decline'::text, 'error_before_processing'::text, 'process_then_drop_response'::text, 'slow'::text])))` |
| `reservations` | `reservations_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `reservations` | `reservations_status_check` | CHECK | `status` | - | `CHECK ((status = ANY (ARRAY['RECEIVED'::text, 'HELD'::text, 'PAYMENT_PENDING'::text, 'PAYMENT_UNKNOWN'::text, 'PAID'::text, 'CONFIRMED'::text, 'PAYMENT_DECLINED'::text, 'REFUND_REQUIRED'::text, 'CANCELLING'::text, 'CANCELLED'::text, 'REJECTED_NO_INVENTORY'::text, 'FAILED_TECHNICAL'::text, 'MANUAL_REVIEW'::text])))` |

### Índices

| Tabla | Índice | Definición |
|---|---|---|
| `outbox` | `idx_outbox_pending` | `CREATE INDEX idx_outbox_pending ON public.outbox USING btree (next_attempt_at) WHERE (status = 'PENDING'::text)` |
| `outbox` | `outbox_pkey` | `CREATE UNIQUE INDEX outbox_pkey ON public.outbox USING btree (id)` |
| `reservation_events` | `idx_reservation_events_reservation` | `CREATE INDEX idx_reservation_events_reservation ON public.reservation_events USING btree (reservation_id, id)` |
| `reservation_events` | `reservation_events_pkey` | `CREATE UNIQUE INDEX reservation_events_pkey ON public.reservation_events USING btree (id)` |
| `reservations` | `idx_reservations_customer` | `CREATE INDEX idx_reservations_customer ON public.reservations USING btree (customer_id, created_at DESC)` |
| `reservations` | `idx_reservations_due` | `CREATE INDEX idx_reservations_due ON public.reservations USING btree (next_attempt_at) WHERE (status <> ALL (ARRAY['CONFIRMED'::text, 'REJECTED_NO_INVENTORY'::text, 'FAILED_TECHNICAL'::text, 'CANCELLED'::text, 'MANUAL_REVIEW'::text]))` |
| `reservations` | `reservations_idempotency_key_key` | `CREATE UNIQUE INDEX reservations_idempotency_key_key ON public.reservations USING btree (idempotency_key)` |
| `reservations` | `reservations_pkey` | `CREATE UNIQUE INDEX reservations_pkey ON public.reservations USING btree (id)` |

### Secuencias

| Secuencia | Tipo |
|---|---|
| `reservation_events_id_seq` | bigint |

## `notification_db`

Dueño: `notification` · Tamaño: 7791 kB · Revisión Alembic: `0001`

### Tablas

| Tabla | Filas |
|---|---:|
| `notifications` | 29 |

### Columnas

| Tabla | # | Columna | Tipo | Nulo | Default | Sensible |
|---|---:|---|---|---|---|---|
| `notifications` | 1 | `id` | uuid | no | - | - |
| `notifications` | 2 | `event_id` | uuid | no | - | - |
| `notifications` | 3 | `type` | text | no | - | - |
| `notifications` | 4 | `reservation_id` | uuid | no | - | - |
| `notifications` | 5 | `customer_id` | uuid | no | - | - |
| `notifications` | 6 | `payload` | jsonb | no | '{}'::jsonb | - |
| `notifications` | 7 | `status` | text | no | 'PENDING'::text | - |
| `notifications` | 8 | `attempts` | integer | no | 0 | - |
| `notifications` | 9 | `next_attempt_at` | timestamp with time zone | no | now() | - |
| `notifications` | 10 | `last_error` | text | sí | - | - |
| `notifications` | 11 | `created_at` | timestamp with time zone | no | now() | - |
| `notifications` | 12 | `sent_at` | timestamp with time zone | sí | - | - |

### Claves y restricciones

| Tabla | Nombre | Tipo | Columnas | Referencia | Definición |
|---|---|---|---|---|---|
| `notifications` | `notifications_event_id_key` | UNIQUE | `event_id` | - | `UNIQUE (event_id)` |
| `notifications` | `notifications_pkey` | PK | `id` | - | `PRIMARY KEY (id)` |
| `notifications` | `notifications_status_check` | CHECK | `status` | - | `CHECK ((status = ANY (ARRAY['PENDING'::text, 'SENT'::text, 'FAILED'::text])))` |
| `notifications` | `notifications_type_check` | CHECK | `type` | - | `CHECK ((type = ANY (ARRAY['reservation.confirmed'::text, 'reservation.cancelled'::text])))` |

### Índices

| Tabla | Índice | Definición |
|---|---|---|
| `notifications` | `idx_notifications_pending` | `CREATE INDEX idx_notifications_pending ON public.notifications USING btree (next_attempt_at) WHERE (status = 'PENDING'::text)` |
| `notifications` | `idx_notifications_reservation` | `CREATE INDEX idx_notifications_reservation ON public.notifications USING btree (reservation_id)` |
| `notifications` | `notifications_event_id_key` | `CREATE UNIQUE INDEX notifications_event_id_key ON public.notifications USING btree (event_id)` |
| `notifications` | `notifications_pkey` | `CREATE UNIQUE INDEX notifications_pkey ON public.notifications USING btree (id)` |

### Secuencias

Sin secuencias propias: las PK son UUID generados por la aplicación.
