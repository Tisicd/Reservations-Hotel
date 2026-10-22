import uuid

import pytest
import sqlalchemy as sa

from tests.invariants.checker import (
    assert_no_loss,
    check_availability,
    check_cross,
    check_outbox_backlog_old,
    check_payment,
    check_reservation,
    open_connections,
)

TRUNCATE = {
    "availability_db": "TRUNCATE inventory, holds",
    "reservation_db": "TRUNCATE reservation_events, outbox, reservations",
    "payment_db": "TRUNCATE ledger, payment_attempts, payments",
    "notification_db": "TRUNCATE notifications",
}

TYPE_CREATED = uuid.UUID("6b4a1e0e-0000-4000-8000-000000000001")
TYPE_CREATED_2 = uuid.UUID("6b4a1e0e-0000-4000-8000-000000000002")
TYPE_CREATED_3 = uuid.UUID("6b4a1e0e-0000-4000-8000-000000000003")
ROOM_ID = uuid.UUID("6b4a1e0e-0000-4000-8000-000000000010")
HOTEL_ID = uuid.UUID("6b4a1e0e-0000-4000-8000-000000000011")


@pytest.fixture()
def conns():
    test_conns, engines = open_connections(read_only=False)
    for db, conn in test_conns.items():
        conn.commit()
        conn.execute(sa.text(TRUNCATE[db]))
        conn.commit()
    transactions = {db: conn.begin() for db, conn in test_conns.items()}
    yield test_conns
    for transaction in transactions.values():
        transaction.rollback()
    for conn in test_conns.values():
        conn.close()
    for engine in engines:
        engine.dispose()


def _codes(violations):
    return {violation.code for violation in violations}


def _all(conns, grace_seconds=60):
    return (
        check_availability(conns["availability_db"])
        + check_reservation(conns["reservation_db"], grace_seconds)
        + check_payment(conns["payment_db"])
        + check_cross(conns, grace_seconds)
    )


def _reservation(conn, reservation_id, status, phase="now()"):
    conn.execute(
        sa.text(
            """
            INSERT INTO reservations (
                id, idempotency_key, request_hash, customer_id, hotel_id, room_id,
                check_in, check_out, nights, amount_cents, currency, payment_method,
                payment_token, payment_simulate, status, phase_started_at
            ) VALUES (
                :id, :key, 'hash', gen_random_uuid(), :hotel, :room,
                current_date, current_date + 1, 1, 1000, 'USD', 'card',
                'tok', 'ok', :status, """
            + phase
            + """
            )
            """
        ),
        {
            "id": reservation_id,
            "key": f"key-{reservation_id}",
            "hotel": HOTEL_ID,
            "room": ROOM_ID,
            "status": status,
        },
    )


def _event(conn, reservation_id, from_status, to_status):
    conn.execute(
        sa.text(
            "INSERT INTO reservation_events (reservation_id, from_status, to_status) "
            "VALUES (:id, :from_status, :to_status)"
        ),
        {"id": reservation_id, "from_status": from_status, "to_status": to_status},
    )


def _chain(conn, reservation_id, statuses):
    previous = None
    for status in statuses:
        _event(conn, reservation_id, previous, status)
        previous = status


def _payment(conn, reservation_id, status, charge=False, refund=False, payment_id=None):
    payment_id = payment_id or uuid.uuid4()
    conn.execute(
        sa.text(
            """
            INSERT INTO payments (
                id, reservation_id, idempotency_key, request_hash, amount_cents,
                currency, method, status
            ) VALUES (:id, :reservation, :key, 'hash', 1000, 'USD', 'card', :status)
            """
        ),
        {
            "id": payment_id,
            "reservation": reservation_id,
            "key": f"pay-{payment_id}",
            "status": status,
        },
    )
    if charge:
        conn.execute(
            sa.text(
                "INSERT INTO ledger (id, payment_id, kind, amount_cents, currency) "
                "VALUES (gen_random_uuid(), :payment, 'CHARGE', 1000, 'USD')"
            ),
            {"payment": payment_id},
        )
    if refund:
        conn.execute(
            sa.text(
                "INSERT INTO ledger (id, payment_id, kind, amount_cents, currency) "
                "VALUES (gen_random_uuid(), :payment, 'REFUND', 1000, 'USD')"
            ),
            {"payment": payment_id},
        )
    return payment_id


