import datetime as dt
import uuid

import pytest
from fakes import FakeClock, make_service

from app.application.use_cases import CreateReservationCommand
from app.domain.errors import (
    CustomerNotFound,
    DependencyUnavailable,
    InvalidState,
    ValidationError,
)
from app.domain.reservation import (
    REASON_CANCEL_TIMEOUT,
    REASON_DECLINED,
    REASON_HOLD_LOST_REFUNDED,
    REASON_TECHNICAL,
)
from app.domain.state_machine import (
    CANCELLED,
    CANCELLING,
    CONFIRMED,
    FAILED_TECHNICAL,
    MANUAL_REVIEW,
    PAID,
    PAYMENT_UNKNOWN,
    RECEIVED,
    REJECTED_NO_INVENTORY,
)


def _cmd(clock: FakeClock, **overrides) -> CreateReservationCommand:
    today = clock.today()
    values = {
        "customer_id": uuid.uuid4(),
        "hotel_id": uuid.uuid4(),
        "room_id": uuid.uuid4(),
        "check_in": today + dt.timedelta(days=1),
        "check_out": today + dt.timedelta(days=4),
        "method": "card",
        "token": "tok_demo",
        "simulate": "ok",
    }
    values.update(overrides)
    return CreateReservationCommand(**values)


def _service(clock=None, **fake_kwargs):
    clock = clock or FakeClock()
    command = _cmd(clock)
    fake_kwargs["hotel"] = {"hotel_id": command.hotel_id, **fake_kwargs.get("hotel", {})}
    service, repo, availability, payment, customer, hotel, clock, crash = make_service(
        clock=clock, **fake_kwargs
    )
    return service, repo, availability, payment, clock, command


def _event_pairs(repo, reservation_id):
    return [
        (e["from_status"], e["to_status"])
        for e in repo.events(reservation_id)
    ]


def test_camino_feliz_confirmado_con_outbox_y_eventos():
    service, repo, availability, payment, _, command = _service()
    reservation, replayed = service.create_reservation("key-1", command)

    assert replayed is False
    assert reservation.status == CONFIRMED
    assert reservation.amount_cents == 30000
    assert reservation.payment_status == "SUCCEEDED"
    assert _event_pairs(repo, reservation.id) == [
        (None, "RECEIVED"),
        ("RECEIVED", "HELD"),
        ("HELD", "PAYMENT_PENDING"),
        ("PAYMENT_PENDING", "PAID"),
        ("PAID", "CONFIRMED"),
    ]
    assert [e["type"] for e in repo.outbox_rows] == ["reservation.confirmed"]
    assert len(availability.created) == 1
    assert len(availability.confirms) == 1
    assert len(payment.charges) == 1


def test_sin_cupo_no_llama_a_payment():
    service, repo, _, payment, _, command = _service(
        availability={"create_behavior": "no_inventory"}
    )
    reservation, _ = service.create_reservation("key-2", command)

    assert reservation.status == REJECTED_NO_INVENTORY
    assert reservation.status_reason == "NO_INVENTORY"
    assert payment.create_calls == []
    assert repo.outbox_rows == []


def test_availability_caida_reintenta_y_luego_failed_technical():
    service, repo, _, _, clock, command = _service(
        availability={"create_behavior": "down"}
    )
    reservation, _ = service.create_reservation("key-3", command)

    assert reservation.status == RECEIVED
    assert reservation.attempts >= 1
    assert reservation.next_attempt_at > clock.now() - dt.timedelta(seconds=5)

    clock.advance(11)
    recovered = service.advance(reservation.id)
    assert recovered.status == FAILED_TECHNICAL
    assert recovered.status_reason == REASON_TECHNICAL


def test_pago_rechazado_libera_hold_y_cancela():
    service, repo, availability, payment, _, command = _service(
        payment={"create_statuses": ["DECLINED"]}
    )
    reservation, _ = service.create_reservation("key-4", command)

    assert reservation.status == CANCELLED
    assert reservation.status_reason == REASON_DECLINED
    assert len(availability.releases) == 1
    assert len(availability.confirms) == 0
    assert [e["type"] for e in repo.outbox_rows] == []
    assert len(payment.charges) == 1


def test_fallo_tecnico_reintenta_con_la_misma_clave_y_luego_cancela():
    service, _, availability, payment, _, command = _service(
        payment={"create_statuses": ["FAILED_TECHNICAL"]}
    )
    reservation, _ = service.create_reservation("key-5", command)

    assert reservation.status == CANCELLED
    assert reservation.status_reason == REASON_TECHNICAL
    assert len(payment.create_calls) == 3
    assert set(payment.create_calls) == {str(reservation.id)}
    assert len(availability.releases) == 1


def test_pago_incierto_se_reconcilia_y_extiende_el_hold():
    service, _, availability, payment, _, command = _service(
        payment={
            "create_statuses": ["RAISE_AMBIGUOUS"],
            "lookup_statuses": ["UNKNOWN", "UNKNOWN", "SUCCEEDED"],
        }
    )
    reservation, _ = service.create_reservation("key-6", command)

    assert reservation.status == CONFIRMED
    assert len(availability.extends) == 3
    assert [ttl for _, ttl in availability.extends] == [600, 600, 600]
    assert len(payment.lookup_calls) == 3


