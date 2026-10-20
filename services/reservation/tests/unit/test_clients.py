import datetime as dt
import uuid

import httpx
import pytest

from app.application.ports import (
    HoldConflict,
    HoldExpired,
    NoInventory,
    PaymentInfo,
    PaymentNotFound,
    RoomInfo,
)
from app.domain.errors import DependencyUnavailable, InvalidState, RoomNotFound
from app.infrastructure.clients.http import (
    HttpAvailabilityClient,
    HttpCustomerClient,
    HttpHotelClient,
    HttpJson,
    HttpPaymentClient,
)
from app.logging import request_id_var


def _error(code: str, status: int) -> httpx.Response:
    return httpx.Response(
        status, json={"error": {"code": code, "message": "", "request_id": "x", "details": {}}}
    )


def _client(cls, handler, base="http://deps"):
    transport = httpx.MockTransport(handler)
    return cls(HttpJson(base, 1, 2, transport))


def _hold(availability):
    today = dt.date.today()
    return availability.create_hold(uuid.uuid4(), uuid.uuid4(), today, today, 1, 60)


def test_create_hold_mapea_no_inventory_y_conflicto():
    availability = _client(
        HttpAvailabilityClient,
        lambda request: _error("NO_INVENTORY", 409),
    )
    with pytest.raises(NoInventory):
        _hold(availability)

    availability = _client(
        HttpAvailabilityClient,
        lambda request: _error("HOLD_CONFLICT", 409),
    )
    with pytest.raises(HoldConflict):
        _hold(availability)


def test_confirm_expired_y_release_exitoso():
    availability = _client(
        HttpAvailabilityClient,
        lambda request: _error("HOLD_EXPIRED", 409),
    )
    with pytest.raises(HoldExpired):
        availability.confirm_hold(uuid.uuid4())

    availability = _client(
        HttpAvailabilityClient,
        lambda request: httpx.Response(200, json={"status": "RELEASED"}),
    )
    assert availability.release_hold(uuid.uuid4()) == "RELEASED"


def test_timeout_es_ambiguo_y_conexion_rechazada_no():
    def timeout(request):
        raise httpx.ReadTimeout("timeout", request=request)

    availability = _client(HttpAvailabilityClient, timeout)
    with pytest.raises(DependencyUnavailable) as exc:
        _hold(availability)
    assert exc.value.ambiguous is True

    def refused(request):
        raise httpx.ConnectError("refused", request=request)

    availability = _client(HttpAvailabilityClient, refused)
    with pytest.raises(DependencyUnavailable) as exc:
        _hold(availability)
    assert exc.value.ambiguous is False


def test_503_es_ambiguo():
    customer = _client(
        HttpCustomerClient,
        lambda request: _error("DEPENDENCY_UNAVAILABLE", 503),
    )
    with pytest.raises(DependencyUnavailable) as exc:
        customer.exists(uuid.uuid4())
    assert exc.value.ambiguous is True


def test_post_no_se_reintenta():
    calls = []

    def timeout(request):
        calls.append(request.url.path)
        raise httpx.ReadTimeout("timeout", request=request)

    availability = _client(HttpAvailabilityClient, timeout)
    with pytest.raises(DependencyUnavailable):
        _hold(availability)
    assert len(calls) == 1


def test_get_de_validacion_reintenta_y_propaga_request_id():
    calls = []
    seen = []
    request_id_var.set("req-123")

    def handler(request):
        calls.append(1)
        seen.append(request.headers.get("X-Request-ID"))
        if len(calls) < 3:
            return _error("DEPENDENCY_UNAVAILABLE", 503)
        return httpx.Response(200, json={"id": str(uuid.uuid4())})

    customer = _client(HttpCustomerClient, handler)
    assert customer.exists(uuid.uuid4()) is True
    assert len(calls) == 3
    assert set(seen) == {"req-123"}


def test_cliente_inexistente_y_habitacion_inexistente():
    customer = _client(
        HttpCustomerClient, lambda request: _error("NOT_FOUND", 404)
    )
    assert customer.exists(uuid.uuid4()) is False

    hotel = _client(HttpHotelClient, lambda request: _error("NOT_FOUND", 404))
    with pytest.raises(RoomNotFound):
        hotel.get_room(uuid.uuid4())


def test_hotel_parsea_habitacion():
    hotel_id = uuid.uuid4()
    room_id = uuid.uuid4()
    hotel = _client(
        HttpHotelClient,
        lambda request: httpx.Response(
            200,
            json={
                "id": str(room_id),
                "hotel_id": str(hotel_id),
                "price_per_night_cents": 12500,
            },
        ),
    )
    room = hotel.get_room(room_id)
    assert room == RoomInfo(hotel_id=hotel_id, price_cents=12500)


def test_payment_mapea_estados_y_errores():
    payment_id = uuid.uuid4()
    reservation_id = uuid.uuid4()
    payment = _client(
        HttpPaymentClient,
        lambda request: httpx.Response(
            201,
            json={
                "id": str(payment_id),
                "reservation_id": str(reservation_id),
                "status": "SUCCEEDED",
            },
        ),
    )
    info = payment.create(reservation_id, 100, "USD", "card", "tok", "ok")
    assert info == PaymentInfo(id=payment_id, status="SUCCEEDED")

    payment = _client(
        HttpPaymentClient, lambda request: _error("NOT_FOUND", 404)
    )
    with pytest.raises(PaymentNotFound):
        payment.get_by_reservation(reservation_id)

    payment = _client(
        HttpPaymentClient, lambda request: _error("INVALID_STATE", 409)
    )
    with pytest.raises(InvalidState):
        payment.refund(payment_id)


def test_confirm_parsea_respuesta():
    response = httpx.Response(200, json={"status": "CONFIRMED"})
    availability = _client(HttpAvailabilityClient, lambda request: response)
    assert availability.confirm_hold(uuid.uuid4()) == "CONFIRMED"
