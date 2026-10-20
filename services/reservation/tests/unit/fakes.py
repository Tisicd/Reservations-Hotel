import dataclasses
import datetime as dt
import threading
import uuid

from app.application.advance import SagaConfig
from app.application.ports import (
    HoldConflict,
    HoldExpired,
    HoldNotFound,
    NoInventory,
    PaymentInfo,
    PaymentNotFound,
    RoomInfo,
)
from app.application.use_cases import ReservationService
from app.domain.errors import (
    ConcurrentModification,
    DependencyUnavailable,
    InvalidState,
    ReservationNotFound,
    RoomNotFound,
)
from app.domain.reservation import Reservation
from app.domain.state_machine import CONFIRMED, HELD, RECEIVED, ensure_transition, is_stable

TEST_CONFIG = SagaConfig(
    saga_sync_wait_seconds=5,
    hold_ttl_seconds=600,
    saga_hold_deadline_seconds=10,
    payment_max_technical_retries=3,
    payment_reconcile_deadline_seconds=20,
    confirm_deadline_seconds=10,
    manual_review_hold_ttl_seconds=86400,
    backoff_base_seconds=0.5,
    backoff_max_seconds=2,
    lease_seconds=15,
)


class SimulatedCrash(Exception):
    pass


class CrashPlan:
    def __init__(self, target: int | None = None) -> None:
        self.target = target
        self.count = 0
        self.ops: list[str] = []

    def tick(self, name: str) -> None:
        self.ops.append(name)
        self.count += 1
        if self.target is not None and self.count == self.target:
            self.target = None
            raise SimulatedCrash(name)

    def disarm(self) -> None:
        self.target = None


class FakeClock:
    def __init__(self, start: dt.datetime | None = None) -> None:
        self._now = start or dt.datetime(2026, 11, 1, 12, tzinfo=dt.UTC)
        self._lock = threading.Lock()

    def now(self) -> dt.datetime:
        with self._lock:
            return self._now

    def today(self) -> dt.date:
        return self.now().date()

    def advance(self, seconds: float) -> None:
        with self._lock:
            self._now += dt.timedelta(seconds=seconds)


def clock_sleep(clock: FakeClock):
    def _sleep(seconds: float) -> None:
        clock.advance(max(seconds, 0.001))

    return _sleep


