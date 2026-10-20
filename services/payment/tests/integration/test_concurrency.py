import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text

from app.application.use_cases import PaymentService
from app.infrastructure.db.repository import SqlPaymentRepository
from app.infrastructure.provider_sim import SimulatedProvider


@pytest.mark.parametrize("iteration", range(20))
def test_concurrencia_i3_una_fila_un_cargo_un_asiento(engine, db_url_fixture, iteration):
    reservation = uuid.uuid4()
    key = str(reservation)

    big = create_engine(db_url_fixture, pool_size=50)
    service = PaymentService(
        SqlPaymentRepository(big),
        SimulatedProvider(big, timeout_seconds=3, slow_seconds=1),
        simulation_enabled=True,
    )
    results = []

    def worker(_):
        try:
            payment, created = service.create_payment(
                idempotency_key=key,
                reservation_id=reservation,
                amount_cents=30000,
                currency="USD",
                method="card",
                token="tok_demo",
            )
            results.append((payment.status, created))
        except Exception as e:  # noqa: BLE001
            results.append(("ERROR", repr(e)))

    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(worker, range(10)))
    big.dispose()

    assert all(status == "SUCCEEDED" for status, _ in results), results
    assert sum(1 for _, created in results if created) == 1

    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM payments WHERE reservation_id = :r"),
                {"r": reservation},
            ).scalar_one()
            == 1
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM sim_provider_charges WHERE idempotency_key = :k"),
                {"k": key},
            ).scalar_one()
            == 1
        )
        payment_id = conn.execute(
            text("SELECT id FROM payments WHERE reservation_id = :r"), {"r": reservation}
        ).scalar_one()
        assert (
            conn.execute(
                text("SELECT count(*) FROM ledger WHERE payment_id = :p AND kind = 'CHARGE'"),
                {"p": payment_id},
            ).scalar_one()
            == 1
        )
