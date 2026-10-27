# Diagrama ER — `reservation_db`

Fuente Mermaid generada desde el catálogo real. GitHub la renderiza;
para exportar PNG/SVG, pega el bloque en <https://mermaid.live>.
Se omiten `alembic_version` (infraestructura) y los datos. Dueño: `reservation`.

```mermaid
erDiagram
    OUTBOX {
        uuid id PK
        uuid aggregate_id
        text type
        jsonb payload
        text status
        int attempts
        timestamptz next_attempt_at
        timestamptz created_at
        timestamptz sent_at
    }
    RESERVATION_EVENTS {
        bigint id PK
        uuid reservation_id FK
        text from_status
        text to_status
        text reason
        timestamptz created_at
    }
    RESERVATIONS {
        uuid id PK
        text idempotency_key UK
        text request_hash
        uuid customer_id
        uuid hotel_id
        uuid room_id
        date check_in
        date check_out
        int nights
        int amount_cents
        text currency
        text payment_method
        text payment_token
        text payment_simulate
        uuid payment_id
        text payment_status
        text status
        text status_reason
        int attempts
        timestamptz next_attempt_at
        timestamptz phase_started_at
        timestamptz locked_until
        int version
        timestamptz created_at
        timestamptz updated_at
    }
    RESERVATIONS ||--o{ RESERVATION_EVENTS : "reservation_events_reservation_id_fkey"
```

## Restricciones CHECK y UNIQUE compuestas

Se validan en la base y no se dibujan como aristas:

- `outbox.outbox_status_check`: `CHECK ((status = ANY (ARRAY['PENDING'::text, 'SENT'::text])))`
- `reservations.reservations_amount_cents_check`: `CHECK ((amount_cents > 0))`
- `reservations.reservations_check`: `CHECK ((check_out > check_in))`
- `reservations.reservations_idempotency_key_key`: `UNIQUE (idempotency_key)`
- `reservations.reservations_nights_check`: `CHECK ((nights > 0))`
- `reservations.reservations_payment_simulate_check`: `CHECK ((payment_simulate = ANY (ARRAY['ok'::text, 'decline'::text, 'error_before_processing'::text, 'process_then_drop_response'::text, 'slow'::text])))`
- `reservations.reservations_status_check`: `CHECK ((status = ANY (ARRAY['RECEIVED'::text, 'HELD'::text, 'PAYMENT_PENDING'::text, 'PAYMENT_UNKNOWN'::text, 'PAID'::text, 'CONFIRMED'::text, 'PAYMENT_DECLINED'::text, 'REFUND_REQUIRED'::text, 'CANCELLING'::text, 'CANCELLED'::text, 'REJECTED_NO_INVENTORY'::text, 'FAILED_TECHNICAL'::text, 'MANUAL_REVIEW'::text])))`
