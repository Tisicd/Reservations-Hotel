import dataclasses
import datetime as dt
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fakes import FakeClock, make_service

from app.application.use_cases import CreateReservationCommand
from app.domain.errors import IdempotencyKeyReused
from app.domain.state_machine import CONFIRMED


def _command(clock):
    return CreateReservationCommand(
        customer_id=uuid.uuid4(),
        hotel_id=uuid.uuid4(),
        room_id=uuid.uuid4(),
        check_in=clock.today() + dt.timedelta(days=1),
        check_out=clock.today() + dt.timedelta(days=3),
    )


def _service():
    clock = FakeClock()
    command = _command(clock)
    service, repo, *_rest = make_service(clock=clock, hotel={"hotel_id": command.hotel_id})
    return service, repo, command, clock


def test_misma_clave_y_cuerpo_devuelve_la_misma_reserva():
    service, repo, command, _ = _service()
    first, replayed = service.create_reservation("key-a", command)
    second, replayed_again = service.create_reservation("key-a", command)

    assert replayed is False
    assert replayed_again is True
    assert first.id == second.id
    assert len(repo.rows) == 1


def test_misma_clave_otro_cuerpo_falla():
    service, repo, command, _ = _service()
    service.create_reservation("key-b", command)
    other = dataclasses.replace(command, token="otro_token")

    with pytest.raises(IdempotencyKeyReused):
        service.create_reservation("key-b", other)
    assert len(repo.rows) == 1


def test_concurrente_una_sola_reserva():
    service, repo, command, _ = _service()
    service.saga.sleep = lambda _seconds: None
    ids = []
    errors = []

    def worker(_):
        try:
            reservation, _replayed = service.create_reservation("key-c", command)
            ids.append(reservation.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(worker, range(10)))

    assert errors == []
    assert len(repo.rows) == 1
    assert set(ids) == set(repo.rows)
    assert repo.get_by_idempotency_key("key-c").status == CONFIRMED