class FakeRepo:
    def __init__(self, clock: FakeClock, crash: CrashPlan | None = None) -> None:
        self.clock = clock
        self.crash = crash or CrashPlan()
        self.rows: dict[uuid.UUID, Reservation] = {}
        self.by_key: dict[str, uuid.UUID] = {}
        self.event_rows: list[dict] = []
        self.outbox_rows: list[dict] = []
        self.lock = threading.RLock()

    def _tick(self, name: str) -> None:
        self.crash.tick(name)

    def ping(self) -> None:
        return None

    def get(self, reservation_id: uuid.UUID) -> Reservation:
        with self.lock:
            try:
                return self.rows[reservation_id]
            except KeyError:
                raise ReservationNotFound() from None

    def get_by_idempotency_key(self, key: str) -> Reservation | None:
        with self.lock:
            reservation_id = self.by_key.get(key)
            return self.rows.get(reservation_id) if reservation_id else None

    def create_received(self, reservation: Reservation) -> tuple[Reservation, bool]:
        with self.lock:
            self._tick("repo.create_received.before")
            existing_id = self.by_key.get(reservation.idempotency_key)
            if existing_id is not None:
                return self.rows[existing_id], False
            self.rows[reservation.id] = reservation
            self.by_key[reservation.idempotency_key] = reservation.id
            self._add_event(reservation.id, None, RECEIVED, None)
            self._tick("repo.create_received.after")
            return reservation, True

    def transition(
        self,
        reservation: Reservation,
        to_status: str,
        reason: str | None,
        patch: dict,
        outbox_event: dict | None = None,
    ) -> Reservation:
        return self.transition_chain(reservation, [to_status], reason, patch, outbox_event)

    def transition_chain(
        self,
        reservation: Reservation,
        to_statuses: list[str],
        reason: str | None,
        patch: dict,
        outbox_event: dict | None = None,
    ) -> Reservation:
        with self.lock:
            self._tick("repo.transition.before")
            stored = self.rows.get(reservation.id)
            if stored is None:
                raise ReservationNotFound()
            if stored.status != reservation.status or stored.version != reservation.version:
                raise ConcurrentModification()
            current = stored
            now = self.clock.now()
            for index, to_status in enumerate(to_statuses):
                ensure_transition(current.status, to_status)
                last = index == len(to_statuses) - 1
                values = {
                    "status": to_status,
                    "status_reason": reason if last else None,
                    "phase_started_at": now,
                    "next_attempt_at": now,
                    "attempts": 0,
                    "locked_until": None,
                    "version": current.version + 1,
                    "updated_at": now,
                }
                if last:
                    values.update(patch)
                self._add_event(current.id, current.status, to_status, values["status_reason"])
                current = dataclasses.replace(current, **values)
            self.rows[current.id] = current
            if outbox_event is not None:
                self.outbox_rows.append(
                    {
                        "id": uuid.uuid4(),
                        "aggregate_id": current.id,
                        "type": outbox_event["type"],
                        "payload": outbox_event["payload"],
                        "status": "PENDING",
                        "attempts": 0,
                        "created_at": now,
                    }
                )
            self._tick("repo.transition.after")
            return current

    def schedule_retry(
        self, reservation_id: uuid.UUID, attempts: int, next_attempt_at: dt.datetime
    ) -> None:
        with self.lock:
            self._tick("repo.schedule_retry.before")
            stored = self.rows[reservation_id]
            self.rows[reservation_id] = dataclasses.replace(
                stored,
                attempts=attempts,
                next_attempt_at=next_attempt_at,
                locked_until=None,
                version=stored.version + 1,
                updated_at=self.clock.now(),
            )
            self._tick("repo.schedule_retry.after")

    def claim(self, reservation_id: uuid.UUID, lease_seconds: int) -> Reservation | None:
        with self.lock:
            self._tick("repo.claim.before")
            stored = self.rows.get(reservation_id)
            if stored is None:
                raise ReservationNotFound()
            now = self.clock.now()
            if is_stable(stored.status):
                return None
            if stored.locked_until is not None and stored.locked_until > now:
                return None
            if stored.next_attempt_at is not None and stored.next_attempt_at > now:
                return None
            claimed = dataclasses.replace(
                stored, locked_until=now + dt.timedelta(seconds=lease_seconds)
            )
            self.rows[reservation_id] = claimed
            self._tick("repo.claim.after")
            return claimed

    def claim_due(self, limit: int, lease_seconds: int) -> list[Reservation]:
        with self.lock:
            self._tick("repo.claim_due.before")
            now = self.clock.now()
            due = []
            for stored in self.rows.values():
                if is_stable(stored.status):
                    continue
                if stored.locked_until is not None and stored.locked_until > now:
                    continue
                if stored.next_attempt_at is not None and stored.next_attempt_at > now:
                    continue
                due.append(stored)
            due.sort(key=lambda r: r.next_attempt_at)
            claimed = []
            for stored in due[:limit]:
                copy = dataclasses.replace(
                    stored, locked_until=now + dt.timedelta(seconds=lease_seconds)
                )
                self.rows[stored.id] = copy
                claimed.append(copy)
            self._tick("repo.claim_due.after")
            return claimed

    def list_by_customer(self, customer_id: uuid.UUID) -> list[Reservation]:
        with self.lock:
            rows = [r for r in self.rows.values() if r.customer_id == customer_id]
            return sorted(rows, key=lambda r: r.created_at, reverse=True)

    def events(self, reservation_id: uuid.UUID) -> list[dict]:
        with self.lock:
            return [e for e in self.event_rows if e["reservation_id"] == reservation_id]

    def _add_event(
        self,
        reservation_id: uuid.UUID,
        from_status: str | None,
        to_status: str,
        reason: str | None,
    ) -> None:
        self.event_rows.append(
            {
                "reservation_id": reservation_id,
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
                "at": self.clock.now(),
            }
        )


