import datetime as dt
import uuid

import pytest

from app.domain.errors import HoldExpired, InvalidState
from app.domain.hold import CONFIRMED, EXPIRED, HELD, RELEASED, Hold, transition

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def make_hold(status=HELD, expires_at=None):
    return Hold(
        hold_id=uuid.uuid4(),
        room_id=uuid.uuid4(),
        check_in=dt.date(2026, 1, 1),
        check_out=dt.date(2026, 1, 3),
        units=1,
        status=status,
        expires_at=expires_at if expires_at is not None else NOW + dt.timedelta(minutes=10),
        created_at=NOW,
        updated_at=NOW,
    )


def test_confirm_desde_held_vigente():
    h = make_hold()
    assert transition(h, "confirm", h.expires_at - dt.timedelta(seconds=1)) == CONFIRMED


def test_confirm_es_idempotente():
    h = make_hold(status=CONFIRMED)
    assert transition(h, "confirm", NOW) == CONFIRMED


def test_confirm_hold_expirado():
    h = make_hold()
    with pytest.raises(HoldExpired):
        transition(h, "confirm", h.expires_at + dt.timedelta(seconds=1))


def test_release_desde_held_y_confirmed():
    assert transition(make_hold(HELD), "release", NOW) == RELEASED
    assert transition(make_hold(CONFIRMED), "release", NOW) == RELEASED


def test_release_terminal_sin_cambios():
    assert transition(make_hold(RELEASED), "release", NOW) == RELEASED
    assert transition(make_hold(EXPIRED), "release", NOW) == EXPIRED


def test_extend_solo_held_vigente():
    h = make_hold()
    assert transition(h, "extend", h.expires_at - dt.timedelta(seconds=1)) == HELD
    with pytest.raises(HoldExpired):
        transition(h, "extend", h.expires_at + dt.timedelta(seconds=1))
    with pytest.raises(InvalidState):
        transition(make_hold(CONFIRMED), "extend", NOW)


def test_confirm_desde_estado_invalido():
    with pytest.raises(InvalidState):
        transition(make_hold(RELEASED), "confirm", NOW)


def test_is_expired():
    h = make_hold()
    assert not h.is_expired(h.expires_at - dt.timedelta(seconds=1))
    assert h.is_expired(h.expires_at + dt.timedelta(seconds=1))
    assert not make_hold(CONFIRMED).is_expired(h.expires_at + dt.timedelta(hours=1))
