import uuid

import pytest
from fakes import FakeProvider, FakeRepo

from app.application.ports import DECLINED as PROVIDER_DECLINED
from app.application.use_cases import PaymentService
from app.domain.errors import (
    IdempotencyKeyReused,
    InvalidState,
    SimulationDisabled,
    ValidationError,
)
from app.domain.payment import (
    DECLINED,
    FAILED_TECHNICAL,
    INITIATED,
    REFUNDED,
    SUCCEEDED,
    UNKNOWN,
)


def _service(provider=None, simulation_enabled=True):
    repo = FakeRepo()
    provider = provider or FakeProvider()
    return PaymentService(repo, provider, simulation_enabled=simulation_enabled), repo, provider


def _create(service, simulate="ok", key=None, amount=30000, token="tok_demo"):
    reservation = uuid.uuid4()
    return service.create_payment(
        idempotency_key=key or str(reservation),
        reservation_id=reservation,
        amount_cents=amount,
        currency="USD",
        method="card",
        token=token,
        simulate=simulate,
    )


def test_ok_crea_pago_y_asiento():
    service, repo, provider = _service()
    payment, created = _create(service)
    assert created is True
    assert payment.status == SUCCEEDED
    assert payment.provider_ref.startswith("sim_")
    assert len(repo.ledger) == 1
    assert len(provider.charges) == 1


def test_decline_es_terminal_y_no_reintenta():
    service, repo, provider = _service(FakeProvider(outcome=PROVIDER_DECLINED))
    payment, _ = _create(service, simulate="decline")
    assert payment.status == DECLINED
    again, created = service.create_payment(
        idempotency_key=payment.idempotency_key,
        reservation_id=payment.reservation_id,
        amount_cents=30000,
        currency="USD",
        method="card",
        token="tok_demo",
    )
    assert again.status == DECLINED
    assert created is False
    assert len(provider.calls) == 1
    assert repo.ledger == []


def test_error_before_processing_es_failed_technical_y_reintenta():
    service, repo, provider = _service()
    payment, _ = _create(service, simulate="error_before_processing")
    assert payment.status == FAILED_TECHNICAL
    assert provider.charges == {}

    again, created = service.create_payment(
        idempotency_key=payment.idempotency_key,
        reservation_id=payment.reservation_id,
        amount_cents=30000,
        currency="USD",
        method="card",
        token="tok_demo",
        simulate="ok",
    )
    assert created is False
    assert again.status == SUCCEEDED
    assert len(provider.charges) == 1
    assert len(repo.ledger) == 1


def test_process_then_drop_queda_unknown_y_reconcilia():
    service, repo, provider = _service()
    payment, _ = _create(service, simulate="process_then_drop_response")
    assert payment.status == UNKNOWN
    assert len(provider.charges) == 1

    resolved = service.get_by_reservation(payment.reservation_id)
    assert resolved.status == SUCCEEDED
    assert len(repo.ledger) == 1


def test_slow_queda_unknown_y_worker_reconcilia():
    service, repo, provider = _service()
    payment, _ = _create(service, simulate="slow")
    assert payment.status == UNKNOWN

    count = service.reconcile_unknown(limit=10)
    assert count == 1
    assert repo.get(payment.id).status == SUCCEEDED


def test_crash_entre_cobro_y_persistencia_reintenta_sin_doble_asiento():
    provider = FakeProvider(raise_after=RuntimeError("caÃ­da simulada"))
    service, repo, _ = _service(provider)
    reservation = uuid.uuid4()
    with pytest.raises(RuntimeError):
        service.create_payment(
            idempotency_key=str(reservation),
            reservation_id=reservation,
            amount_cents=30000,
            currency="USD",
            method="card",
            token="tok_demo",
        )

    payment = service.get_by_reservation(reservation)
    assert payment.status == INITIATED
    assert repo.ledger == []

    retried = service.create_payment(
        idempotency_key=str(reservation),
        reservation_id=reservation,
        amount_cents=30000,
        currency="USD",
        method="card",
        token="tok_demo",
    )
    assert retried[0].status == SUCCEEDED
    assert retried[1] is False
    assert len(repo.ledger) == 1
    assert len(provider.charges) == 1


def test_replay_succeeded_devuelve_el_mismo_pago():
    service, repo, provider = _service()
    payment, _ = _create(service)
    again, created = service.create_payment(
        idempotency_key=payment.idempotency_key,
        reservation_id=payment.reservation_id,
        amount_cents=30000,
        currency="USD",
        method="card",
        token="tok_demo",
    )
    assert created is False
    assert again.id == payment.id
    assert len(provider.calls) == 1


def test_misma_clave_otro_cuerpo_rechaza():
    service, _, _ = _service()
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


def test_clave_distinta_de_reservation_rechaza():
    service, _, _ = _service()
    with pytest.raises(ValidationError):
        service.create_payment(
            idempotency_key="otra",
            reservation_id=uuid.uuid4(),
            amount_cents=100,
            currency="USD",
            method="card",
            token="t",
        )


def test_simulacion_deshabilitada_rechaza():
    service, _, _ = _service(simulation_enabled=False)
    with pytest.raises(SimulationDisabled):
        _create(service, simulate="decline")


def test_refund_idempotente_y_solo_desde_succeeded():
    service, repo, provider = _service()
    payment, _ = _create(service)
    refunded = service.refund_payment(payment.id)
    assert refunded.status == REFUNDED
    assert provider.refunded == {payment.idempotency_key}
    assert [x["kind"] for x in repo.ledger].count("REFUND") == 1

    again = service.refund_payment(payment.id)
    assert again.status == REFUNDED
    assert [x["kind"] for x in repo.ledger].count("REFUND") == 1

    declined_service, _, declined_provider = _service(FakeProvider(outcome=PROVIDER_DECLINED))
    declined, _ = _create(declined_service, simulate="decline")
    with pytest.raises(InvalidState):
        declined_service.refund_payment(declined.id)
