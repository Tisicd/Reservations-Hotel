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
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)


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

    def ping(self) -> None:
        try:
            with self.engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise DependencyUnavailable("base de datos no disponible") from exc
