import concurrent.futures as futures
import datetime as dt
import os
import time
import uuid
from functools import partial

import httpx
import pytest
from sqlalchemy import text

from app.application.advance import SagaConfig
from app.application.ports import RoomInfo
from app.application.use_cases import CreateReservationCommand, ReservationService
from app.domain.state_machine import (
    CANCELLED,
    CONFIRMED,
    PAYMENT_UNKNOWN,
    REJECTED_NO_INVENTORY,
    is_stable,
)
from app.infrastructure.clients.http import (
    HttpAvailabilityClient,
    HttpJson,
    HttpPaymentClient,
)
from app.infrastructure.db.repository import SqlReservationRepository

pytestmark = pytest.mark.stack

AVAILABILITY_URL = os.environ.get("AVAILABILITY_URL", "http://127.0.0.1:8081/svc/availability")
PAYMENT_URL = os.environ.get("PAYMENT_URL", "http://127.0.0.1:8081/svc/payment")


class _Clock:
    def now(self):
        return dt.datetime.now(dt.UTC)

    def today(self):
        return self.now().date()


class _Customer:
    def exists(self, _customer_id):
        return True


class _Hotel:
    def __init__(self, hotel_id: uuid.UUID) -> None:
        self.hotel_id = hotel_id

    def get_room(self, _room_id) -> RoomInfo:
        return RoomInfo(hotel_id=self.hotel_id, price_cents=10000)


def _service(engine, hotel_id: uuid.UUID) -> ReservationService:
    return ReservationService(
        SqlReservationRepository(engine),
        HttpAvailabilityClient(HttpJson(AVAILABILITY_URL, 1, 2)),
        HttpPaymentClient(HttpJson(PAYMENT_URL, 1, 5)),
        _Customer(),
        _Hotel(hotel_id),
        _Clock(),
        SagaConfig(),
    )


def _dates():
    today = dt.date.today()
    return today + dt.timedelta(days=2), today + dt.timedelta(days=5)


def _seed(room_id, hotel_id, check_in, check_out, total):
    response = httpx.put(
        f"{AVAILABILITY_URL}/inventory/{room_id}",
        json={
            "hotel_id": str(hotel_id),
            "from": check_in.isoformat(),
            "to": check_out.isoformat(),
            "total": total,
        },
    )
    assert response.status_code == 200, response.text


def _available(room_id, hotel_id, check_in, check_out) -> int:
    response = httpx.get(
        f"{AVAILABILITY_URL}/availability",
        params={
            "hotel_id": str(hotel_id),
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
        },
    )
    for room in response.json()["rooms"]:
        if room["room_id"] == str(room_id):
            return room["available"]
    raise AssertionError("habitación no encontrada")


def _create(service, key_prefix, hotel_id, room_id, check_in, check_out, index):
    return service.create_reservation(
        f"{key_prefix}-{index}",
        _command(hotel_id, room_id, check_in, check_out),
    )


def _command(hotel_id, room_id, check_in, check_out, simulate="ok"):
    return CreateReservationCommand(
        customer_id=uuid.uuid4(),
        hotel_id=hotel_id,
        room_id=room_id,
        check_in=check_in,
        check_out=check_out,
        simulate=simulate,
    )


def test_camino_feliz_contra_availability_y_payment_reales(engine, clean):
    hotel_id = uuid.uuid4()
    room_id = uuid.uuid4()
    check_in, check_out = _dates()
    _seed(room_id, hotel_id, check_in, check_out, 5)
    service = _service(engine, hotel_id)

    reservation, _ = service.create_reservation(
        "stack-happy", _command(hotel_id, room_id, check_in, check_out)
    )

    assert reservation.status == CONFIRMED
    events = [e["to_status"] for e in service.events(reservation.id)]
    assert events == [
        "RECEIVED",
        "HELD",
        "PAYMENT_PENDING",
        "PAID",
        "CONFIRMED",
    ]
    assert _available(room_id, hotel_id, check_in, check_out) == 4
    payment = httpx.get(
        f"{PAYMENT_URL}/payments", params={"reservation_id": str(reservation.id)}
    )
    assert payment.json()["status"] == "SUCCEEDED"


def test_rechazo_libera_el_hold(engine, clean):
    hotel_id = uuid.uuid4()
    room_id = uuid.uuid4()
    check_in, check_out = _dates()
    _seed(room_id, hotel_id, check_in, check_out, 1)
    service = _service(engine, hotel_id)

    reservation, _ = service.create_reservation(
        "stack-decline",
        _command(hotel_id, room_id, check_in, check_out, simulate="decline"),
    )

    assert reservation.status == CANCELLED
    assert reservation.status_reason == "DECLINED"
    assert _available(room_id, hotel_id, check_in, check_out) == 1
    payment = httpx.get(
        f"{PAYMENT_URL}/payments", params={"reservation_id": str(reservation.id)}
    )
    assert payment.json()["status"] == "DECLINED"


def test_pago_incierto_se_recupera_a_confirmado(engine, clean):
    hotel_id = uuid.uuid4()
    room_id = uuid.uuid4()
    check_in, check_out = _dates()
    _seed(room_id, hotel_id, check_in, check_out, 1)
    service = _service(engine, hotel_id)

    reservation, _ = service.create_reservation(
        "stack-unknown",
        _command(
            hotel_id,
            room_id,
            check_in,
            check_out,
            simulate="process_then_drop_response",
        ),
    )

    for _ in range(60):
        if is_stable(reservation.status):
            break
        time.sleep(0.5)
        reservation = service.advance(reservation.id)

    assert reservation.status == CONFIRMED
    states = [e["to_status"] for e in service.events(reservation.id)]
    assert PAYMENT_UNKNOWN in states
    assert states[-1] == CONFIRMED


def test_veinte_concurrentes_por_cinco_cupos_diez_veces(engine, clean):
    for repetition in range(10):
        hotel_id = uuid.uuid4()
        room_id = uuid.uuid4()
        check_in, check_out = _dates()
        _seed(room_id, hotel_id, check_in, check_out, 5)
        service = _service(engine, hotel_id)

        create = partial(
            _create,
            service,
            f"stack-{repetition}",
            hotel_id,
            room_id,
            check_in,
            check_out,
        )
        with futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(create, range(20)))

        statuses = [reservation.status for reservation, _ in results]
        assert statuses.count(CONFIRMED) == 5, f"repetición {repetition}"
        assert statuses.count(REJECTED_NO_INVENTORY) == 15
        assert _available(room_id, hotel_id, check_in, check_out) == 0

        with engine.connect() as conn:
            counts = dict(
                conn.execute(
                    text(
                        "SELECT status, count(*) FROM reservations "
                        "WHERE room_id = :room GROUP BY status"
                    ),
                    {"room": room_id},
                ).fetchall()
            )
        assert counts == {CONFIRMED: 5, REJECTED_NO_INVENTORY: 15}

        for reservation, _ in results:
            response = httpx.get(
                f"{PAYMENT_URL}/payments",
                params={"reservation_id": str(reservation.id)},
            )
            if reservation.status == CONFIRMED:
                assert response.status_code == 200
            else:
                assert response.status_code == 404
