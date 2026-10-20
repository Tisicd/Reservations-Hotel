import datetime as dt

import pytest

from app.domain.date_range import DateRange
from app.domain.errors import InvalidDateRange


def test_nights_es_intervalo_abierto():
    r = DateRange(dt.date(2026, 11, 10), dt.date(2026, 11, 13))
    assert r.nights == [
        dt.date(2026, 11, 10),
        dt.date(2026, 11, 11),
        dt.date(2026, 11, 12),
    ]


def test_check_out_igual_o_anterior_invalido():
    with pytest.raises(InvalidDateRange):
        DateRange(dt.date(2026, 11, 10), dt.date(2026, 11, 10))
    with pytest.raises(InvalidDateRange):
        DateRange(dt.date(2026, 11, 10), dt.date(2026, 11, 9))


def test_excede_max_noches():
    with pytest.raises(InvalidDateRange):
        DateRange(dt.date(2026, 11, 1), dt.date(2026, 11, 4), max_nights=2)


def test_una_noche_valida():
    r = DateRange(dt.date(2026, 11, 10), dt.date(2026, 11, 11))
    assert r.nights == [dt.date(2026, 11, 10)]
