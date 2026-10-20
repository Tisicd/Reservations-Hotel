"""esquema inicial: reservas, eventos append-only y outbox

Revision ID: 0001
Revises:
Create Date: 2026-10-20

"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATES = (
    "'RECEIVED','HELD','PAYMENT_PENDING','PAYMENT_UNKNOWN','PAID','CONFIRMED',"
    "'PAYMENT_DECLINED','REFUND_REQUIRED','CANCELLING','CANCELLED',"
    "'REJECTED_NO_INVENTORY','FAILED_TECHNICAL','MANUAL_REVIEW'"
)
STABLE = (
    "'CONFIRMED','REJECTED_NO_INVENTORY','FAILED_TECHNICAL','CANCELLED','MANUAL_REVIEW'"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE reservations (
            id uuid PRIMARY KEY,
            idempotency_key text NOT NULL UNIQUE,
            request_hash text NOT NULL,
            customer_id uuid NOT NULL,
            hotel_id uuid NOT NULL,
            room_id uuid NOT NULL,
            check_in date NOT NULL,
            check_out date NOT NULL,
            nights integer NOT NULL CHECK (nights > 0),
            amount_cents integer NOT NULL CHECK (amount_cents > 0),
            currency text NOT NULL,
            payment_method text NOT NULL,
            payment_token text NOT NULL,
            payment_simulate text NOT NULL CHECK (payment_simulate IN (
                'ok','decline','error_before_processing','process_then_drop_response','slow'
            )),
            payment_id uuid,
            payment_status text,
            status text NOT NULL CHECK (status IN ({STATES})),
            status_reason text,
            attempts integer NOT NULL DEFAULT 0,
            next_attempt_at timestamptz,
            phase_started_at timestamptz NOT NULL,
            locked_until timestamptz,
            version integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (check_out > check_in)
        )
        """
    )
    op.execute(
        f"""
        CREATE INDEX idx_reservations_due ON reservations (next_attempt_at)
        WHERE status NOT IN ({STABLE})
        """
    )
    op.execute(
        "CREATE INDEX idx_reservations_customer ON reservations (customer_id, created_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE reservation_events (
            id bigserial PRIMARY KEY,
            reservation_id uuid NOT NULL REFERENCES reservations(id),
            from_status text,
            to_status text NOT NULL,
            reason text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_reservation_events_reservation
        ON reservation_events (reservation_id, id)
        """
    )
    op.execute(
        """
        CREATE FUNCTION reservation_events_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'reservation_events es append-only';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER reservation_events_no_update_delete
        BEFORE UPDATE OR DELETE ON reservation_events
        FOR EACH ROW EXECUTE FUNCTION reservation_events_append_only()
        """
    )
    op.execute(
        """
        CREATE TABLE outbox (
            id uuid PRIMARY KEY,
            aggregate_id uuid NOT NULL,
            type text NOT NULL,
            payload jsonb NOT NULL,
            status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','SENT')),
            attempts integer NOT NULL DEFAULT 0,
            next_attempt_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            sent_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_outbox_pending ON outbox (next_attempt_at) WHERE status = 'PENDING'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS outbox")
    op.execute("DROP TRIGGER IF EXISTS reservation_events_no_update_delete ON reservation_events")
    op.execute("DROP FUNCTION IF EXISTS reservation_events_append_only()")
    op.execute("DROP TABLE IF EXISTS reservation_events")
    op.execute("DROP TABLE IF EXISTS reservations")
