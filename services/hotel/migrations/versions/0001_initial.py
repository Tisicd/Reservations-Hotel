"""hoteles y habitaciones

Revision ID: 0001
Revises:
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hotels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "hotel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hotels.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("price_per_night_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("capacity BETWEEN 1 AND 10", name="rooms_capacity_check"),
        sa.CheckConstraint("price_per_night_cents > 0", name="rooms_price_check"),
        sa.CheckConstraint("currency = 'USD'", name="rooms_currency_check"),
    )
    op.create_index("rooms_hotel_id_idx", "rooms", ["hotel_id"])


def downgrade() -> None:
    op.drop_index("rooms_hotel_id_idx", table_name="rooms")
    op.drop_table("rooms")
    op.drop_table("hotels")
