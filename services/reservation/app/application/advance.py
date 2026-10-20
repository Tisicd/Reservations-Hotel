import dataclasses
import datetime as dt
import random
import time
import uuid
from collections.abc import Callable

from app.domain.errors import ConcurrentModification, DependencyUnavailable, InvalidState
from app.domain.reservation import (
    REASON_CONFIRM_TIMEOUT,
    REASON_DECLINED,
    REASON_HOLD_LOST,
    REASON_HOLD_LOST_REFUNDED,
    REASON_NO_INVENTORY,
    REASON_RECONCILE_TIMEOUT,
    REASON_REFUND_TIMEOUT,
    REASON_TECHNICAL,
    Reservation,
)
from app.domain.state_machine import (
    CANCELLED,
    CANCELLING,
    CONFIRMED,
    FAILED_TECHNICAL,
    HELD,
    MANUAL_REVIEW,
    PAID,
    PAYMENT_DECLINED,
    PAYMENT_PENDING,
    PAYMENT_UNKNOWN,
    RECEIVED,
    REFUND_REQUIRED,
    REJECTED_NO_INVENTORY,
    is_stable,
)

from .ports import (
    AvailabilityClient,
    Clock,
    HoldConflict,
    HoldExpired,
    HoldNotFound,
    NoInventory,
    PaymentClient,
    PaymentNotFound,
    ReservationRepository,
)


@dataclasses.dataclass(frozen=True)
class SagaConfig:
    saga_sync_wait_seconds: float = 5.0
    hold_ttl_seconds: int = 600
    saga_hold_deadline_seconds: int = 60
    payment_max_technical_retries: int = 3
    payment_reconcile_deadline_seconds: int = 900
    confirm_deadline_seconds: int = 120
    manual_review_hold_ttl_seconds: int = 86400
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 30.0
    lease_seconds: int = 15
    max_nights: int = 30


def backoff(attempts: int, config: SagaConfig, jitter: Callable[[], float]) -> float:
    base = min(config.backoff_max_seconds, config.backoff_base_seconds * (2**attempts))
    return base * jitter()


def _default_jitter() -> float:
    return random.uniform(0.5, 1.0)


