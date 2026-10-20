import datetime as dt
import uuid

import pytest

from app.domain.errors import InvalidState
from app.domain.payment import (
    DECLINED,
    FAILED_TECHNICAL,
    INITIATED,
    REFUNDED,
    SUCCEEDED,
    UNKNOWN,
    Payment,
    request_hash,
)


def _payment(status=INITIATED):
    now = dt.datetime.now(dt.UTC)
    return Payment(
        id=uuid.uuid4(),
        reservation_id=uuid.uuid4(),
        idempotency_key="k",
        request_hash="h",
        amount_cents=1000,
        currency="USD",
        method="card",
        status=status,
        provider_ref=None,
        created_at=now,
        updated_at=now,
    )


def test_transiciones_validas():
    p = _payment(INITIATED)
    assert p.transition(SUCCEEDED).status == SUCCEEDED
    assert p.transition(DECLINED).status == DECLINED
    assert p.transition(FAILED_TECHNICAL).status == FAILED_TECHNICAL
    assert p.transition(UNKNOWN).status == UNKNOWN
    assert _payment(UNKNOWN).transition(SUCCEEDED).status == SUCCEEDED
    assert _payment(UNKNOWN).transition(DECLINED).status == DECLINED
    assert _payment(FAILED_TECHNICAL).transition(INITIATED).status == INITIATED
    assert _payment(SUCCEEDED).transition(REFUNDED).status == REFUNDED


@pytest.mark.parametrize("target", [INITIATED, REFUNDED])
def test_transiciones_invalidas_desde_initiated(target):
    with pytest.raises(InvalidState):
        _payment(INITIATED).transition(target)


@pytest.mark.parametrize("state", [DECLINED, REFUNDED])
def test_terminales_no_transicionan(state):
    for target in (SUCCEEDED, UNKNOWN, INITIATED, REFUNDED):
        with pytest.raises(InvalidState):
            _payment(state).transition(target)


def test_request_hash_excluye_simulate():
    rid = uuid.uuid4()
    a = request_hash(rid, 30000, "USD", "card", "tok_demo")
    b = request_hash(rid, 30000, "USD", "card", "tok_demo")
    assert a == b
    assert request_hash(rid, 30001, "USD", "card", "tok_demo") != a
    assert request_hash(rid, 30000, "EUR", "card", "tok_demo") != a
