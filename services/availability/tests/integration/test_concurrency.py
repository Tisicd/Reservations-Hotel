import datetime as dt
import random
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text

from app.domain.errors import DependencyUnavailable, HoldConflict, NoInventory
from app.infrastructure.db.store import SqlInventoryStore


def test_concurrencia_i1_sin_sobreventa(store, engine, db_url_fixture):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    check_in = dt.date(2026, 11, 10)
    check_out = dt.date(2026, 11, 13)
    store.put_inventory(hotel, room, check_in, check_out, total=5)

    big = create_engine(db_url_fixture, pool_size=50)
    results = []

    def worker(_):
        s = SqlInventoryStore(big)
        try:
            s.create_hold(uuid.uuid4(), room, check_in, check_out, units=1, ttl_seconds=600)
            results.append("HELD")
        except NoInventory:
            results.append("NO_INVENTORY")
        except DependencyUnavailable:
            results.append("DEP_UNAVAILABLE")

    with ThreadPoolExecutor(max_workers=50) as ex:
        list(ex.map(worker, range(50)))
    big.dispose()

    assert results.count("HELD") == 5
    assert results.count("NO_INVENTORY") == 45
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT held + confirmed, total FROM inventory WHERE room_id = :r"), {"r": room}
        ).fetchall()
        assert all(row[0] <= row[1] for row in rows)
        held_nights = [
            r[0]
            for r in conn.execute(
                text("SELECT held FROM inventory WHERE room_id = :r ORDER BY night"), {"r": room}
            ).fetchall()
        ]
        assert held_nights == [5, 5, 5]


def test_rangos_solapados_sin_interbloqueos(store, engine, db_url_fixture):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    check_in = dt.date(2026, 11, 10)
    check_out = dt.date(2026, 11, 20)
    store.put_inventory(hotel, room, check_in, check_out, total=2)

    random.seed(42)
    ranges = []
    for _ in range(100):
        start = random.randint(0, 9)
        length = random.randint(1, 10 - start)
        ranges.append(
            (check_in + dt.timedelta(days=start), check_in + dt.timedelta(days=start + length))
        )

    big = create_engine(db_url_fixture, pool_size=50)
    errors = []

    def worker(rng):
        ci, co = rng
        s = SqlInventoryStore(big)
        try:
            s.create_hold(uuid.uuid4(), room, ci, co, units=1, ttl_seconds=600)
        except (NoInventory, DependencyUnavailable):
            pass
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    with ThreadPoolExecutor(max_workers=50) as ex:
        list(ex.map(worker, ranges))
    big.dispose()

    assert errors == []
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT held + confirmed, total FROM inventory WHERE room_id = :r"), {"r": room}
        ).fetchall()
        assert all(row[0] <= row[1] for row in rows)


def test_idempotencia_mismo_hold_id(store, engine, db_url_fixture):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    check_in = dt.date(2026, 11, 10)
    check_out = dt.date(2026, 11, 12)
    store.put_inventory(hotel, room, check_in, check_out, total=5)
    hold_id = uuid.uuid4()

    big = create_engine(db_url_fixture, pool_size=50)
    created = []

    def worker(_):
        s = SqlInventoryStore(big)
        _, was_created = s.create_hold(hold_id, room, check_in, check_out, units=1, ttl_seconds=600)
        if was_created:
            created.append(True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(worker, range(10)))
    big.dispose()

    assert len(created) == 1
    with engine.connect() as conn:
        cnt = conn.execute(text("SELECT count(*) FROM holds WHERE hold_id = :h"), {"h": hold_id}).scalar()
        assert cnt == 1
        held_nights = [
            r[0]
            for r in conn.execute(
                text("SELECT held FROM inventory WHERE room_id = :r ORDER BY night"), {"r": room}
            ).fetchall()
        ]
        assert held_nights == [1, 1]


def test_idempotencia_conflicto_parametros_distintos(store):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    check_in = dt.date(2026, 11, 10)
    check_out = dt.date(2026, 11, 12)
    store.put_inventory(hotel, room, check_in, check_out, total=5)
    hold_id = uuid.uuid4()
    store.create_hold(hold_id, room, check_in, check_out, units=1, ttl_seconds=600)

    with pytest.raises(HoldConflict):
        store.create_hold(hold_id, room, check_in, check_out, units=2, ttl_seconds=600)
