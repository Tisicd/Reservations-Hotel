import datetime as dt
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.domain.errors import DependencyUnavailable
from app.infrastructure.db.store import SqlInventoryStore


def test_check_en_bd_rechaza_sobreventa(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO inventory (room_id, hotel_id, night, total, held, confirmed) "
                    "VALUES (:r, :h, :n, 1, 2, 0)"
                ),
                {"r": uuid.uuid4(), "h": uuid.uuid4(), "n": dt.date(2026, 11, 10)},
            )


def test_fail_closed_lock_timeout(store, engine, db_url_fixture):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    ci = dt.date(2026, 11, 10)
    co = dt.date(2026, 11, 12)
    store.put_inventory(hotel, room, ci, co, total=2)

    holder = create_engine(db_url_fixture)
    with holder.begin() as conn:
        conn.execute(text("SELECT * FROM inventory WHERE room_id = :r FOR UPDATE"), {"r": room})

        low_timeout = create_engine(
            db_url_fixture, connect_args={"options": "-c lock_timeout=1000"}
        )
        s = SqlInventoryStore(low_timeout)
        hold_id = uuid.uuid4()
        with pytest.raises(DependencyUnavailable):
            s.create_hold(hold_id, room, ci, co, units=1, ttl_seconds=600)
        low_timeout.dispose()

    holder.dispose()

    # sin estado parcial
    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT count(*) FROM holds WHERE hold_id = :h"), {"h": hold_id}
        ).scalar()
        assert cnt == 0
        held = conn.execute(
            text("SELECT held FROM inventory WHERE room_id = :r AND night = :n"),
            {"r": room, "n": ci},
        ).scalar()
        assert held == 0
