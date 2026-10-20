import datetime as dt
import uuid
from typing import Callable, TypeVar

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
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, TimeoutError as SAConnectionTimeout

from app.domain.errors import (
    DependencyUnavailable,
    DomainError,
    HoldConflict,
    HoldExpired,
    HoldNotFound,
    InventoryBelowCommitted,
    InvalidState,
    NoInventory,
)
from app.domain.hold import CONFIRMED, EXPIRED, HELD, RELEASED, Hold

T = TypeVar("T")

metadata = MetaData()

inventory = Table(
    "inventory",
    metadata,
    Column("room_id", Uuid, nullable=False),
    Column("hotel_id", Uuid, nullable=False),
    Column("night", Date, nullable=False),
    Column("total", Integer, nullable=False),
    Column("held", Integer, nullable=False, server_default="0"),
    Column("confirmed", Integer, nullable=False, server_default="0"),
    # PK y CHECKs se definen en la migración Alembic; aquí solo para reflejo.
)

holds = Table(
    "holds",
    metadata,
    Column("hold_id", Uuid, primary_key=True),
    Column("room_id", Uuid, nullable=False),
    Column("check_in", Date, nullable=False),
    Column("check_out", Date, nullable=False),
    Column("units", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


def _nights(check_in: dt.date, check_out: dt.date) -> list[dt.date]:
    return [check_in + dt.timedelta(days=i) for i in range((check_out - check_in).days)]


class SqlInventoryStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def ping(self) -> None:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except (OperationalError, SAConnectionTimeout) as e:
            raise DependencyUnavailable("base de datos no disponible") from e

    def _run(self, fn: Callable[[object], T]) -> T:
        try:
            with self.engine.begin() as conn:
                return fn(conn)
        except DomainError:
            raise
        except (OperationalError, SAConnectionTimeout) as e:
            raise DependencyUnavailable("base de datos no disponible") from e

    @staticmethod
    def _now(conn) -> dt.datetime:
        return conn.execute(select(func.now())).scalar_one()

    @staticmethod
    def _to_hold(row) -> Hold:
        return Hold(
            hold_id=row["hold_id"],
            room_id=row["room_id"],
            check_in=row["check_in"],
            check_out=row["check_out"],
            units=row["units"],
            status=row["status"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def put_inventory(
        self,
        hotel_id: uuid.UUID,
        room_id: uuid.UUID,
        check_in: dt.date,
        check_out: dt.date,
        total: int,
    ) -> None:
        def op(conn):
            nights = _nights(check_in, check_out)
            rows = conn.execute(
                select(inventory)
                .where(inventory.c.room_id == room_id, inventory.c.night.in_(nights))
                .order_by(inventory.c.night)
                .with_for_update()
            ).fetchall()
            by_night = {r.night: r for r in rows}
            for n in nights:
                row = by_night.get(n)
                if row is not None and total < row.held + row.confirmed:
                    raise InventoryBelowCommitted("total por debajo de lo comprometido")
            for n in nights:
                conn.execute(
                    insert(inventory)
                    .values(room_id=room_id, hotel_id=hotel_id, night=n, total=total, held=0, confirmed=0)
                    .on_conflict_do_update(
                        index_elements=["room_id", "night"],
                        set_={"hotel_id": hotel_id, "total": total},
                    )
                )
            return None

        self._run(op)

    def search(
        self, hotel_id: uuid.UUID, check_in: dt.date, check_out: dt.date
    ) -> list[dict]:
        def op(conn):
            n_nights = (check_out - check_in).days
            rows = conn.execute(
                select(
                    inventory.c.room_id,
                    (func.min(inventory.c.total - inventory.c.held - inventory.c.confirmed)).label(
                        "available"
                    ),
                )
                .where(
                    inventory.c.hotel_id == hotel_id,
                    inventory.c.night >= check_in,
                    inventory.c.night < check_out,
                )
                .group_by(inventory.c.room_id)
                .having(func.count() == n_nights)
                .order_by(inventory.c.room_id)
            ).fetchall()
            return [{"room_id": r.room_id, "available": r.available} for r in rows]

        return self._run(op)

    def create_hold(
        self,
        hold_id: uuid.UUID,
        room_id: uuid.UUID,
        check_in: dt.date,
        check_out: dt.date,
        units: int,
        ttl_seconds: int,
    ) -> tuple[Hold, bool]:
        def op(conn):
            nights = _nights(check_in, check_out)
            now = self._now(conn)
            expires_at = now + dt.timedelta(seconds=ttl_seconds)

            result = conn.execute(
                insert(holds)
                .values(
                    hold_id=hold_id,
                    room_id=room_id,
                    check_in=check_in,
                    check_out=check_out,
                    units=units,
                    status=HELD,
                    expires_at=expires_at,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["hold_id"])
                .returning(holds.c.hold_id)
            )
            if result.fetchone() is None:
                existing = conn.execute(
                    select(holds).where(holds.c.hold_id == hold_id)
                ).mappings().one()
                h = self._to_hold(existing)
                if (h.room_id, h.check_in, h.check_out, h.units) == (room_id, check_in, check_out, units):
                    return h, False
                raise HoldConflict("mismo hold_id con parámetros distintos")

            rows = conn.execute(
                select(inventory)
                .where(inventory.c.room_id == room_id, inventory.c.night.in_(nights))
                .order_by(inventory.c.night)
                .with_for_update()
            ).fetchall()
            by_night = {r.night: r for r in rows}
            if len(by_night) != len(nights):
                raise NoInventory("sin inventario para todas las noches")
            for n in nights:
                row = by_night[n]
                if row.total - row.held - row.confirmed < units:
                    raise NoInventory("sin cupo suficiente")

            conn.execute(
                update(inventory)
                .where(inventory.c.room_id == room_id, inventory.c.night.in_(nights))
                .values(held=inventory.c.held + units)
            )

            return (
                Hold(
                    hold_id=hold_id,
                    room_id=room_id,
                    check_in=check_in,
                    check_out=check_out,
                    units=units,
                    status=HELD,
                    expires_at=expires_at,
                    created_at=now,
                    updated_at=now,
                ),
                True,
            )

        return self._run(op)

    def confirm_hold(self, hold_id: uuid.UUID) -> Hold:
        def op(conn):
            now = self._now(conn)
            row = conn.execute(
                select(holds).where(holds.c.hold_id == hold_id).with_for_update()
            ).mappings().first()
            if row is None:
                raise HoldNotFound()
            if row["status"] == CONFIRMED:
                return self._to_hold(row)
            if row["status"] == HELD:
                if row["expires_at"] <= now:
                    raise HoldExpired()
                nights = _nights(row["check_in"], row["check_out"])
                conn.execute(
                    update(inventory)
                    .where(inventory.c.room_id == row["room_id"], inventory.c.night.in_(nights))
                    .values(held=inventory.c.held - row["units"], confirmed=inventory.c.confirmed + row["units"])
                )
                conn.execute(
                    update(holds).where(holds.c.hold_id == hold_id).values(status=CONFIRMED, updated_at=now)
                )
                return Hold(
                    hold_id=row["hold_id"],
                    room_id=row["room_id"],
                    check_in=row["check_in"],
                    check_out=row["check_out"],
                    units=row["units"],
                    status=CONFIRMED,
                    expires_at=row["expires_at"],
                    created_at=row["created_at"],
                    updated_at=now,
                )
            if row["status"] == EXPIRED:
                raise HoldExpired()
            raise InvalidState(f"no se puede confirmar desde {row['status']}")

        return self._run(op)

    def release_hold(self, hold_id: uuid.UUID) -> Hold:
        def op(conn):
            now = self._now(conn)
            row = conn.execute(
                select(holds).where(holds.c.hold_id == hold_id).with_for_update()
            ).mappings().first()
            if row is None:
                raise HoldNotFound()
            if row["status"] == HELD:
                nights = _nights(row["check_in"], row["check_out"])
                conn.execute(
                    update(inventory)
                    .where(inventory.c.room_id == row["room_id"], inventory.c.night.in_(nights))
                    .values(held=inventory.c.held - row["units"])
                )
                conn.execute(
                    update(holds).where(holds.c.hold_id == hold_id).values(status=RELEASED, updated_at=now)
                )
            elif row["status"] == CONFIRMED:
                nights = _nights(row["check_in"], row["check_out"])
                conn.execute(
                    update(inventory)
                    .where(inventory.c.room_id == row["room_id"], inventory.c.night.in_(nights))
                    .values(confirmed=inventory.c.confirmed - row["units"])
                )
                conn.execute(
                    update(holds).where(holds.c.hold_id == hold_id).values(status=RELEASED, updated_at=now)
                )
            else:
                return self._to_hold(row)  # RELEASED/EXPIRED sin cambios
            return Hold(
                hold_id=row["hold_id"],
                room_id=row["room_id"],
                check_in=row["check_in"],
                check_out=row["check_out"],
                units=row["units"],
                status=RELEASED,
                expires_at=row["expires_at"],
                created_at=row["created_at"],
                updated_at=now,
            )

        return self._run(op)

    def extend_hold(self, hold_id: uuid.UUID, ttl_seconds: int) -> Hold:
        def op(conn):
            now = self._now(conn)
            row = conn.execute(
                select(holds).where(holds.c.hold_id == hold_id).with_for_update()
            ).mappings().first()
            if row is None:
                raise HoldNotFound()
            if row["status"] != HELD:
                raise InvalidState(f"no se puede extender desde {row['status']}")
            if row["expires_at"] <= now:
                raise HoldExpired()
            new_expires = now + dt.timedelta(seconds=ttl_seconds)
            conn.execute(
                update(holds).where(holds.c.hold_id == hold_id).values(expires_at=new_expires, updated_at=now)
            )
            return Hold(
                hold_id=row["hold_id"],
                room_id=row["room_id"],
                check_in=row["check_in"],
                check_out=row["check_out"],
                units=row["units"],
                status=HELD,
                expires_at=new_expires,
                created_at=row["created_at"],
                updated_at=now,
            )

        return self._run(op)

    def get_hold(self, hold_id: uuid.UUID) -> Hold:
        def op(conn):
            row = conn.execute(select(holds).where(holds.c.hold_id == hold_id)).mappings().first()
            if row is None:
                raise HoldNotFound()
            return self._to_hold(row)

        return self._run(op)

    def expire_due(self, limit: int) -> list[uuid.UUID]:
        def op(conn):
            now = self._now(conn)
            rows = conn.execute(
                select(holds)
                .where(holds.c.status == HELD, holds.c.expires_at <= now)
                .order_by(holds.c.expires_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).mappings().fetchall()
            released = []
            for row in rows:
                nights = _nights(row["check_in"], row["check_out"])
                conn.execute(
                    update(inventory)
                    .where(inventory.c.room_id == row["room_id"], inventory.c.night.in_(nights))
                    .values(held=inventory.c.held - row["units"])
                )
                conn.execute(
                    update(holds).where(holds.c.hold_id == row["hold_id"]).values(status=EXPIRED, updated_at=now)
                )
                released.append(row["hold_id"])
            return released

        return self._run(op)
