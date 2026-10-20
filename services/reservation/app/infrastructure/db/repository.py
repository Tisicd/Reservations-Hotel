import dataclasses
import datetime as dt
import uuid

from sqlalchemy import (
    Column,
    Date,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SAConnectionTimeout

from app.domain.errors import (
    ConcurrentModification,
    DependencyUnavailable,
    ReservationNotFound,
)
from app.domain.outbox import OutboxEvent
from app.domain.reservation import Reservation
from app.domain.state_machine import STABLE_STATES, ensure_transition

metadata = MetaData()

reservations = Table(
    "reservations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("idempotency_key", String, nullable=False, unique=True),
    Column("request_hash", String, nullable=False),
    Column("customer_id", Uuid, nullable=False),
    Column("hotel_id", Uuid, nullable=False),
    Column("room_id", Uuid, nullable=False),
    Column("check_in", Date, nullable=False),
    Column("check_out", Date, nullable=False),
    Column("nights", Integer, nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("currency", String, nullable=False),
    Column("payment_method", String, nullable=False),
    Column("payment_token", String, nullable=False),
    Column("payment_simulate", String, nullable=False),
    Column("payment_id", Uuid),
    Column("payment_status", String),
    Column("status", String, nullable=False),
    Column("status_reason", String),
    Column("attempts", Integer, nullable=False),
    Column("next_attempt_at", DateTime(timezone=True)),
    Column("phase_started_at", DateTime(timezone=True), nullable=False),
    Column("locked_until", DateTime(timezone=True)),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

reservation_events = Table(
    "reservation_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("reservation_id", Uuid, nullable=False),
    Column("from_status", String),
    Column("to_status", String, nullable=False),
    Column("reason", String),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

outbox = Table(
    "outbox",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("aggregate_id", Uuid, nullable=False),
    Column("type", String, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("next_attempt_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("sent_at", DateTime(timezone=True)),
)

STABLE = tuple(sorted(STABLE_STATES))


def _to_reservation(row) -> Reservation:
    return Reservation(
        id=row["id"],
        idempotency_key=row["idempotency_key"],
        request_hash=row["request_hash"],
        customer_id=row["customer_id"],
        hotel_id=row["hotel_id"],
        room_id=row["room_id"],
        check_in=row["check_in"],
        check_out=row["check_out"],
        nights=row["nights"],
        amount_cents=row["amount_cents"],
        currency=row["currency"],
        payment_method=row["payment_method"],
        payment_token=row["payment_token"],
        payment_simulate=row["payment_simulate"],
        status=row["status"],
        status_reason=row["status_reason"],
        payment_id=row["payment_id"],
        payment_status=row["payment_status"],
        attempts=row["attempts"],
        next_attempt_at=row["next_attempt_at"],
        phase_started_at=row["phase_started_at"],
        locked_until=row["locked_until"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _insert_event(conn, reservation_id, from_status, to_status, reason, now) -> None:
    conn.execute(
        insert(reservation_events).values(
            reservation_id=reservation_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            created_at=now,
        )
    )


def _insert_outbox(conn, aggregate_id, event: dict, now) -> None:
    conn.execute(
        insert(outbox).values(
            id=uuid.uuid4(),
            aggregate_id=aggregate_id,
            type=event["type"],
            payload=event["payload"],
            status="PENDING",
            attempts=0,
            next_attempt_at=now,
            created_at=now,
        )
    )


class SqlReservationRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _run(self, fn):
        try:
            with self.engine.begin() as conn:
                return fn(conn)
        except (OperationalError, SAConnectionTimeout) as e:
            raise DependencyUnavailable("base de datos no disponible") from e

    def ping(self) -> None:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except (OperationalError, SAConnectionTimeout) as e:
            raise DependencyUnavailable("base de datos no disponible") from e

    def get(self, reservation_id: uuid.UUID) -> Reservation:
        def op(conn):
            row = conn.execute(
                select(reservations).where(reservations.c.id == reservation_id)
            ).mappings().first()
            if row is None:
                raise ReservationNotFound()
            return _to_reservation(row)

        return self._run(op)

    def get_by_idempotency_key(self, key: str) -> Reservation | None:
        def op(conn):
            row = conn.execute(
                select(reservations).where(reservations.c.idempotency_key == key)
            ).mappings().first()
            return _to_reservation(row) if row else None

        return self._run(op)

    def create_received(self, reservation: Reservation) -> tuple[Reservation, bool]:
        def op(conn):
            inserted = conn.execute(
                pg_insert(reservations)
                .values(**dataclasses.asdict(reservation))
                .on_conflict_do_nothing()
                .returning(reservations.c.id)
            ).fetchone()
            if inserted is None:
                row = conn.execute(
                    select(reservations).where(
                        reservations.c.idempotency_key == reservation.idempotency_key
                    )
                ).mappings().one()
                return _to_reservation(row), False
            now = conn.execute(select(func.now())).scalar_one()
            _insert_event(conn, reservation.id, None, reservation.status, None, now)
            row = conn.execute(
                select(reservations).where(reservations.c.id == reservation.id)
            ).mappings().one()
            return _to_reservation(row), True

        return self._run(op)

    def transition(
        self,
        reservation: Reservation,
        to_status: str,
        reason: str | None,
        patch: dict,
        outbox_event: dict | None = None,
    ) -> Reservation:
        return self.transition_chain(reservation, [to_status], reason, patch, outbox_event)

    def transition_chain(
        self,
        reservation: Reservation,
        to_statuses: list[str],
        reason: str | None,
        patch: dict,
        outbox_event: dict | None = None,
    ) -> Reservation:
        def op(conn):
            row = (
                conn.execute(
                    select(reservations)
                    .where(reservations.c.id == reservation.id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ReservationNotFound()
            current = _to_reservation(row)
            if (
                current.status != reservation.status
                or current.version != reservation.version
            ):
                raise ConcurrentModification()
            now = conn.execute(select(func.now())).scalar_one()
            for index, to_status in enumerate(to_statuses):
                last = index == len(to_statuses) - 1
                ensure_transition(current.status, to_status)
                values = {
                    "status": to_status,
                    "status_reason": reason if last else None,
                    "phase_started_at": now,
                    "next_attempt_at": now,
                    "attempts": 0,
                    "locked_until": None,
                    "version": current.version + 1,
                    "updated_at": now,
                }
                if last:
                    values.update(patch)
                _insert_event(
                    conn, current.id, current.status, to_status, values["status_reason"], now
                )
                current = dataclasses.replace(current, **values)
                conn.execute(
                    update(reservations)
                    .where(reservations.c.id == current.id)
                    .values(**values)
                )
            if outbox_event is not None:
                _insert_outbox(conn, current.id, outbox_event, now)
            return current

        return self._run(op)

    def schedule_retry(
        self, reservation_id: uuid.UUID, attempts: int, next_attempt_at: dt.datetime
    ) -> None:
        def op(conn):
            result = conn.execute(
                update(reservations)
                .where(reservations.c.id == reservation_id)
                .values(
                    attempts=attempts,
                    next_attempt_at=next_attempt_at,
                    locked_until=None,
                    version=reservations.c.version + 1,
                    updated_at=func.now(),
                )
            )
            if result.rowcount == 0:
                raise ReservationNotFound()

        self._run(op)

    def claim(self, reservation_id: uuid.UUID, lease_seconds: int) -> Reservation | None:
        def op(conn):
            row = conn.execute(
                update(reservations)
                .where(
                    reservations.c.id == reservation_id,
                    reservations.c.status.notin_(STABLE),
                    (reservations.c.locked_until.is_(None))
                    | (reservations.c.locked_until <= func.now()),
                    (reservations.c.next_attempt_at.is_(None))
                    | (reservations.c.next_attempt_at <= func.now()),
                )
                .values(locked_until=func.now() + dt.timedelta(seconds=lease_seconds))
                .returning(reservations)
            ).mappings().first()
            return _to_reservation(row) if row else None

        return self._run(op)

    def claim_due(self, limit: int, lease_seconds: int) -> list[Reservation]:
        def op(conn):
            due = (
                select(reservations.c.id)
                .where(
                    reservations.c.status.notin_(STABLE),
                    (reservations.c.locked_until.is_(None))
                    | (reservations.c.locked_until <= func.now()),
                    (reservations.c.next_attempt_at.is_(None))
                    | (reservations.c.next_attempt_at <= func.now()),
                )
                .order_by(reservations.c.next_attempt_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            rows = conn.execute(
                update(reservations)
                .where(reservations.c.id.in_(due))
                .values(locked_until=func.now() + dt.timedelta(seconds=lease_seconds))
                .returning(reservations)
            ).mappings()
            return [_to_reservation(row) for row in rows]

        return self._run(op)

    def claim_outbox(self, limit: int, lease_seconds: int) -> list[OutboxEvent]:
        def op(conn):
            due = (
                select(outbox.c.id)
                .where(
                    outbox.c.status == "PENDING",
                    outbox.c.next_attempt_at <= func.now(),
                )
                .order_by(outbox.c.next_attempt_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            rows = conn.execute(
                update(outbox)
                .where(outbox.c.id.in_(due))
                .values(
                    attempts=outbox.c.attempts + 1,
                    next_attempt_at=func.now() + dt.timedelta(seconds=lease_seconds),
                )
                .returning(outbox)
            ).mappings()
            return [
                OutboxEvent(
                    id=row["id"],
                    aggregate_id=row["aggregate_id"],
                    type=row["type"],
                    payload=row["payload"],
                    attempts=row["attempts"],
                )
                for row in rows
            ]

        return self._run(op)

    def mark_outbox_sent(self, outbox_id: uuid.UUID) -> None:
        def op(conn):
            conn.execute(
                update(outbox)
                .where(outbox.c.id == outbox_id, outbox.c.status == "PENDING")
                .values(status="SENT", sent_at=func.now())
            )

        self._run(op)

    def reschedule_outbox(self, outbox_id: uuid.UUID, delay_seconds: float) -> None:
        def op(conn):
            conn.execute(
                update(outbox)
                .where(outbox.c.id == outbox_id)
                .values(next_attempt_at=func.now() + dt.timedelta(seconds=delay_seconds))
            )

        self._run(op)

    def list_by_customer(self, customer_id: uuid.UUID) -> list[Reservation]:
        def op(conn):
            rows = conn.execute(
                select(reservations)
                .where(reservations.c.customer_id == customer_id)
                .order_by(reservations.c.created_at.desc())
            ).mappings()
            return [_to_reservation(row) for row in rows]

        return self._run(op)

    def events(self, reservation_id: uuid.UUID) -> list[dict]:
        def op(conn):
            rows = conn.execute(
                select(reservation_events)
                .where(reservation_events.c.reservation_id == reservation_id)
                .order_by(reservation_events.c.id)
            ).mappings()
            return [
                {
                    "reservation_id": row["reservation_id"],
                    "from_status": row["from_status"],
                    "to_status": row["to_status"],
                    "reason": row["reason"],
                    "at": row["created_at"],
                }
                for row in rows
            ]

        return self._run(op)
