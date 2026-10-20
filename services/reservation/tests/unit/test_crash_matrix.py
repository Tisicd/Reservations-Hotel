import datetime as dt
import uuid

import pytest
from fakes import (
    CrashPlan,
    FakeAvailability,
    FakeClock,
    FakeCustomer,
    FakeHotel,
    FakePayment,
    FakeRepo,
    SimulatedCrash,
    clock_sleep,
)

from app.application.advance import SagaConfig
from app.application.use_cases import CreateReservationCommand, ReservationService
from app.domain.state_machine import CANCELLED, CONFIRMED, is_stable

CONFIG = SagaConfig(
    saga_sync_wait_seconds=5,
    hold_ttl_seconds=600,
    saga_hold_deadline_seconds=10,
    payment_max_technical_retries=3,
    payment_reconcile_deadline_seconds=20,
    confirm_deadline_seconds=10,
    cancel_deadline_seconds=10,
    manual_review_hold_ttl_seconds=86400,
    backoff_base_seconds=0.5,
    backoff_max_seconds=2,
    lease_seconds=2,
)

EXPECTED = {
    "happy": {"status": CONFIRMED, "holds": 1, "charges": 1, "confirms": 1, "outbox": 1},
    "decline": {
        "status": CANCELLED,
        "holds": 1,
        "charges": 1,
        "confirms": 0,
        "releases": 1,
        "outbox": 0,
    },
    "unknown": {"status": CONFIRMED, "holds": 1, "charges": 1, "confirms": 1, "outbox": 1},
    "cancel": {
        "status": CANCELLED,
        "holds": 1,
        "charges": 1,
        "confirms": 1,
        "releases": 1,
        "refunds": 1,
        "outbox": 2,
    },
}


def _scenario(kind: str, target: int | None):
    clock = FakeClock()
    crash = CrashPlan(None)
    repo = FakeRepo(clock, crash)
    availability = FakeAvailability(clock, crash)
    if kind == "decline":
        payment = FakePayment(clock, crash, create_statuses=["DECLINED"])
    elif kind == "unknown":
        payment = FakePayment(
            clock,
            crash,
            create_statuses=["UNKNOWN"],
            lookup_statuses=["UNKNOWN", "SUCCEEDED"],
        )
    else:
        payment = FakePayment(clock, crash)
    customer = FakeCustomer(clock, crash)
    hotel_id = uuid.uuid4()
    hotel = FakeHotel(clock, crash, hotel_id=hotel_id)
    command = CreateReservationCommand(
        customer_id=uuid.uuid4(),
        hotel_id=hotel_id,
        room_id=uuid.uuid4(),
        check_in=clock.today() + dt.timedelta(days=1),
        check_out=clock.today() + dt.timedelta(days=4),
    )
    service = ReservationService(
        repo,
        availability,
        payment,
        customer,
        hotel,
        clock,
        CONFIG,
        jitter=lambda: 1.0,
        sleep=clock_sleep(clock),
    )
    key = f"crash-{kind}"

    crashed = False
    if kind == "cancel":
        service.create_reservation(key, command)
        crash.reset(target)
        try:
            service.cancel_reservation(repo.get_by_idempotency_key(key).id)
        except SimulatedCrash:
            crashed = True
    else:
        crash.target = target
        try:
            service.create_reservation(key, command)
        except SimulatedCrash:
            crashed = True
    if target is not None:
        assert crashed, f"no se inyectó la caída en el punto {target}"

    crash.disarm()
    recovery = ReservationService(
        repo,
        availability,
        payment,
        customer,
        hotel,
        clock,
        CONFIG,
        jitter=lambda: 1.0,
        sleep=clock_sleep(clock),
    )
    existing = repo.get_by_idempotency_key(key)
    if kind == "cancel":
        recovery.cancel_reservation(existing.id)
        for _ in range(1500):
            if is_stable(repo.get(existing.id).status):
                break
            recovery.recover_due(20)
            clock.advance(1)
        else:
            raise AssertionError(f"{kind}: no alcanzó un estado estable")
    elif existing is None:
        recovery.create_reservation(key, command)
    else:
        for _ in range(1500):
            if is_stable(repo.get(existing.id).status):
                break
            recovery.recover_due(20)
            clock.advance(1)
        else:
            raise AssertionError(f"{kind}: no alcanzó un estado estable")

    reservation = repo.get_by_idempotency_key(key)
    return reservation, crash, repo, availability, payment


def _fingerprint(reservation, repo, availability, payment):
    return {
        "status": reservation.status,
        "reason": reservation.status_reason,
        "payment_status": reservation.payment_status,
        "events": [
            (e["from_status"], e["to_status"], e["reason"]) for e in repo.event_rows
        ],
        "outbox": [o["type"] for o in repo.outbox_rows],
        "holds": len(availability.created),
        "confirms": len(availability.confirms),
        "releases": len(availability.releases),
        "charges": len(payment.charges),
        "refunds": len(payment.refunds),
    }


@pytest.mark.parametrize("kind", ["happy", "decline", "unknown", "cancel"])
def test_matriz_de_caidas(kind):
    reservation, plan, repo, availability, payment = _scenario(kind, None)
    base = _fingerprint(reservation, repo, availability, payment)
    expected = EXPECTED[kind]

    assert base["status"] == expected["status"]
    assert base["holds"] == expected["holds"]
    assert base["charges"] == expected["charges"]
    assert base["confirms"] == expected["confirms"]
    assert base["releases"] == expected.get("releases", 0)
    assert base["refunds"] == expected.get("refunds", 0)
    assert len(base["outbox"]) == expected["outbox"]

    assert plan.ops, "la matriz no registró puntos de caída"

    for target in range(1, len(plan.ops) + 1):
        reservation, _, repo, availability, payment = _scenario(kind, target)
        result = _fingerprint(reservation, repo, availability, payment)
        assert result == base, (
            f"{kind}: divergió tras la caída en '{plan.ops[target - 1]}' (punto {target})"
        )
