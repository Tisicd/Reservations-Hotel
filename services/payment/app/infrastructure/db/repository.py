import datetime as dt
import uuid
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as SAConnectionTimeout

from app.domain.errors import (
    DependencyUnavailable,
    DomainError,
    IdempotencyKeyReused,
    InvalidState,
    PaymentNotFound,
)
from app.domain.payment import REFUNDED, SUCCEEDED, Payment

T = TypeVar("T")

metadata = MetaData()

payments = Table(
    "payments",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("reservation_id", Uuid, nullable=False, unique=True),
    Column("idempotency_key", String, nullable=False, unique=True),
    Column("request_hash", String, nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("currency", String, nullable=False),
    Column("method", String, nullable=False),
    Column("status", String, nullable=False),
    Column("provider_ref", String),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

payment_attempts = Table(
    "payment_attempts",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("payment_id", Uuid, nullable=False),
    Column("attempt_no", Integer, nullable=False),
    Column("simulate", String, nullable=False),
    Column("outcome", String),
    Column("error", String),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
)

ledger = Table(
    "ledger",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("payment_id", Uuid, nullable=False),
    Column("kind", String, nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("currency", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


def _to_payment(row) -> Payment:
    return Payment(
        id=row["id"],
        reservation_id=row["reservation_id"],
        idempotency_key=row["idempotency_key"],
        request_hash=row["request_hash"],
        amount_cents=row["amount_cents"],
        currency=row["currency"],
        method=row["method"],
        status=row["status"],
        provider_ref=row["provider_ref"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqlPaymentRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _run(self, fn: Callable[[object], T]) -> T:
        try:
            with self.engine.begin() as conn:
                return fn(conn)
        except DomainError:
            raise
        except (OperationalError, SAConnectionTimeout) as e:
            raise DependencyUnavailable("base de datos no disponible") from e

    def ping(self) -> None:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except (OperationalError, SAConnectionTimeout) as e:
            raise DependencyUnavailable("base de datos no disponible") from e

    def insert_initiated(
        self,
        reservation_id: uuid.UUID,
        idempotency_key: str,
        request_hash: str,
        amount_cents: int,
        currency: str,
        method: str,
    ) -> tuple[Payment, bool]:
        payment_id = uuid.uuid4()

        def op(conn):
            now = conn.execute(select(func.now())).scalar_one()
            created = conn.execute(
                pg_insert(payments)
                .values(
                    id=payment_id,
                    reservation_id=reservation_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    amount_cents=amount_cents,
                    currency=currency,
                    method=method,
                    status="INITIATED",
                    created_at=now,
                    updated_at=now,
                )
                # Sin objetivos: absorbe el conflicto por cualquier índice único
                # (idempotency_key o reservation_id). Distinguimos el caso por la
                # clave: si no existe la misma clave, es una reserva ya pagada.
                .on_conflict_do_nothing()
                .returning(payments.c.id)
            ).fetchone()
            if created is not None:
                row = conn.execute(select(payments).where(payments.c.id == payment_id))
                return _to_payment(row.mappings().one()), True
            row = conn.execute(
                select(payments).where(payments.c.idempotency_key == idempotency_key)
            )
            mapping = row.mappings().first()
            if mapping is None:
                raise IdempotencyKeyReused("ya existe un pago para esta reserva con otra clave")
            return _to_payment(mapping), False

        try:
            return self._run(op)
        except IntegrityError as e:
            raise IdempotencyKeyReused("ya existe un pago para esta reserva con otra clave") from e

    def get(self, payment_id: uuid.UUID) -> Payment:
        def op(conn):
            row = conn.execute(select(payments).where(payments.c.id == payment_id))
            mapping = row.mappings().first()
            if mapping is None:
                raise PaymentNotFound()
            return _to_payment(mapping)

        return self._run(op)

    def get_by_reservation(self, reservation_id: uuid.UUID) -> Payment:
        def op(conn):
            row = conn.execute(select(payments).where(payments.c.reservation_id == reservation_id))
            mapping = row.mappings().first()
            if mapping is None:
                raise PaymentNotFound()
            return _to_payment(mapping)

        return self._run(op)

    def start_attempt(self, payment_id: uuid.UUID, simulate: str) -> uuid.UUID:
        def op(conn):
            now = conn.execute(select(func.now())).scalar_one()
            conn.execute(select(payments.c.id).where(payments.c.id == payment_id).with_for_update())
            attempt_no = conn.execute(
                select(func.coalesce(func.max(payment_attempts.c.attempt_no), 0) + 1).where(
                    payment_attempts.c.payment_id == payment_id
                )
            ).scalar_one()
            attempt_id = uuid.uuid4()
            conn.execute(
                insert(payment_attempts).values(
                    id=attempt_id,
                    payment_id=payment_id,
                    attempt_no=attempt_no,
                    simulate=simulate,
                    started_at=now,
                )
            )
            return attempt_id

        return self._run(op)

    def finish_attempt(self, attempt_id: uuid.UUID, outcome: str, error: str | None) -> None:
        def op(conn):
            conn.execute(
                update(payment_attempts)
                .where(payment_attempts.c.id == attempt_id)
                .values(outcome=outcome, error=error, finished_at=func.now())
            )

        self._run(op)

    def record_result(
        self,
        payment_id: uuid.UUID,
        from_statuses: set[str],
        to_status: str,
        provider_ref: str | None = None,
    ) -> Payment | None:
        def op(conn):
            now = conn.execute(select(func.now())).scalar_one()
            values: dict = {"status": to_status, "updated_at": now}
            if provider_ref is not None:
                values["provider_ref"] = provider_ref
            changed = conn.execute(
                update(payments)
                .where(
                    payments.c.id == payment_id,
                    payments.c.status.in_(from_statuses),
                )
                .values(**values)
                .returning(payments.c.id)
            ).fetchone()
            if changed is None:
                return None
            if to_status == SUCCEEDED:
                row = conn.execute(
                    select(payments.c.amount_cents, payments.c.currency).where(
                        payments.c.id == payment_id
                    )
                ).one()
                conn.execute(
                    pg_insert(ledger)
                    .values(
                        id=uuid.uuid4(),
                        payment_id=payment_id,
                        kind="CHARGE",
                        amount_cents=row.amount_cents,
                        currency=row.currency,
                        created_at=now,
                    )
                    .on_conflict_do_nothing(index_elements=["payment_id", "kind"])
                )
            row = conn.execute(select(payments).where(payments.c.id == payment_id))
            return _to_payment(row.mappings().one())

        return self._run(op)

    def refund(self, payment_id: uuid.UUID) -> Payment | None:
        def op(conn):
            now = conn.execute(select(func.now())).scalar_one()
            row = (
                conn.execute(select(payments).where(payments.c.id == payment_id).with_for_update())
                .mappings()
                .first()
            )
            if row is None:
                raise PaymentNotFound()
            if row["status"] == REFUNDED:
                return _to_payment(row)
            if row["status"] != SUCCEEDED:
                raise InvalidState(f"no se puede reembolsar desde {row['status']}")
            conn.execute(
                update(payments)
                .where(payments.c.id == payment_id)
                .values(status=REFUNDED, updated_at=now)
            )
            conn.execute(
                pg_insert(ledger)
                .values(
                    id=uuid.uuid4(),
                    payment_id=payment_id,
                    kind="REFUND",
                    amount_cents=row["amount_cents"],
                    currency=row["currency"],
                    created_at=now,
                )
                .on_conflict_do_nothing(index_elements=["payment_id", "kind"])
            )
            updated = conn.execute(select(payments).where(payments.c.id == payment_id))
            return _to_payment(updated.mappings().one())

        return self._run(op)

    def list_unknown(self, min_age_seconds: int, limit: int) -> list[Payment]:
        def op(conn):
            cutoff = func.now() - dt.timedelta(seconds=min_age_seconds)
            rows = (
                conn.execute(
                    select(payments)
                    .where(payments.c.status == "UNKNOWN", payments.c.updated_at <= cutoff)
                    .order_by(payments.c.updated_at)
                    .with_for_update(skip_locked=True)
                    .limit(limit)
                )
                .mappings()
                .all()
            )
            return [_to_payment(r) for r in rows]

        return self._run(op)
