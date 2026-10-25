"""autenticacion

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column(
        "customers",
        sa.Column("failed_attempts", sa.Integer(), nullable=False,
                  server_default="0"),
    )
    op.add_column(
        "customers",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("sessions_customer_id_idx", "sessions", ["customer_id"])
    op.create_index("sessions_expires_at_idx", "sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("sessions_expires_at_idx", table_name="sessions")
    op.drop_index("sessions_customer_id_idx", table_name="sessions")
    op.drop_table("sessions")
    op.drop_column("customers", "last_login_at")
    op.drop_column("customers", "locked_until")
    op.drop_column("customers", "failed_attempts")
    op.drop_column("customers", "password_hash")