class SagaEngine:
    def __init__(
        self,
        repo: ReservationRepository,
        availability: AvailabilityClient,
        payment: PaymentClient,
        clock: Clock,
        config: SagaConfig,
        jitter: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.repo = repo
        self.availability = availability
        self.payment = payment
        self.clock = clock
        self.config = config
        self.jitter = jitter or _default_jitter
        self.sleep = sleep or time.sleep
        self._handlers = {
            RECEIVED: self._on_received,
            HELD: self._on_held,
            PAYMENT_PENDING: self._on_payment_pending,
            PAYMENT_UNKNOWN: self._on_payment_unknown,
            PAID: self._on_paid,
            PAYMENT_DECLINED: self._on_payment_declined,
            REFUND_REQUIRED: self._on_refund_required,
            CANCELLING: self._on_cancelling,
        }

    def advance(self, reservation_id: uuid.UUID) -> Reservation:
        claimed = self.repo.claim(reservation_id, self.config.lease_seconds)
        if claimed is None:
            return self.repo.get(reservation_id)
        return self._step(claimed)

    def advance_claimed(self, reservation: Reservation) -> Reservation:
        return self._step(reservation)

    def recover_due(self, limit: int) -> list[Reservation]:
        done = []
        for reservation in self.repo.claim_due(limit, self.config.lease_seconds):
            try:
                done.append(self._step(reservation))
            except ConcurrentModification:
                continue
        return done

    def run_until_stable(self, reservation_id: uuid.UUID, max_wait_seconds: float) -> Reservation:
        deadline = self.clock.now() + dt.timedelta(seconds=max_wait_seconds)
        while True:
            reservation = self.advance(reservation_id)
            if is_stable(reservation.status):
                return reservation
            now = self.clock.now()
            remaining = (deadline - now).total_seconds()
            if remaining <= 0:
                return reservation
            wait = (reservation.next_attempt_at - now).total_seconds()
            if wait <= 0:
                wait = min(0.05, remaining)
            self.sleep(min(wait, remaining))

    def _step(self, reservation: Reservation) -> Reservation:
        handler = self._handlers.get(reservation.status)
        if handler is None:
            return reservation
        try:
            return handler(reservation)
        except ConcurrentModification:
            return self.repo.get(reservation.id)

    def _elapsed(self, reservation: Reservation) -> float:
        return (self.clock.now() - reservation.phase_started_at).total_seconds()

    def _retry(self, reservation: Reservation, attempts: int | None = None) -> Reservation:
        attempts = reservation.attempts + 1 if attempts is None else attempts
        delay = backoff(attempts, self.config, self.jitter)
        next_at = self.clock.now() + dt.timedelta(seconds=delay)
        self.repo.schedule_retry(reservation.id, attempts, next_at)
        return dataclasses.replace(
            reservation, attempts=attempts, next_attempt_at=next_at, locked_until=None
        )

    def _transition(
        self,
        reservation: Reservation,
        to_status: str,
        reason: str | None = None,
        patch: dict | None = None,
        outbox_event: dict | None = None,
    ) -> Reservation:
        return self.repo.transition(
            reservation, to_status, reason, patch or {}, outbox_event
        )

    def _chain(
        self,
        reservation: Reservation,
        to_statuses: list[str],
        reason: str | None = None,
        patch: dict | None = None,
        outbox_event: dict | None = None,
    ) -> Reservation:
        return self.repo.transition_chain(
            reservation, to_statuses, reason, patch or {}, outbox_event
        )

    def _release_quietly(self, reservation_id: uuid.UUID) -> None:
        try:
            self.availability.release_hold(reservation_id)
        except (HoldNotFound, HoldExpired, NoInventory, DependencyUnavailable):
            pass

    def _extend_quietly(self, reservation_id: uuid.UUID, ttl_seconds: int) -> None:
        try:
            self.availability.extend_hold(reservation_id, ttl_seconds)
        except (HoldNotFound, HoldExpired, DependencyUnavailable):
            pass

    def _on_received(self, reservation: Reservation) -> Reservation:
        if self._elapsed(reservation) >= self.config.saga_hold_deadline_seconds:
            self._release_quietly(reservation.id)
            return self._transition(reservation, FAILED_TECHNICAL, REASON_TECHNICAL)
        try:
            status = self.availability.create_hold(
                reservation.id,
                reservation.room_id,
                reservation.check_in,
                reservation.check_out,
                1,
                self.config.hold_ttl_seconds,
            )
        except NoInventory:
            return self._transition(reservation, REJECTED_NO_INVENTORY, REASON_NO_INVENTORY)
        except HoldConflict:
            self._release_quietly(reservation.id)
            return self._transition(reservation, FAILED_TECHNICAL, REASON_TECHNICAL)
        except DependencyUnavailable:
            return self._retry(reservation)
        if status != HELD:
            self._release_quietly(reservation.id)
            return self._transition(reservation, FAILED_TECHNICAL, REASON_TECHNICAL)
        return self._chain(reservation, [HELD, PAYMENT_PENDING])

    def _on_held(self, reservation: Reservation) -> Reservation:
        return self._transition(reservation, PAYMENT_PENDING)

    def _enter_unknown(
        self, reservation: Reservation, payment_id: uuid.UUID | None = None
    ) -> Reservation:
        next_at = self.clock.now() + dt.timedelta(
            seconds=backoff(0, self.config, self.jitter)
        )
        patch = {"payment_status": "UNKNOWN", "next_attempt_at": next_at}
        if payment_id is not None:
            patch["payment_id"] = payment_id
        return self._transition(reservation, PAYMENT_UNKNOWN, None, patch)

    def _on_payment_pending(self, reservation: Reservation) -> Reservation:
        try:
            info = self.payment.create(
                reservation.id,
                reservation.amount_cents,
                reservation.currency,
                reservation.payment_method,
                reservation.payment_token,
                reservation.payment_simulate,
            )
        except DependencyUnavailable as e:
            if e.ambiguous:
                return self._enter_unknown(reservation)
            return self._retry(reservation)
        except PaymentNotFound:
            return self._retry(reservation)

        patch = {"payment_id": info.id, "payment_status": info.status}
        if info.status == "SUCCEEDED":
            return self._transition(reservation, PAID, None, patch)
        if info.status == "DECLINED":
            return self._transition(reservation, PAYMENT_DECLINED, REASON_DECLINED, patch)
        if info.status == "UNKNOWN":
            return self._enter_unknown(reservation, info.id)

        if reservation.attempts + 1 >= self.config.payment_max_technical_retries:
            return self._transition(reservation, PAYMENT_DECLINED, REASON_TECHNICAL, patch)
        return self._retry(reservation, attempts=reservation.attempts + 1)

    def _on_payment_unknown(self, reservation: Reservation) -> Reservation:
        if self._elapsed(reservation) >= self.config.payment_reconcile_deadline_seconds:
            self._extend_quietly(reservation.id, self.config.manual_review_hold_ttl_seconds)
            return self._transition(reservation, MANUAL_REVIEW, REASON_RECONCILE_TIMEOUT)

        hold_lost = False
        try:
            self.availability.extend_hold(reservation.id, self.config.hold_ttl_seconds)
        except (HoldExpired, HoldNotFound):
            hold_lost = True
        except DependencyUnavailable:
            return self._retry(reservation)

        try:
            info = self.payment.get_by_reservation(reservation.id)
        except PaymentNotFound:
            return self._transition(reservation, PAYMENT_PENDING)
        except DependencyUnavailable:
            return self._retry(reservation)

        patch = {"payment_id": info.id, "payment_status": info.status}
        if info.status == "SUCCEEDED":
            if hold_lost:
                return self._chain(
                    reservation, [PAID, REFUND_REQUIRED], REASON_HOLD_LOST, patch
                )
            return self._transition(reservation, PAID, None, patch)
        if info.status == "DECLINED":
            return self._transition(reservation, PAYMENT_DECLINED, REASON_DECLINED, patch)
        if info.status == "FAILED_TECHNICAL":
            return self._transition(reservation, PAYMENT_PENDING, None, patch)
        if hold_lost:
            return self._transition(reservation, MANUAL_REVIEW, REASON_RECONCILE_TIMEOUT, patch)
        return self._retry(reservation)

    def _on_paid(self, reservation: Reservation) -> Reservation:
        if self._elapsed(reservation) >= self.config.confirm_deadline_seconds:
            return self._transition(reservation, MANUAL_REVIEW, REASON_CONFIRM_TIMEOUT)
        try:
            status = self.availability.confirm_hold(reservation.id)
        except (HoldExpired, HoldNotFound):
            return self._transition(reservation, REFUND_REQUIRED, REASON_HOLD_LOST)
        except DependencyUnavailable:
            return self._retry(reservation)
        if status != CONFIRMED:
            return self._transition(reservation, REFUND_REQUIRED, REASON_HOLD_LOST)
        return self._transition(
            reservation, CONFIRMED, None, {}, self._outbox_confirmed(reservation)
        )

    def _on_payment_declined(self, reservation: Reservation) -> Reservation:
        if self._elapsed(reservation) >= self.config.saga_hold_deadline_seconds:
            return self._transition(reservation, CANCELLED, reservation.status_reason)
        try:
            self.availability.release_hold(reservation.id)
        except (HoldNotFound, HoldExpired):
            pass
        except DependencyUnavailable:
            return self._retry(reservation)
        return self._transition(reservation, CANCELLED, reservation.status_reason)

    def _on_refund_required(self, reservation: Reservation) -> Reservation:
        if self._elapsed(reservation) >= self.config.confirm_deadline_seconds:
            return self._transition(reservation, MANUAL_REVIEW, REASON_REFUND_TIMEOUT)
        if reservation.payment_id is None:
            return self._transition(reservation, MANUAL_REVIEW, REASON_REFUND_TIMEOUT)
        try:
            self.payment.refund(reservation.payment_id)
        except (PaymentNotFound, InvalidState):
            return self._transition(reservation, MANUAL_REVIEW, REASON_REFUND_TIMEOUT)
        except DependencyUnavailable:
            return self._retry(reservation)
        return self._transition(reservation, CANCELLED, REASON_HOLD_LOST_REFUNDED)

    def _on_cancelling(self, reservation: Reservation) -> Reservation:
        try:
            self.availability.release_hold(reservation.id)
        except (HoldNotFound, HoldExpired):
            pass
        except DependencyUnavailable:
            return self._retry(reservation)
        if reservation.payment_id is None:
            return self._transition(reservation, MANUAL_REVIEW, REASON_REFUND_TIMEOUT)
        try:
            self.payment.refund(reservation.payment_id)
        except (PaymentNotFound, InvalidState):
            return self._transition(reservation, MANUAL_REVIEW, REASON_REFUND_TIMEOUT)
        except DependencyUnavailable:
            return self._retry(reservation)
        return self._transition(
            reservation, CANCELLED, None, {}, self._outbox_cancelled(reservation)
        )

    @staticmethod
    def _outbox_confirmed(reservation: Reservation) -> dict:
        return {"type": "reservation.confirmed", "payload": _payload(reservation)}

    @staticmethod
    def _outbox_cancelled(reservation: Reservation) -> dict:
        return {"type": "reservation.cancelled", "payload": _payload(reservation)}


def _payload(reservation: Reservation) -> dict:
    return {
        "reservation_id": str(reservation.id),
        "customer_id": str(reservation.customer_id),
        "hotel_id": str(reservation.hotel_id),
        "room_id": str(reservation.room_id),
        "check_in": reservation.check_in.isoformat(),
        "check_out": reservation.check_out.isoformat(),
        "nights": reservation.nights,
        "amount_cents": reservation.amount_cents,
        "currency": reservation.currency,
        "payment_id": str(reservation.payment_id) if reservation.payment_id else None,
    }