class FakeAvailability:
    def __init__(
        self,
        clock: FakeClock,
        crash: CrashPlan | None = None,
        create_behavior: str = "ok",
        confirm_behavior: str = "ok",
        extend_behavior: str = "ok",
        release_behavior: str = "ok",
    ) -> None:
        self.clock = clock
        self.crash = crash or CrashPlan()
        self.create_behavior = create_behavior
        self.confirm_behavior = confirm_behavior
        self.extend_behavior = extend_behavior
        self.release_behavior = release_behavior
        self.holds: dict[uuid.UUID, dict] = {}
        self.create_calls: list[uuid.UUID] = []
        self.created: list[uuid.UUID] = []
        self.confirms: list[uuid.UUID] = []
        self.releases: list[uuid.UUID] = []
        self.extends: list[tuple[uuid.UUID, int]] = []
        self.lock = threading.RLock()

    def create_hold(
        self,
        hold_id: uuid.UUID,
        room_id: uuid.UUID,
        check_in: dt.date,
        check_out: dt.date,
        units: int,
        ttl_seconds: int,
    ) -> str:
        with self.lock:
            self.crash.tick("availability.create_hold.before")
            self.create_calls.append(hold_id)
            if self.create_behavior == "down":
                raise DependencyUnavailable("availability caída", ambiguous=True)
            hold = self.holds.get(hold_id)
            if hold is not None:
                self.crash.tick("availability.create_hold.after")
                return hold["status"]
            if self.create_behavior == "no_inventory":
                raise NoInventory()
            if self.create_behavior == "conflict":
                raise HoldConflict()
            self.holds[hold_id] = {
                "status": HELD,
                "expires_at": self.clock.now() + dt.timedelta(seconds=ttl_seconds),
            }
            self.created.append(hold_id)
            self.crash.tick("availability.create_hold.after")
            return HELD

    def extend_hold(self, hold_id: uuid.UUID, ttl_seconds: int) -> dt.datetime:
        with self.lock:
            self.crash.tick("availability.extend_hold.before")
            self.extends.append((hold_id, ttl_seconds))
            if self.extend_behavior == "down":
                raise DependencyUnavailable("availability caída", ambiguous=True)
            hold = self.holds.get(hold_id)
            if hold is None or self.extend_behavior == "not_found":
                raise HoldNotFound()
            if self.extend_behavior == "expired" or hold["status"] != HELD:
                raise HoldExpired()
            if hold["expires_at"] <= self.clock.now():
                raise HoldExpired()
            hold["expires_at"] = self.clock.now() + dt.timedelta(seconds=ttl_seconds)
            self.crash.tick("availability.extend_hold.after")
            return hold["expires_at"]

    def confirm_hold(self, hold_id: uuid.UUID) -> str:
        with self.lock:
            self.crash.tick("availability.confirm_hold.before")
            if self.confirm_behavior == "down":
                raise DependencyUnavailable("availability caída", ambiguous=True)
            hold = self.holds.get(hold_id)
            if hold is None:
                raise HoldNotFound()
            if self.confirm_behavior == "expired":
                raise HoldExpired()
            if hold["status"] == CONFIRMED:
                return CONFIRMED
            if hold["status"] != HELD or hold["expires_at"] <= self.clock.now():
                raise HoldExpired()
            hold["status"] = CONFIRMED
            self.confirms.append(hold_id)
            self.crash.tick("availability.confirm_hold.after")
            return CONFIRMED

    def release_hold(self, hold_id: uuid.UUID) -> str:
        with self.lock:
            self.crash.tick("availability.release_hold.before")
            if self.release_behavior == "down":
                raise DependencyUnavailable("availability caída", ambiguous=True)
            hold = self.holds.get(hold_id)
            if hold is None or self.release_behavior == "not_found":
                raise HoldNotFound()
            if hold["status"] != "RELEASED":
                hold["status"] = "RELEASED"
                self.releases.append(hold_id)
            self.crash.tick("availability.release_hold.after")
            return "RELEASED"