def _hold(conn, hold_id, status, expires="now() + interval '10 minutes'"):
    conn.execute(
        sa.text(
            f"""
            INSERT INTO holds (hold_id, room_id, check_in, check_out, units, status, expires_at)
            VALUES (
                :id, :room, current_date, current_date + 1, 1, :status,
                {expires}
            )
            """
        ),
        {"id": hold_id, "room": ROOM_ID, "status": status},
    )


def _inventory(conn, total, held, confirmed):
    conn.execute(
        sa.text(
            "INSERT INTO inventory (room_id, hotel_id, night, total, held, confirmed) "
            "VALUES (:room, :hotel, current_date, :total, :held, :confirmed)"
        ),
        {
            "room": ROOM_ID,
            "hotel": HOTEL_ID,
            "total": total,
            "held": held,
            "confirmed": confirmed,
        },
    )


def _outbox(conn, reservation_id, event_type):
    conn.execute(
        sa.text(
            """
            INSERT INTO outbox (id, aggregate_id, type, payload, status, next_attempt_at)
            VALUES (gen_random_uuid(), :id, :type, '{}'::jsonb, 'PENDING', now())
            """
        ),
        {"id": reservation_id, "type": event_type},
    )


def test_bd_limpia_sin_violaciones(conns):
    assert _all(conns) == []


def test_escenario_valido_sin_violaciones(conns):
    confirmed = TYPE_CREATED
    _reservation(conns["reservation_db"], confirmed, "CONFIRMED")
    _chain(
        conns["reservation_db"],
        confirmed,
        ["RECEIVED", "HELD", "PAYMENT_PENDING", "PAID", "CONFIRMED"],
    )
    _outbox(conns["reservation_db"], confirmed, "reservation.confirmed")
    _payment(conns["payment_db"], confirmed, "SUCCEEDED", charge=True)
    _hold(conns["availability_db"], confirmed, "CONFIRMED")
    _inventory(conns["availability_db"], 5, 0, 1)

    declined = TYPE_CREATED_2
    _reservation(conns["reservation_db"], declined, "CANCELLED")
    _chain(
        conns["reservation_db"],
        declined,
        ["RECEIVED", "HELD", "PAYMENT_PENDING", "PAYMENT_DECLINED", "CANCELLED"],
    )
    _payment(conns["payment_db"], declined, "DECLINED")
    _hold(conns["availability_db"], declined, "RELEASED")

    refunded = TYPE_CREATED_3
    _reservation(conns["reservation_db"], refunded, "CANCELLED")
    _chain(
        conns["reservation_db"],
        refunded,
        ["RECEIVED", "HELD", "PAYMENT_PENDING", "PAID", "CONFIRMED", "CANCELLING", "CANCELLED"],
    )
    _outbox(conns["reservation_db"], refunded, "reservation.confirmed")
    _outbox(conns["reservation_db"], refunded, "reservation.cancelled")
    _payment(conns["payment_db"], refunded, "REFUNDED", charge=True, refund=True)
    _hold(conns["availability_db"], refunded, "RELEASED")

    assert _all(conns) == []


def test_oversell(conns):
    conns["availability_db"].execute(sa.text("ALTER TABLE inventory DROP CONSTRAINT inventory_check"))
    _inventory(conns["availability_db"], 1, 1, 1)
    assert "OVERSELL" in _codes(check_availability(conns["availability_db"]))


def test_inventory_drift(conns):
    _inventory(conns["availability_db"], 5, 1, 0)
    assert "INVENTORY_DRIFT" in _codes(check_availability(conns["availability_db"]))


def test_event_chain_broken(conns):
    _reservation(conns["reservation_db"], TYPE_CREATED, "PAID")
    _chain(conns["reservation_db"], TYPE_CREATED, ["RECEIVED", "PAID"])
    assert "EVENT_CHAIN_BROKEN" in _codes(
        check_reservation(conns["reservation_db"])
    )


def test_double_charge(conns):
    conns["payment_db"].execute(
        sa.text("ALTER TABLE ledger DROP CONSTRAINT ledger_payment_id_kind_key")
    )
    payment_id = _payment(conns["payment_db"], TYPE_CREATED, "SUCCEEDED", charge=True)
    conns["payment_db"].execute(
        sa.text(
            "INSERT INTO ledger (id, payment_id, kind, amount_cents, currency) "
            "VALUES (gen_random_uuid(), :payment, 'CHARGE', 1000, 'USD')"
        ),
        {"payment": payment_id},
    )
    assert "DOUBLE_CHARGE" in _codes(check_payment(conns["payment_db"]))


