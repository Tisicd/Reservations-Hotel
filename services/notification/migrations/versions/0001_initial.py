"""esquema inicial: inbox de notificaciones

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
        CREATE TABLE notifications (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL UNIQUE,
            type text NOT NULL CHECK (type IN (
                'reservation.confirmed','reservation.cancelled'
            )),
            reservation_id uuid NOT NULL,
            customer_id uuid NOT NULL,
            payload jsonb NOT NULL DEFAULT '{}'::jsonb,
            status text NOT NULL DEFAULT 'PENDING' CHECK (status IN (
                'PENDING','SENT','FAILED'
            )),
            attempts integer NOT NULL DEFAULT 0,
            next_attempt_at timestamptz NOT NULL DEFAULT now(),
            last_error text,
            created_at timestamptz NOT NULL DEFAULT now(),
            sent_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_notifications_pending ON notifications (next_attempt_at) "
        "WHERE status = 'PENDING'"
    )
    op.execute(
        "CREATE INDEX idx_notifications_reservation ON notifications (reservation_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notifications")
