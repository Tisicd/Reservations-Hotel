import dataclasses
import datetime as dt
import uuid

from app.domain.errors import (
    CustomerNotFound,
    IdempotencyKeyReused,
    InvalidState,
    ValidationError,
)
from app.domain.reservation import (
    SIMULATION_MODES,
    Reservation,
    request_hash,
)
from app.domain.state_machine import CANCELLED, CANCELLING, CONFIRMED, RECEIVED

from .advance import SagaConfig, SagaEngine
from .ports import (
    AvailabilityClient,
    Clock,
    CustomerClient,
    HotelClient,
    PaymentClient,
    ReservationRepository,
)


@dataclasses.dataclass(frozen=True)
class CreateReservationCommand:
    customer_id: uuid.UUID
    hotel_id: uuid.UUID
    room_id: uuid.UUID
    check_in: dt.date
    check_out: dt.date
    method: str = "card"
    token: str = "tok_demo"
    simulate: str = "ok"


class ReservationService:
    def __init__(
        self,
        repo: ReservationRepository,
        availability: AvailabilityClient,
        payment: PaymentClient,
        customer: CustomerClient,
        hotel: HotelClient,
        clock: Clock,
        config: SagaConfig | None = None,
        jitter=None,
        sleep=None,
    ) -> None:
        self.repo = repo
        self.customer = customer
        self.hotel = hotel
        self.clock = clock
        self.config = config or SagaConfig()
        self.saga = SagaEngine(
            repo, availability, payment, clock, self.config, jitter=jitter, sleep=sleep
        )

    def create_reservation(
        self, idempotency_key: str, command: CreateReservationCommand
    ) -> tuple[Reservation, bool]:
        if not idempotency_key:
            raise ValidationError("Idempotency-Key es obligatoria")
        digest = request_hash(
            command.customer_id,
            command.hotel_id,
            command.room_id,
            command.check_in,
            command.check_out,
            command.method,
            command.token,
        )
        existing = self.repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            if existing.request_hash != digest:
                raise IdempotencyKeyReused("la clave se reutilizó con otro cuerpo")
            return existing, True

        self._validate(command)
        if not self.customer.exists(command.customer_id):
            raise CustomerNotFound("cliente inexistente")
        room = self.hotel.get_room(command.room_id)
        if room.hotel_id != command.hotel_id:
            raise ValidationError("la habitación no pertenece al hotel")

        nights = (command.check_out - command.check_in).days
        now = self.clock.now()
        reservation = Reservation(
            id=uuid.uuid4(),
            idempotency_key=idempotency_key,
            request_hash=digest,
            customer_id=command.customer_id,
            hotel_id=command.hotel_id,
            room_id=command.room_id,
            check_in=command.check_in,
            check_out=command.check_out,
            nights=nights,
            amount_cents=nights * room.price_cents,
            currency="USD",
            payment_method=command.method,
            payment_token=command.token,
            payment_simulate=command.simulate,
            status=RECEIVED,
            attempts=0,
            next_attempt_at=now,
            phase_started_at=now,
            version=0,
            created_at=now,
            updated_at=now,
        )
        stored, created = self.repo.create_received(reservation)
        if not created:
            if stored.request_hash != digest:
                raise IdempotencyKeyReused("la clave se reutilizó con otro cuerpo")
            return stored, True
        return self.saga.run_until_stable(stored.id, self.config.saga_sync_wait_seconds), False

    def cancel_reservation(self, reservation_id: uuid.UUID) -> Reservation:
        reservation = self.repo.get(reservation_id)
        if reservation.status == CANCELLED:
            return reservation
        if reservation.status == CANCELLING:
            return self.saga.run_until_stable(
                reservation_id, self.config.saga_sync_wait_seconds
            )
        if reservation.status != CONFIRMED:
            raise InvalidState(f"no se puede cancelar desde {reservation.status}")
        self.repo.transition(reservation, CANCELLING, None, {})
        return self.saga.run_until_stable(reservation_id, self.config.saga_sync_wait_seconds)

    def get_reservation(self, reservation_id: uuid.UUID) -> Reservation:
        return self.repo.get(reservation_id)

    def list_by_customer(self, customer_id: uuid.UUID) -> list[Reservation]:
        return self.repo.list_by_customer(customer_id)

    def events(self, reservation_id: uuid.UUID) -> list[dict]:
        return self.repo.events(reservation_id)

    def advance(self, reservation_id: uuid.UUID) -> Reservation:
        return self.saga.advance(reservation_id)

    def recover_due(self, limit: int) -> list[Reservation]:
        return self.saga.recover_due(limit)

    def ping(self) -> None:
        self.repo.ping()

    def _validate(self, command: CreateReservationCommand) -> None:
        if command.check_out <= command.check_in:
            raise ValidationError("check_out debe ser posterior a check_in")
        if command.check_in < self.clock.today():
            raise ValidationError("check_in no puede ser anterior a hoy")
        nights = (command.check_out - command.check_in).days
        if nights > self.config.max_nights:
            raise ValidationError("se supera el máximo de noches")
        if not command.method:
            raise ValidationError("payment.method es obligatorio")
        if not command.token:
            raise ValidationError("payment.token es obligatorio")
        if command.simulate not in SIMULATION_MODES:
            raise ValidationError(f"simulate inválido: {command.simulate}")
