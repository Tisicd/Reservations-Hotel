from __future__ import annotations

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
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SAConnectionTimeout

from app.domain.errors import DependencyUnavailable
from app.domain.notification import Notification

T = TypeVar("T")

metadata = MetaData()

notifications = Table(
    "notifications",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("event_id", Uuid, nullable=False, unique=True),
    Column("type", String, nullable=False),
    Column("reservation_id", Uuid, nullable=False),
    Column("customer_id", Uuid, nullable=False),
    Column("payload", JSONB, nullable=False, default=dict),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("next_attempt_at", DateTime(timezone=True), nullable=False),
    Column("last_error", String),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("sent_at", DateTime(timezone=True)),
)


def _to_notification(row) -> Notification:
    return Notification(
        id=row["id"],
        event_id=row["event_id"],
        type=row["type"],
        reservation_id=row["reservation_id"],
        customer_id=row["customer_id"],
        payload=row["payload"] or {},
        status=row["status"],
        attempts=row["attempts"],
        created_at=row["created_at"],
        next_attempt_at=row["next_attempt_at"],
        sent_at=row["sent_at"],
        last_error=row["last_error"],
    )


class SqlNotificationRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _run(self, fn: Callable[[object], T]) -> T:
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

    def insert_inbox(
        self,
        event_id: uuid.UUID,
        type: str,
        reservation_id: uuid.UUID,
        customer_id: uuid.UUID,
        payload: dict,
    ) -> tuple[Notification, bool]:
        notification_id = uuid.uuid4()

        def op(conn):
            created = conn.execute(
                pg_insert(notifications)
                .values(
                    id=notification_id,
                    event_id=event_id,
                    type=type,
                    reservation_id=reservation_id,
                    customer_id=customer_id,
                    payload=payload,
                    status="PENDING",
                    attempts=0,
                )
                .on_conflict_do_nothing(index_elements=["event_id"])
                .returning(notifications.c.id)
            ).fetchone()
            if created is not None:
                row = conn.execute(
                    select(notifications).where(notifications.c.id == notification_id)
                )
                return _to_notification(row.mappings().one()), True
            row = conn.execute(
                select(notifications).where(notifications.c.event_id == event_id)
            )
            return _to_notification(row.mappings().one()), False

        return self._run(op)

    def list_by_reservation(self, reservation_id: uuid.UUID) -> list[Notification]:
        def op(conn):
            rows = conn.execute(
                select(notifications)
                .where(notifications.c.reservation_id == reservation_id)
                .order_by(notifications.c.created_at)
            ).mappings()
            return [_to_notification(row) for row in rows]

        return self._run(op)

    def claim_due(self, limit: int, lease_seconds: int) -> list[Notification]:
        def op(conn):
            due = (
                select(notifications.c.id)
                .where(
                    notifications.c.status == "PENDING",
                    notifications.c.next_attempt_at <= func.now(),
                )
                .order_by(notifications.c.next_attempt_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            rows = conn.execute(
                update(notifications)
                .where(notifications.c.id.in_(due))
                .values(
                    attempts=notifications.c.attempts + 1,
                    next_attempt_at=func.now() + dt.timedelta(seconds=lease_seconds),
                )
                .returning(notifications)
            ).mappings()
            return [_to_notification(row) for row in rows]

        return self._run(op)

    def mark_sent(self, notification_id: uuid.UUID) -> None:
        def op(conn):
            conn.execute(
                update(notifications)
                .where(
                    notifications.c.id == notification_id,
                    notifications.c.status == "PENDING",
                )
                .values(status="SENT", sent_at=func.now(), last_error=None)
            )

        self._run(op)

    def mark_retry(
        self,
        notification_id: uuid.UUID,
        failed: bool,
        next_attempt_at: dt.datetime,
        error: str,
    ) -> None:
        def op(conn):
            conn.execute(
                update(notifications)
                .where(notifications.c.id == notification_id)
                .values(
                    status="FAILED" if failed else "PENDING",
                    next_attempt_at=next_attempt_at,
                    last_error=error,
                )
            )

        self._run(op)
