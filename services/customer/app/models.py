import datetime as dt

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .errors import DependencyUnavailable, EmailExists

metadata = sa.MetaData()

customers = sa.Table(
    "customers",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("email", sa.String(254), nullable=False),
    sa.Column("password_hash", sa.Text, nullable=True),
    sa.Column("failed_attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)

sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("token_hash", sa.String(64), primary_key=True),
    sa.Column(
        "customer_id",
        UUID(as_uuid=True),
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
sa.Index("sessions_customer_id_idx", sessions.c.customer_id)
sa.Index("sessions_expires_at_idx", sessions.c.expires_at)


class CustomerStore:
    def __init__(self, engine: sa.Engine):
        self.engine = engine

    def create(self, customer_id, name: str, email: str) -> dict:
        try:
            with self.engine.begin() as conn:
                row = conn.execute(
                    sa.insert(customers)
                    .values(id=customer_id, name=name, email=email)
                    .returning(
                        customers.c.id,
                        customers.c.name,
                        customers.c.email,
                        customers.c.created_at,
                    )
                ).one()
            return dict(row._mapping)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise EmailExists("email ya registrado") from exc
            raise DependencyUnavailable("base de datos no disponible") from exc
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def register(self, customer_id, name: str, email: str,
                 password_hash: str) -> dict:
        try:
            with self.engine.begin() as conn:
                row = conn.execute(
                    sa.insert(customers)
                    .values(id=customer_id, name=name, email=email,
                            password_hash=password_hash)
                    .returning(
                        customers.c.id,
                        customers.c.name,
                        customers.c.email,
                        customers.c.created_at,
                    )
                ).one()
            return dict(row._mapping)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise EmailExists("email ya registrado") from exc
            raise DependencyUnavailable("base de datos no disponible") from exc
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def get(self, customer_id) -> dict | None:
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    sa.select(
                        customers.c.id,
                        customers.c.name,
                        customers.c.email,
                        customers.c.created_at,
                    ).where(customers.c.id == customer_id)
                ).first()
            return dict(row._mapping) if row else None
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def get_by_email(self, email: str) -> dict | None:
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    sa.select(customers).where(
                        sa.func.lower(customers.c.email) == email.lower())
                ).first()
            return dict(row._mapping) if row else None
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def record_failure(self, customer_id, max_failures: int,
                       lock_seconds: int) -> None:
        locked_until = dt.datetime.now(dt.UTC) + dt.timedelta(
            seconds=lock_seconds)
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    sa.update(customers)
                    .where(customers.c.id == customer_id)
                    .values(
                        failed_attempts=customers.c.failed_attempts + 1,
                        locked_until=sa.case(
                            (customers.c.failed_attempts + 1 >= max_failures,
                             locked_until),
                            else_=customers.c.locked_until,
                        ),
                    )
                )
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def record_success(self, customer_id) -> None:
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    sa.update(customers)
                    .where(customers.c.id == customer_id)
                    .values(
                        failed_attempts=0,
                        locked_until=None,
                        last_login_at=sa.func.now(),
                    )
                )
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def create_session(self, token_hash: str, customer_id,
                       expires_at: dt.datetime) -> None:
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    sa.insert(sessions).values(
                        token_hash=token_hash,
                        customer_id=customer_id,
                        expires_at=expires_at,
                    )
                )
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def get_session(self, token_hash: str) -> dict | None:
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    sa.select(
                        customers.c.id,
                        customers.c.name,
                        customers.c.email,
                    ).select_from(
                        sessions.join(customers,
                                      sessions.c.customer_id == customers.c.id)
                    ).where(
                        sessions.c.token_hash == token_hash,
                        sessions.c.expires_at > sa.func.now(),
                    )
                ).first()
            return dict(row._mapping) if row else None
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def delete_session(self, token_hash: str) -> None:
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    sa.delete(sessions).where(sessions.c.token_hash == token_hash)
                )
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def delete_expired_sessions(self) -> None:
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    sa.delete(sessions).where(sessions.c.expires_at <= sa.func.now())
                )
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc

    def ping(self) -> None:
        try:
            with self.engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc
