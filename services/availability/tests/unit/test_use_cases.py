import datetime as dt
import uuid

import pytest

from app.application.use_cases import AvailabilityService
from app.domain.errors import InvalidDateRange, ValidationError


class FakeStore:
    def __init__(self):
        self.calls = []

    def put_inventory(self, *a, **k):
        self.calls.append(("put_inventory", a, k))

    def search(self, *a, **k):
        self.calls.append(("search", a, k))
        return []

    def create_hold(self, *a, **k):
        self.calls.append(("create_hold", a, k))
        return (None, True)

    def extend_hold(self, *a, **k):
        self.calls.append(("extend_hold", a, k))

    def confirm_hold(self, *a, **k):
        self.calls.append(("confirm_hold", a, k))

    def release_hold(self, *a, **k):
        self.calls.append(("release_hold", a, k))

    def get_hold(self, *a, **k):
        self.calls.append(("get_hold", a, k))

    def expire_due(self, *a, **k):
        self.calls.append(("expire_due", a, k))
        return []

    def ping(self):
        self.calls.append(("ping",))


def svc(store=None):
    return AvailabilityService(store or FakeStore())


def test_units_fuera_de_rango():
    s = svc()
    args = (uuid.uuid4(), uuid.uuid4(), dt.date(2026, 1, 1), dt.date(2026, 1, 2))
    with pytest.raises(ValidationError):
        s.create_hold(*args, units=0)
    with pytest.raises(ValidationError):
        s.create_hold(*args, units=11)


def test_ttl_fuera_de_rango():
    s = svc()
    args = (uuid.uuid4(), uuid.uuid4(), dt.date(2026, 1, 1), dt.date(2026, 1, 2))
    with pytest.raises(ValidationError):
        s.create_hold(*args, units=1, ttl_seconds=0)
    with pytest.raises(ValidationError):
        s.create_hold(*args, units=1, ttl_seconds=3601)


def test_ttl_por_defecto():
    store = FakeStore()
    s = svc(store)
    h = uuid.uuid4()
    s.create_hold(h, uuid.uuid4(), dt.date(2026, 1, 1), dt.date(2026, 1, 2), units=1)
    call = store.calls[0]
    assert call[0] == "create_hold"
    assert call[1][5] == 600  # ttl_seconds es el 6º argumento posicional


def test_fecha_invalida():
    s = svc()
    with pytest.raises(InvalidDateRange):
        s.search(uuid.uuid4(), dt.date(2026, 1, 2), dt.date(2026, 1, 1))


def test_total_negativo_rechazado():
    s = svc()
    with pytest.raises(ValidationError):
        s.put_inventory(
            uuid.uuid4(), uuid.uuid4(), dt.date(2026, 1, 1), dt.date(2026, 1, 2), total=-1
        )


def test_extend_valida_ttl():
    store = FakeStore()
    s = svc(store)
    with pytest.raises(ValidationError):
        s.extend_hold(uuid.uuid4(), ttl_seconds=0)
