import uuid

from sqlalchemy import text

from app.domain.payment import DECLINED, FAILED_TECHNICAL, REFUNDED, SUCCEEDED, UNKNOWN


def _create(service, simulate="ok"):
    reservation = uuid.uuid4()
    payment, created = service.create_payment(
        idempotency_key=str(reservation),
        reservation_id=reservation,
        amount_cents=30000,
        currency="USD",
        method="card",
        token="tok_demo",
        simulate=simulate,
    )
    return payment, created


def _count(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_ok_succeeded_un_cargo_y_un_asiento(service, engine):
    payment, created = _create(service)
    assert created is True
    assert payment.status == SUCCEEDED
    assert _count(engine, "sim_provider_charges") == 1
    assert _count(engine, "ledger") == 1
    assert _count(engine, "payment_attempts") == 1


def test_decline_terminal_sin_nuevo_cargo(service, engine):
    payment, _ = _create(service, simulate="decline")
    assert payment.status == DECLINED

    again, created = service.create_payment(
        idempotency_key=payment.idempotency_key,
        reservation_id=payment.reservation_id,
        amount_cents=30000,
        currency="USD",
        method="card",
        token="tok_demo",
        simulate="decline",
    )
    assert again.status == DECLINED
    assert created is False
    assert _count(engine, "sim_provider_charges") == 1


def test_error_before_processing_no_cobra_y_reintenta(service, engine):
    payment, _ = _create(service, simulate="error_before_processing")
    assert payment.status == FAILED_TECHNICAL
    assert _count(engine, "sim_provider_charges") == 0

    retried, created = service.create_payment(
        idempotency_key=payment.idempotency_key,
        reservation_id=payment.reservation_id,
        amount_cents=30000,
        currency="USD",
        method="card",
        token="tok_demo",
        simulate="ok",
    )
    assert created is False
    assert retried.status == SUCCEEDED
    assert _count(engine, "sim_provider_charges") == 1
    assert _count(engine, "ledger") == 1


def test_process_then_drop_unknown_y_reconcilia_por_reserva(service, engine):
    payment, _ = _create(service, simulate="process_then_drop_response")
    assert payment.status == UNKNOWN
    assert _count(engine, "sim_provider_charges") == 1

    resolved = service.get_by_reservation(payment.reservation_id)
    assert resolved.status == SUCCEEDED
    assert _count(engine, "ledger") == 1
    assert _count(engine, "sim_provider_charges") == 1


def test_slow_unknown_y_worker_reconcilia_sin_http(service, engine):
    payment, _ = _create(service, simulate="slow")
    assert payment.status == UNKNOWN

    assert service.reconcile_unknown(limit=10) == 1
    assert service.get_payment(payment.id).status == SUCCEEDED
    assert _count(engine, "ledger") == 1


def test_refund_flujo_completo(service, engine):
    payment, _ = _create(service)
    refunded = service.refund_payment(payment.id)
    assert refunded.status == REFUNDED
    with engine.connect() as conn:
        kinds = conn.execute(text("SELECT kind FROM ledger ORDER BY kind")).scalars().all()
    assert kinds.count("CHARGE") == 1
    assert kinds.count("REFUND") == 1

    again = service.refund_payment(payment.id)
    assert again.status == REFUNDED
    with engine.connect() as conn:
        refunds = conn.execute(
            text("SELECT count(*) FROM ledger WHERE kind = 'REFUND'")
        ).scalar_one()
    assert refunds == 1