def test_unknown_agotado_pasa_a_manual_review_sin_liberar():
    service, _, availability, _, clock, command = _service(
        payment={"create_statuses": ["UNKNOWN"], "lookup_statuses": ["UNKNOWN"]}
    )
    reservation, _ = service.create_reservation("key-7", command)
    assert reservation.status == PAYMENT_UNKNOWN

    clock.advance(21)
    recovered = service.advance(reservation.id)

    assert recovered.status == MANUAL_REVIEW
    assert availability.releases == []
    assert availability.extends[-1][1] == 86400


def test_paid_con_hold_vencido_reembolsa_y_cancela_una_sola_vez():
    service, _, _, payment, _, command = _service(
        availability={"confirm_behavior": "expired"}
    )
    reservation, _ = service.create_reservation("key-8", command)

    assert reservation.status == CANCELLED
    assert reservation.status_reason == REASON_HOLD_LOST_REFUNDED
    assert len(payment.refunds) == 1

    again = service.advance(reservation.id)
    assert again.status == CANCELLED
    assert len(payment.refunds) == 1


def test_paid_con_availability_caida_termina_en_manual_review_sin_liberar():
    service, _, availability, _, clock, command = _service(
        availability={"confirm_behavior": "down"}
    )
    reservation, _ = service.create_reservation("key-9", command)
    assert reservation.status == PAID

    clock.advance(11)
    recovered = service.advance(reservation.id)

    assert recovered.status == MANUAL_REVIEW
    assert availability.releases == []
    assert availability.confirms == []


def test_cancelacion_confirmada_y_repetida_es_idempotente():
    service, repo, availability, payment, _, command = _service()
    reservation, _ = service.create_reservation("key-10", command)

    cancelled = service.cancel_reservation(reservation.id)
    assert cancelled.status == CANCELLED
    assert len(availability.releases) == 1
    assert len(payment.refunds) == 1
    assert [e["type"] for e in repo.outbox_rows] == [
        "reservation.confirmed",
        "reservation.cancelled",
    ]

    again = service.cancel_reservation(reservation.id)
    assert again.status == CANCELLED
    assert len(availability.releases) == 1
    assert len(payment.refunds) == 1
    assert len(repo.outbox_rows) == 2


def test_cancelacion_que_no_puede_reembolsar_vence_a_manual_review():
    service, repo, availability, payment, clock, command = _service(
        payment={"refund_behavior": "down"}
    )
    reservation, _ = service.create_reservation("key-cancel-timeout", command)
    assert reservation.status == CONFIRMED

    started = service.cancel_reservation(reservation.id)
    assert started.status == CANCELLING
    assert len(availability.releases) == 1

    clock.advance(service.config.cancel_deadline_seconds)
    final = service.advance(reservation.id)

    assert final.status == MANUAL_REVIEW
    assert final.status_reason == REASON_CANCEL_TIMEOUT
    assert len(availability.releases) == 1
    assert payment.refunds == []
    assert [e["type"] for e in repo.outbox_rows] == ["reservation.confirmed"]


def test_cancelar_desde_estado_no_confirmado_es_invalido():
    service, _, _, _, _, command = _service(
        availability={"create_behavior": "down"}
    )
    reservation, _ = service.create_reservation("key-11", command)
    assert reservation.status == RECEIVED

    with pytest.raises(InvalidState):
        service.cancel_reservation(reservation.id)


def test_lease_impide_doble_procesamiento_y_permite_relevo():
    service, repo, _, _, clock, command = _service(
        availability={"create_behavior": "down"}
    )
    reservation, _ = service.create_reservation("key-12", command)

    clock.advance(20)
    assert repo.claim(reservation.id, 15) is not None
    assert repo.claim(reservation.id, 15) is None
    clock.advance(16)
    assert repo.claim(reservation.id, 15) is not None


def test_validacion_sin_registro():
    clock = FakeClock()
    command = _cmd(clock)

    service, repo, *_ = _service(clock=clock, customer={"found": False})
    with pytest.raises(CustomerNotFound):
        service.create_reservation("key-13", command)
    assert repo.rows == {}

    service, repo, *_ = _service(clock=clock, customer={"behavior": "down"})
    with pytest.raises(DependencyUnavailable):
        service.create_reservation("key-14", command)
    assert repo.rows == {}

    service, repo, *_ = _service(clock=clock, hotel={"hotel_id": uuid.uuid4()})
    with pytest.raises(ValidationError):
        service.create_reservation("key-15", command)
    assert repo.rows == {}

    service, repo, *_ = _service(clock=clock)
    past = _cmd(
        clock,
        check_in=clock.today() - dt.timedelta(days=1),
        check_out=clock.today() + dt.timedelta(days=1),
    )
    with pytest.raises(ValidationError):
        service.create_reservation("key-16", past)
    assert repo.rows == {}

    too_long = _cmd(
        clock,
        check_in=clock.today() + dt.timedelta(days=1),
        check_out=clock.today() + dt.timedelta(days=40),
    )
    with pytest.raises(ValidationError):
        service.create_reservation("key-17", too_long)
    assert repo.rows == {}
