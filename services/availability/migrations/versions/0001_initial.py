"""esquema inicial: inventory y holds

Revision ID: 0001
Revises:
Create Date: 2026-10-19

"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE inventory (
            room_id uuid NOT NULL,
            hotel_id uuid NOT NULL,
            night date NOT NULL,
            total integer NOT NULL CHECK (total >= 0),
            held integer NOT NULL DEFAULT 0 CHECK (held >= 0),
            confirmed integer NOT NULL DEFAULT 0 CHECK (confirmed >= 0),
            PRIMARY KEY (room_id, night),
            CHECK (held + confirmed <= total)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE holds (
            hold_id uuid PRIMARY KEY,
            room_id uuid NOT NULL,
            check_in date NOT NULL,
            check_out date NOT NULL,
            units integer NOT NULL CHECK (units > 0),
            status text NOT NULL CHECK (status IN ('HELD','CONFIRMED','RELEASED','EXPIRED')),
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (check_out > check_in)
        )
        """
    )
    op.execute("CREATE INDEX idx_inventory_hotel_night ON inventory (hotel_id, night)")
    op.execute("CREATE INDEX idx_holds_expires_held ON holds (expires_at) WHERE status = 'HELD'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS holds")
    op.execute("DROP TABLE IF EXISTS inventory")
