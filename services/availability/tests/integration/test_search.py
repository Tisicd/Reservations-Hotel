import datetime as dt
import uuid

from app.domain.hold import CONFIRMED


def test_search_devuelve_minimo_por_noche(store):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    ci = dt.date(2026, 11, 10)
    co = dt.date(2026, 11, 13)
    store.put_inventory(hotel, room, ci, co, total=3)
    hold_id = uuid.uuid4()
    store.create_hold(hold_id, room, ci, co, units=1, ttl_seconds=600)

    result = store.search(hotel, ci, co)
    assert result == [{"room_id": room, "available": 2}]


def test_search_incluye_disponibilidad_cero(store):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    ci = dt.date(2026, 11, 10)
    co = dt.date(2026, 11, 12)
    store.put_inventory(hotel, room, ci, co, total=1)
    store.create_hold(uuid.uuid4(), room, ci, co, units=1, ttl_seconds=600)

    result = store.search(hotel, ci, co)
    assert result == [{"room_id": room, "available": 0}]


def test_search_excluye_habitacion_con_noches_sin_inventario(store):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    ci = dt.date(2026, 11, 10)
    co = dt.date(2026, 11, 13)
    # inventario solo 2 de 3 noches
    store.put_inventory(hotel, room, ci, dt.date(2026, 11, 12), total=3)
    assert store.search(hotel, ci, co) == []


def test_search_refleja_confirmaciones(store):
    room = uuid.uuid4()
    hotel = uuid.uuid4()
    ci = dt.date(2026, 11, 10)
    co = dt.date(2026, 11, 12)
    store.put_inventory(hotel, room, ci, co, total=2)
    hold_id = uuid.uuid4()
    store.create_hold(hold_id, room, ci, co, units=1, ttl_seconds=600)
    assert store.search(hotel, ci, co)[0]["available"] == 1
    store.confirm_hold(hold_id)
    assert store.search(hotel, ci, co)[0]["available"] == 1  # held -> confirmed


def test_search_otra_habitacion_aparece(store):
    hotel = uuid.uuid4()
    ci = dt.date(2026, 11, 10)
    co = dt.date(2026, 11, 12)
    r1 = uuid.uuid4()
    r2 = uuid.uuid4()
    store.put_inventory(hotel, r1, ci, co, total=1)
    store.put_inventory(hotel, r2, ci, co, total=4)
    result = {r["room_id"]: r["available"] for r in store.search(hotel, ci, co)}
    assert result == {r1: 1, r2: 4}