class FakePayment:
    def __init__(
        self,
        clock: FakeClock,
        crash: CrashPlan | None = None,
        create_statuses: list | None = None,
        lookup_statuses: list | None = None,
        refund_behavior: str = "ok",
    ) -> None:
        self.clock = clock
        self.crash = crash or CrashPlan()
        self.create_statuses = create_statuses or ["SUCCEEDED"]
        self.lookup_statuses = lookup_statuses or ["SUCCEEDED"]
        self.refund_behavior = refund_behavior
        self.charges: dict[str, PaymentInfo] = {}
        self.create_calls: list[str] = []
        self.lookup_calls: list[str] = []
        self.refunds: list[uuid.UUID] = []
        self.lock = threading.RLock()

    @staticmethod
    def _payment_id(key: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, key)

    def _next(self, statuses: list):
        return statuses.pop(0) if len(statuses) > 1 else statuses[0]

    def create(
        self,
        reservation_id: uuid.UUID,
        amount_cents: int,
        currency: str,
        method: str,
        token: str,
        simulate: str,
    ) -> PaymentInfo:
        with self.lock:
            self.crash.tick("payment.create.before")
            key = str(reservation_id)
            self.create_calls.append(key)
            existing = self.charges.get(key)
            if existing is not None:
                self.crash.tick("payment.create.after")
                return existing
            outcome = self._next(self.create_statuses)
            if isinstance(outcome, Exception):
                raise outcome
            if outcome == "RAISE_AMBIGUOUS":
                self.charges[key] = PaymentInfo(
                    id=self._payment_id(key), status="UNKNOWN"
                )
                raise DependencyUnavailable("timeout del proveedor", ambiguous=True)
            if outcome == "RAISE_DOWN":
                raise DependencyUnavailable("conexión rechazada", ambiguous=False)
            info = PaymentInfo(id=self._payment_id(key), status=outcome)
            if outcome in ("SUCCEEDED", "DECLINED", "UNKNOWN"):
                self.charges[key] = info
            self.crash.tick("payment.create.after")
            return info

    def get_by_reservation(self, reservation_id: uuid.UUID) -> PaymentInfo:
        with self.lock:
            self.crash.tick("payment.get_by_reservation.before")
            key = str(reservation_id)
            self.lookup_calls.append(key)
            existing = self.charges.get(key)
            if existing is None:
                raise PaymentNotFound()
            outcome = self._next(self.lookup_statuses)
            if isinstance(outcome, Exception):
                raise outcome
            if outcome == "RAISE_AMBIGUOUS":
                raise DependencyUnavailable("timeout", ambiguous=True)
            if outcome != existing.status:
                existing = PaymentInfo(id=existing.id, status=outcome)
                self.charges[key] = existing
            self.crash.tick("payment.get_by_reservation.after")
            return existing

    def refund(self, payment_id: uuid.UUID) -> PaymentInfo:
        with self.lock:
            self.crash.tick("payment.refund.before")
            if self.refund_behavior == "down":
                raise DependencyUnavailable("payment caído", ambiguous=True)
            match = next((v for v in self.charges.values() if v.id == payment_id), None)
            if match is None or self.refund_behavior == "not_found":
                raise PaymentNotFound()
            if match.status not in ("SUCCEEDED", "REFUNDED"):
                raise InvalidState("no se puede reembolsar")
            if match.status != "REFUNDED":
                self.charges[
                    next(k for k, v in self.charges.items() if v.id == payment_id)
                ] = PaymentInfo(id=payment_id, status="REFUNDED")
                self.refunds.append(payment_id)
            self.crash.tick("payment.refund.after")
            return PaymentInfo(id=payment_id, status="REFUNDED")


class FakeCustomer:
    def __init__(self, clock: FakeClock, crash: CrashPlan | None = None, found=True, behavior="ok"):
        self.clock = clock
        self.crash = crash or CrashPlan()
        self.found = found
        self.behavior = behavior

    def exists(self, customer_id: uuid.UUID) -> bool:
        self.crash.tick("customer.exists.before")
        if self.behavior == "down":
            raise DependencyUnavailable("customer caído", ambiguous=False)
        self.crash.tick("customer.exists.after")
        return self.found


class FakeHotel:
    def __init__(
        self,
        clock: FakeClock,
        crash: CrashPlan | None = None,
        hotel_id: uuid.UUID | None = None,
        price_cents: int = 10000,
        behavior: str = "ok",
    ):
        self.clock = clock
        self.crash = crash or CrashPlan()
        self.hotel_id = hotel_id
        self.price_cents = price_cents
        self.behavior = behavior

    def get_room(self, room_id: uuid.UUID) -> RoomInfo:
        self.crash.tick("hotel.get_room.before")
        if self.behavior == "down":
            raise DependencyUnavailable("hotel caído", ambiguous=False)
        if self.behavior == "missing":
            raise RoomNotFound()
        self.crash.tick("hotel.get_room.after")
        return RoomInfo(hotel_id=self.hotel_id, price_cents=self.price_cents)


def make_service(
    clock: FakeClock | None = None,
    crash: CrashPlan | None = None,
    config: SagaConfig | None = None,
    sleep=None,
    **fake_kwargs,
):
    clock = clock or FakeClock()
    crash = crash or CrashPlan()
    repo = FakeRepo(clock, crash)
    availability = FakeAvailability(
        clock, crash, **fake_kwargs.get("availability", {})
    )
    payment = FakePayment(clock, crash, **fake_kwargs.get("payment", {}))
    customer = FakeCustomer(clock, crash, **fake_kwargs.get("customer", {}))
    hotel = FakeHotel(clock, crash, **fake_kwargs.get("hotel", {}))
    service = ReservationService(
        repo,
        availability,
        payment,
        customer,
        hotel,
        clock,
        config or TEST_CONFIG,
        jitter=lambda: 1.0,
        sleep=sleep or clock_sleep(clock),
    )
    return service, repo, availability, payment, customer, hotel, clock, crash



