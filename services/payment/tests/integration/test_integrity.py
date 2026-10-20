import uuid

import pytest
from sqlalchemy import text
from test_lifecycle import _create

from app.application.use_cases import PaymentService
from app.domain.errors import (
    IdempotencyKeyReused,
    InvalidState,
    SimulationDisabled,
    ValidationError,
)
from app.domain.payment import DECLINED, SUCCEEDED, UNKNOWN


def test_clave_debe_igualar_reservation(service):
    with pytest.raises(ValidationError):
        service.create_payment(
            idempotency_key="otra-clave",
            reservation_id=uuid.uuid4(),
            amount_cents=100,
            currency="USD",
            method="card",
            token="tok",
        )


def test_misma_clave_cuerpo_distinto_rechaza(service):
    payment, _ = _create(service)
    with pytest.raises(IdempotencyKeyReused):
        service.create_payment(
            idempotency_key=payment.idempotency_key,
            reservation_id=payment.reservation_id,
            amount_cents=99999,
            currency="USD",
            method="card",
            token="tok_demo",
        )


def test_otra_clave_misma_reserva_rechazada_por_unique(repo, service, engine):
    payment, _ = _create(service)
    with pytest.raises(IdempotencyKeyReused):
        repo.insert_initiated(
            reservation_id=payment.reservation_id,
            idempotency_key=str(uuid.uuid4()),
            request_hash="otro",
            amount_cents=30000,
            currency="USD",
            method="card",
        )
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM payments")).scalar_one() == 1


def test_simulacion_deshabilitada_rechaza_sin_estado(repo, provider, engine):
    service = PaymentService(repo, provider, simulation_enabled=False)
    with pytest.raises(SimulationDisabled):
        _create(service, simulate="decline")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM payments")).scalar_one() == 0


def test_refund_desde_declined_invalid_state(service):
    payment, _ = _create(service, simulate="decline")
    assert payment.status == DECLINED
    with pytest.raises(InvalidState):
        service.refund_payment(payment.id)


@pytest.mark.parametrize("sql", ["UPDATE ledger SET amount_cents = 1", "DELETE FROM ledger"])
def test_ledger_append_only(service, engine, sql):
    _create(service)
    with pytest.raises(Exception) as exc:
        with engine.begin() as conn:
            conn.execute(text(sql))
    assert "append-only" in str(exc.value)


def test_i3_un_cobro_por_reserva(service, engine):
    _create(service)
    _create(service, simulate="decline")
    dropped, _ = _create(service, simulate="process_then_drop_response")
    assert dropped.status == UNKNOWN
    service.get_by_reservation(dropped.reservation_id)

    with engine.connect() as conn:
        dupes = conn.execute(
            text(
                "SELECT reservation_id FROM payments " "GROUP BY reservation_id HAVING count(*) > 1"
            )
        ).fetchall()
        assert dupes == []
        missing = conn.execute(
            text(
                "SELECT count(*) FROM payments p WHERE p.status = :ok AND NOT EXISTS ("
                "SELECT 1 FROM ledger l WHERE l.payment_id = p.id AND l.kind = 'CHARGE')"
            ),
            {"ok": SUCCEEDED},
        ).scalar_one()
        assert missing == 0
        extra = conn.execute(
            text(
                "SELECT count(*) FROM (SELECT payment_id FROM ledger "
                "WHERE kind = 'CHARGE' GROUP BY payment_id HAVING count(*) > 1) x"
            )
        ).scalar_one()
        assert extra == 0
