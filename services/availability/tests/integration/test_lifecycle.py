import datetime as dt
import time
import uuid

import pytest
from sqlalchemy import text

from app.domain.errors import (
    HoldExpired,
    HoldNotFound,
    InventoryBelowCommitted,
    InvalidState,
)
from app.domain.hold import CONFIRMED, RELEASED


def _seed(store, total=5):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    check_in = dt.date(2026, 11, 10)
    check_out = dt.date(2026, 11, 13)
    store.put_inventory(hotel, room, check_in, check_out, total=total)
    return room, hotel, check_in, check_out


def test_ciclo_de_vida_completo(store, engine):
    room, hotel, ci, co = _seed(store)
    hold_id = uuid.uuid4()
    h, created = store.create_hold(hold_id, room, ci, co, units=2, ttl_seconds=600)
    assert created is True
    assert h.status == "HELD"

    # confirm idempotente
    c1 = store.confirm_hold(hold_id)
    c2 = store.confirm_hold(hold_id)
    assert c1.status == CONFIRMED and c2.status == CONFIRMED
    with engine.connect() as conn:
        held = conn.execute(text("SELECT held FROM inventory WHERE room_id = :r AND night = :n"), {"r": room, "n": ci}).scalar()
        confirmed = conn.execute(text("SELECT confirmed FROM inventory WHERE room_id = :r AND night = :n"), {"r": room, "n": ci}).scalar()
        assert held == 0 and confirmed == 2

    # release desde CONFIRMED restaura
    r = store.release_hold(hold_id)
    assert r.status == RELEASED
    with engine.connect() as conn:
        confirmed = conn.execute(text("SELECT confirmed FROM inventory WHERE room_id = :r AND night = :n"), {"r": room, "n": ci}).scalar()
        assert confirmed == 0


def test_release_desde_held_y_repetido_sin_efecto(store, engine):
    room, hotel, ci, co = _seed(store)
    hold_id = uuid.uuid4()
    store.create_hold(hold_id, room, ci, co, units=1, ttl_seconds=600)
    assert store.release_hold(hold_id).status == RELEASED
    assert store.release_hold(hold_id).status == RELEASED  # sin efecto
    with engine.connect() as conn:
        held = conn.execute(text("SELECT held FROM inventory WHERE room_id = :r AND night = :n"), {"r": room, "n": ci}).scalar()
        assert held == 0


def test_confirm_tras_release_invalid_state(store):
    room, hotel, ci, co = _seed(store)
    hold_id = uuid.uuid4()
    store.create_hold(hold_id, room, ci, co, units=1, ttl_seconds=600)
    store.release_hold(hold_id)
    with pytest.raises(InvalidState):
        store.confirm_hold(hold_id)


def test_hold_inexistente(store):
    with pytest.raises(HoldNotFound):
        store.confirm_hold(uuid.uuid4())
    with pytest.raises(HoldNotFound):
        store.get_hold(uuid.uuid4())


def test_expiracion_libera_cupo(store, engine):
    room, hotel, ci, co = _seed(store)
    hold_id = uuid.uuid4()
    store.create_hold(hold_id, room, ci, co, units=1, ttl_seconds=1)
    time.sleep(1.2)

    with pytest.raises(HoldExpired):
        store.confirm_hold(hold_id)

    released = store.expire_due(limit=100)
    assert hold_id in released
    with engine.connect() as conn:
        held = conn.execute(text("SELECT held FROM inventory WHERE room_id = :r AND night = :n"), {"r": room, "n": ci}).scalar()
        status = conn.execute(text("SELECT status FROM holds WHERE hold_id = :h"), {"h": hold_id}).scalar()
        assert held == 0 and status == "EXPIRED"


def test_extend_antes_y_despues_de_expirar(store):
    room, hotel, ci, co = _seed(store)
    hold_id = uuid.uuid4()
    store.create_hold(hold_id, room, ci, co, units=1, ttl_seconds=2)

    # extiende antes de expirar
    h = store.extend_hold(hold_id, ttl_seconds=60)
    assert h.status == "HELD"

    time.sleep(2.2)
    # tras expirar (aunque el primer ttl era 2s, extendió a 60s -> sigue vigente)
    assert store.extend_hold(hold_id, ttl_seconds=60).status == "HELD"


def test_extend_falla_tras_expirar(store):
    room, hotel, ci, co = _seed(store)
    hold_id = uuid.uuid4()
    store.create_hold(hold_id, room, ci, co, units=1, ttl_seconds=1)
    time.sleep(1.2)
    with pytest.raises(HoldExpired):
        store.extend_hold(hold_id, ttl_seconds=60)


def test_put_inventory_no_baja_por_debajo_de_comprometido(store):
    room, hotel, ci, co = _seed(store, total=2)
    hold_id = uuid.uuid4()
    store.create_hold(hold_id, room, ci, co, units=2, ttl_seconds=600)
    with pytest.raises(InventoryBelowCommitted):
        store.put_inventory(hotel, room, ci, co, total=1)


def test_put_inventory_amplia_rango(store, engine):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    ci = dt.date(2026, 11, 10)
    co = dt.date(2026, 11, 13)
    store.put_inventory(hotel, room, ci, co, total=3)
    # amplía el rango una noche más
    store.put_inventory(hotel, room, ci, dt.date(2026, 11, 14), total=3)
    with engine.connect() as conn:
        cnt = conn.execute(text("SELECT count(*) FROM inventory WHERE room_id = :r"), {"r": room}).scalar()
        assert cnt == 4