@pytest.mark.parametrize("scenario", ["succeeded_sin_charge", "charge_sin_succeeded", "refunded_sin_refund"])
def test_ledger_mismatch(conns, scenario):
    if scenario == "succeeded_sin_charge":
        _payment(conns["payment_db"], TYPE_CREATED, "SUCCEEDED")
    elif scenario == "charge_sin_succeeded":
        _payment(conns["payment_db"], TYPE_CREATED, "INITIATED", charge=True)
    else:
        _payment(conns["payment_db"], TYPE_CREATED, "REFUNDED", charge=True)
    assert "LEDGER_MISMATCH" in _codes(check_payment(conns["payment_db"]))


def test_confirmed_without_payment(conns):
    _reservation(conns["reservation_db"], TYPE_CREATED, "CONFIRMED")
    assert "CONFIRMED_WITHOUT_PAYMENT" in _codes(check_cross(conns))


def test_paid_without_service(conns):
    _reservation(conns["reservation_db"], TYPE_CREATED, "FAILED_TECHNICAL")
    _payment(conns["payment_db"], TYPE_CREATED, "SUCCEEDED", charge=True)
    assert "PAID_WITHOUT_SERVICE" in _codes(check_cross(conns))


def test_stuck_reservation(conns):
    _reservation(
        conns["reservation_db"],
        TYPE_CREATED,
        "PAYMENT_PENDING",
        phase="now() - interval '1 hour'",
    )
    assert "STUCK_RESERVATION" in _codes(check_reservation(conns["reservation_db"], 60))


def test_leaked_hold(conns):
    _hold(conns["availability_db"], TYPE_CREATED, "HELD", "now() - interval '1 hour'")
    assert "LEAKED_HOLD" in _codes(check_cross(conns))


def test_expiry_lag(conns):
    _reservation(conns["reservation_db"], TYPE_CREATED, "PAYMENT_PENDING")
    _hold(conns["availability_db"], TYPE_CREATED, "HELD", "now() - interval '1 hour'")
    assert "EXPIRY_LAG" in _codes(check_cross(conns))


def test_missing_outbox(conns):
    _reservation(conns["reservation_db"], TYPE_CREATED, "CONFIRMED")
    _chain(
        conns["reservation_db"],
        TYPE_CREATED,
        ["RECEIVED", "HELD", "PAYMENT_PENDING", "PAID", "CONFIRMED"],
    )
    assert "MISSING_OUTBOX" in _codes(check_reservation(conns["reservation_db"]))


def test_duplicate_outbox(conns):
    _reservation(conns["reservation_db"], TYPE_CREATED, "CONFIRMED")
    _chain(
        conns["reservation_db"],
        TYPE_CREATED,
        ["RECEIVED", "HELD", "PAYMENT_PENDING", "PAID", "CONFIRMED"],
    )
    _outbox(conns["reservation_db"], TYPE_CREATED, "reservation.confirmed")
    _outbox(conns["reservation_db"], TYPE_CREATED, "reservation.confirmed")
    assert "DUPLICATE_OUTBOX" in _codes(check_reservation(conns["reservation_db"]))


def test_assert_no_loss():
    before = {"reservations": 3, "events": 10}
    assert_no_loss(before, {"reservations": 3, "events": 11})
    with pytest.raises(AssertionError):
        assert_no_loss(before, {"reservations": 2, "events": 10})


def test_outbox_backlog_old(conns):
    conn = conns["notification_db"]
    conn.execute(
        sa.text(
            "INSERT INTO notifications (id, event_id, type, reservation_id, "
            "customer_id, payload, status, created_at) VALUES "
            "(gen_random_uuid(), gen_random_uuid(), 'reservation.confirmed', "
            "gen_random_uuid(), gen_random_uuid(), '{}'::jsonb, 'PENDING', "
            "now() - interval '10 minutes')"
        )
    )
    codes = {violation.code for violation in check_outbox_backlog_old(conn)}
    assert "OUTBOX_BACKLOG_OLD" in codes

