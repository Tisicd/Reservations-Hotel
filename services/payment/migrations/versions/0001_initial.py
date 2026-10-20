"""esquema inicial: pagos, intentos, ledger y proveedor simulado

Revision ID: 0001
Revises:
Create Date: 2026-10-20

"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE payments (
            id uuid PRIMARY KEY,
            reservation_id uuid NOT NULL UNIQUE,
            idempotency_key text NOT NULL UNIQUE,
            request_hash text NOT NULL,
            amount_cents integer NOT NULL CHECK (amount_cents > 0),
            currency text NOT NULL,
            method text NOT NULL,
            status text NOT NULL CHECK (status IN (
                'INITIATED','SUCCEEDED','DECLINED','FAILED_TECHNICAL','UNKNOWN','REFUNDED'
            )),
            provider_ref text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE payment_attempts (
            id uuid PRIMARY KEY,
            payment_id uuid NOT NULL REFERENCES payments(id),
            attempt_no integer NOT NULL,
            simulate text,
            outcome text,
            error text,
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            UNIQUE (payment_id, attempt_no)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE ledger (
            id uuid PRIMARY KEY,
            payment_id uuid NOT NULL REFERENCES payments(id),
            kind text NOT NULL CHECK (kind IN ('CHARGE','REFUND')),
            amount_cents integer NOT NULL,
            currency text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (payment_id, kind)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE sim_provider_charges (
            idempotency_key text PRIMARY KEY,
            provider_ref text NOT NULL,
            status text NOT NULL CHECK (status IN ('APPROVED','DECLINED')),
            amount_cents integer NOT NULL,
            currency text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            refunded_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_payments_unknown ON payments (updated_at) WHERE status = 'UNKNOWN'"
    )
    op.execute(
        """
        CREATE FUNCTION ledger_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'ledger es append-only';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER ledger_no_update_delete
        BEFORE UPDATE OR DELETE ON ledger
        FOR EACH ROW EXECUTE FUNCTION ledger_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ledger_no_update_delete ON ledger")
    op.execute("DROP FUNCTION IF EXISTS ledger_append_only()")
    op.execute("DROP TABLE IF EXISTS sim_provider_charges")
    op.execute("DROP TABLE IF EXISTS ledger")
    op.execute("DROP TABLE IF EXISTS payment_attempts")
    op.execute("DROP TABLE IF EXISTS payments")
