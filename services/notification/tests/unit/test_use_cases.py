import uuid

import pytest
from fakes import FakeRepo, FlakyChannel

from app.application.use_cases import NotificationService
from app.domain.errors import ValidationError

EVENT = uuid.uuid4()
RESERVATION = uuid.uuid4()
CUSTOMER = uuid.uuid4()


def _service(channel=None, **kwargs):
    repo = FakeRepo()
    return NotificationService(repo, channel or FlakyChannel(0), **kwargs), repo


def test_evento_repetido_no_crea_otra_notificacion():
    service, repo = _service()
    first, created = service.create(EVENT, "reservation.confirmed", RESERVATION, CUSTOMER)
    second, created_again = service.create(
        EVENT, "reservation.confirmed", RESERVATION, CUSTOMER
    )

    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert len(repo.items) == 1


def test_tipo_desconocido_es_validacion():
    service, _ = _service()
    with pytest.raises(ValidationError):
        service.create(EVENT, "reservation.refunded", RESERVATION, CUSTOMER)


def test_entrega_marca_enviada():
    service, repo = _service()
    service.create(EVENT, "reservation.confirmed", RESERVATION, CUSTOMER)

    assert service.deliver_due(10) == 1
    assert repo.items[0].status == "SENT"
    assert repo.sent == [repo.items[0].id]


def test_fallo_programa_reintento_y_agota():
    service, repo = _service(FlakyChannel(99), max_attempts=2)
    service.create(EVENT, "reservation.confirmed", RESERVATION, CUSTOMER)

    assert service.deliver_due(10) == 0
    assert repo.items[0].status == "PENDING"
    assert repo.items[0].attempts == 1

    assert service.deliver_due(10) == 0
    assert repo.items[0].status == "FAILED"
    assert repo.items[0].last_error == "canal caído"


def test_reintento_posterior_entrega():
    channel = FlakyChannel(1)
    service, repo = _service(channel)
    service.create(EVENT, "reservation.confirmed", RESERVATION, CUSTOMER)

    service.deliver_due(10)
    assert repo.items[0].status == "PENDING"

    repo.items[0] = repo.items[0].__class__(
        **{**repo.items[0].__dict__, "next_attempt_at": repo.items[0].created_at}
    )
    assert service.deliver_due(10) == 1
    assert repo.items[0].status == "SENT"
