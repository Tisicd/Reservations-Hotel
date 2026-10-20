import dataclasses
import datetime as dt
import uuid
from typing import Protocol

from app.domain.outbox import OutboxEvent
from app.domain.reservation import Reservation


class HoldConflict(Exception):
    """Mismo hold_id con parámetros distintos."""


class HoldExpired(Exception):
    """El hold venció."""


class HoldNotFound(Exception):
    """El hold no existe."""


class NoInventory(Exception):
    """Sin cupo para alguna noche."""


class PaymentNotFound(Exception):
    """El pago no existe."""


@dataclasses.dataclass(frozen=True)
class PaymentInfo:
    id: uuid.UUID
    status: str


@dataclasses.dataclass(frozen=True)
class RoomInfo:
    hotel_id: uuid.UUID
    price_cents: int


class ReservationRepository(Protocol):
    def ping(self) -> None: ...

    def get(self, reservation_id: uuid.UUID) -> Reservation: ...

    def get_by_idempotency_key(self, key: str) -> Reservation | None: ...

    def create_received(self, reservation: Reservation) -> tuple[Reservation, bool]: ...

    def transition(
        self,
        reservation: Reservation,
        to_status: str,
        reason: str | None,
        patch: dict,
        outbox_event: dict | None = None,
    ) -> Reservation: ...

    def transition_chain(
        self,
        reservation: Reservation,
        to_statuses: list[str],
        reason: str | None,
        patch: dict,
        outbox_event: dict | None = None,
    ) -> Reservation: ...

    def schedule_retry(
        self, reservation_id: uuid.UUID, attempts: int, next_attempt_at: dt.datetime
    ) -> None: ...

    def claim(self, reservation_id: uuid.UUID, lease_seconds: int) -> Reservation | None: ...

    def claim_due(self, limit: int, lease_seconds: int) -> list[Reservation]: ...

    def list_by_customer(self, customer_id: uuid.UUID) -> list[Reservation]: ...

    def events(self, reservation_id: uuid.UUID) -> list[dict]: ...

    def claim_outbox(self, limit: int, lease_seconds: int) -> list[OutboxEvent]: ...

    def mark_outbox_sent(self, outbox_id: uuid.UUID) -> None: ...

    def reschedule_outbox(self, outbox_id: uuid.UUID, delay_seconds: float) -> None: ...


class AvailabilityClient(Protocol):
    def create_hold(
        self,
        hold_id: uuid.UUID,
        room_id: uuid.UUID,
        check_in: dt.date,
        check_out: dt.date,
        units: int,
        ttl_seconds: int,
    ) -> str: ...

    def extend_hold(self, hold_id: uuid.UUID, ttl_seconds: int) -> dt.datetime: ...

    def confirm_hold(self, hold_id: uuid.UUID) -> str: ...

    def release_hold(self, hold_id: uuid.UUID) -> str: ...


class PaymentClient(Protocol):
    def create(
        self,
        reservation_id: uuid.UUID,
        amount_cents: int,
        currency: str,
        method: str,
        token: str,
        simulate: str,
    ) -> PaymentInfo: ...

    def get_by_reservation(self, reservation_id: uuid.UUID) -> PaymentInfo: ...

    def refund(self, payment_id: uuid.UUID) -> PaymentInfo: ...


class CustomerClient(Protocol):
    def exists(self, customer_id: uuid.UUID) -> bool: ...


class HotelClient(Protocol):
    def get_room(self, room_id: uuid.UUID) -> RoomInfo: ...


class Clock(Protocol):
    def now(self) -> dt.datetime: ...

    def today(self) -> dt.date: ...

class NotificationSender(Protocol):
    def send(self, event: OutboxEvent) -> None: ...
