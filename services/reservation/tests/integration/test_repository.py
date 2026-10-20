import datetime as dt
import threading
import uuid

import pytest
from sqlalchemy import text

from app.domain.errors import ConcurrentModification
from app.domain.reservation import Reservation
from app.domain.state_machine import (
    CONFIRMED,
    HELD,
    PAID,
    PAYMENT_PENDING,
    RECEIVED,
    REJECTED_NO_INVENTORY,
)
from app.infrastructure.db import repository as repo_module


def _received(key: str | None = None) -> Reservation:
    now = dt.datetime.now(dt.UTC)
    return Reservation(
        id=uuid.uuid4(),
        idempotency_key=key or uuid.uuid4().hex,
        request_hash="hash",
        customer_id=uuid.uuid4(),
        hotel_id=uuid.uuid4(),
        room_id=uuid.uuid4(),
        check_in=now.date() + dt.timedelta(days=1),
        check_out=now.date() + dt.timedelta(days=4),
        nights=3,
        amount_cents=30000,
        currency="USD",
        payment_method="card",
        payment_token="tok_demo",
        payment_simulate="ok",
        status=RECEIVED,
        attempts=0,
        next_attempt_at=now,
        phase_started_at=now,
        version=0,
        created_at=now,
        updated_at=now,
    )


def _create(repo, key=None):
    stored, created = repo.create_received(_received(key))
    assert created
    return stored


def _count(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_transicion_es_atomica(repo, engine, monkeypatch):
    reservation = _create(repo)

    def boom(*args, **kwargs):
        raise RuntimeError("fallo inyectado tras el evento")

    monkeypatch.setattr(repo_module, "_insert_outbox", boom)
    with pytest.raises(RuntimeError):
        repo.transition(
            reservation,
            REJECTED_NO_INVENTORY,
            "NO_INVENTORY",
            {},
            {"type": "reservation.confirmed", "payload": {}},
        )

    row = repo.get(reservation.id)
    assert row.status == RECEIVED
    assert row.version == 0
    assert len(repo.events(reservation.id)) == 1
    assert _count(engine, "outbox") == 0


def test_cas_gana_una_sola_transicion(repo):
    reservation = _create(repo)
    barrier = threading.Barrier(2)
    results = []

    def worker():
        barrier.wait()
        try:
            results.append(repo.transition(reservation, HELD, None, {}))
        except ConcurrentModification:
            results.append("conflict")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    statuses = [r.status if isinstance(r, Reservation) else r for r in results]
    assert sorted(statuses) == sorted(["conflict", HELD])
    assert repo.get(reservation.id).status == HELD
    assert len(repo.events(reservation.id)) == 2


def test_claim_due_no_procesa_dos_veces(repo):
    ids = {_create(repo).id for _ in range(10)}
    barrier = threading.Barrier(2)
    claimed = []
    lock = threading.Lock()

    def worker():
        barrier.wait()
        while True:
            rows = repo.claim_due(3, 15)
            if not rows:
                return
            with lock:
                claimed.extend(r.id for r in rows)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(claimed) == sorted(ids)
    assert len(claimed) == len(set(claimed))


def test_veinte_hilos_misma_clave_una_fila(repo, engine):
    reservation = _received("misma-clave")
    results = []
    barrier = threading.Barrier(20)

    def worker():
        barrier.wait()
        results.append(repo.create_received(reservation)[1])

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(True) == 1
    assert results.count(False) == 19
    assert _count(engine, "reservations") == 1
    assert _count(engine, "reservation_events") == 1


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE reservation_events SET reason = 'x'",
        "DELETE FROM reservation_events",
    ],
)
def test_eventos_append_only(repo, engine, sql):
    reservation = _create(repo)
    with pytest.raises(Exception) as exc:
        with engine.begin() as conn:
            conn.execute(text(sql))
    assert "append-only" in str(exc.value)
    assert len(repo.events(reservation.id)) == 1


def test_confirmado_y_outbox_juntos(repo, engine, monkeypatch):
    reservation = _create(repo)
    paid = repo.transition_chain(reservation, [HELD, PAYMENT_PENDING, PAID], None, {})
    event = {"type": "reservation.confirmed", "payload": {"reservation_id": str(paid.id)}}

    confirmed = repo.transition(paid, CONFIRMED, None, {}, event)
    assert confirmed.status == CONFIRMED
    assert _count(engine, "outbox") == 1

    other = _create(repo)
    other_paid = repo.transition_chain(other, [HELD, PAYMENT_PENDING, PAID], None, {})

    def boom(*args, **kwargs):
        raise RuntimeError("fallo inyectado tras el evento")

    monkeypatch.setattr(repo_module, "_insert_outbox", boom)
    with pytest.raises(RuntimeError):
        repo.transition(other_paid, CONFIRMED, None, {}, event)

    assert repo.get(other.id).status == PAID
    assert _count(engine, "outbox") == 1
