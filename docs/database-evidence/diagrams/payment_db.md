# Diagrama ER — `payment_db`

Fuente Mermaid generada desde el catálogo real. GitHub la renderiza;
para exportar PNG/SVG, pega el bloque en <https://mermaid.live>.
Se omiten `alembic_version` (infraestructura) y los datos. Dueño: `payment`.

```mermaid
erDiagram
    LEDGER {
        uuid id PK
        uuid payment_id FK
        text kind
        int amount_cents
        text currency
        timestamptz created_at
    }
    PAYMENT_ATTEMPTS {
        uuid id PK
        uuid payment_id FK
        int attempt_no
        text simulate
        text outcome
        text error
        timestamptz started_at
        timestamptz finished_at
    }
    PAYMENTS {
        uuid id PK
        uuid reservation_id UK
        text idempotency_key UK
        text request_hash
        int amount_cents
        text currency
        text method
        text status
        text provider_ref
        timestamptz created_at
        timestamptz updated_at
    }
    SIM_PROVIDER_CHARGES {
        text idempotency_key PK
        text provider_ref
        text status
        int amount_cents
        text currency
        timestamptz created_at
        timestamptz refunded_at
    }
    PAYMENTS ||--o{ LEDGER : "ledger_payment_id_fkey"
    PAYMENTS ||--o{ PAYMENT_ATTEMPTS : "payment_attempts_payment_id_fkey"
```

## Restricciones CHECK y UNIQUE compuestas

Se validan en la base y no se dibujan como aristas:

- `ledger.ledger_kind_check`: `CHECK ((kind = ANY (ARRAY['CHARGE'::text, 'REFUND'::text])))`
- `ledger.ledger_payment_id_kind_key`: `UNIQUE (payment_id, kind)`
- `payment_attempts.payment_attempts_payment_id_attempt_no_key`: `UNIQUE (payment_id, attempt_no)`
- `payments.payments_amount_cents_check`: `CHECK ((amount_cents > 0))`
- `payments.payments_idempotency_key_key`: `UNIQUE (idempotency_key)`
- `payments.payments_reservation_id_key`: `UNIQUE (reservation_id)`
- `payments.payments_status_check`: `CHECK ((status = ANY (ARRAY['INITIATED'::text, 'SUCCEEDED'::text, 'DECLINED'::text, 'FAILED_TECHNICAL'::text, 'UNKNOWN'::text, 'REFUNDED'::text])))`
- `sim_provider_charges.sim_provider_charges_status_check`: `CHECK ((status = ANY (ARRAY['APPROVED'::text, 'DECLINED'::text])))`
