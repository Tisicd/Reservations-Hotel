import dataclasses
import datetime as dt

from app.application.use_cases import ReservationService
from app.config import Settings
from app.infrastructure.clients.http import (
    HttpAvailabilityClient,
    HttpCustomerClient,
    HttpHotelClient,
    HttpJson,
    HttpPaymentClient,
)
from app.infrastructure.db.engine import make_engine
from app.infrastructure.db.repository import SqlReservationRepository


@dataclasses.dataclass
class Wiring:
    service: ReservationService
    closers: list

    def close(self) -> None:
        for closer in self.closers:
            closer()


def build(settings: Settings) -> Wiring:
    engine = make_engine(settings.db_url, settings.db_pool_size, settings.db_pool_timeout)
    availability_http = HttpJson(
        settings.availability_url,
        settings.connect_timeout_seconds,
        settings.read_timeout_seconds,
    )
    payment_http = HttpJson(
        settings.payment_url,
        settings.connect_timeout_seconds,
        settings.payment_read_timeout_seconds,
    )
    customer_http = HttpJson(
        settings.customer_url,
        settings.connect_timeout_seconds,
        settings.read_timeout_seconds,
    )
    hotel_http = HttpJson(
        settings.hotel_url,
        settings.connect_timeout_seconds,
        settings.read_timeout_seconds,
    )
    service = ReservationService(
        SqlReservationRepository(engine),
        HttpAvailabilityClient(availability_http),
        HttpPaymentClient(payment_http),
        HttpCustomerClient(customer_http),
        HttpHotelClient(hotel_http),
        _Clock(),
        settings.saga,
    )
    return Wiring(
        service=service,
        closers=[
            availability_http.close,
            payment_http.close,
            customer_http.close,
            hotel_http.close,
            engine.dispose,
        ],
    )


class _Clock:
    def now(self):
        return dt.datetime.now(dt.UTC)

    def today(self):
        return self.now().date()
