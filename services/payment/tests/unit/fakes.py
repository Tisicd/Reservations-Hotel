import dataclasses
import datetime as dt
import uuid

from app.application.ports import APPROVED, ChargeResult, ProviderTimeout, ProviderUnavailable
from app.domain.errors import IdempotencyKeyReused, InvalidState, PaymentNotFound
from app.domain.payment import (
    FAILED_TECHNICAL,
    INITIATED,
    REFUNDED,
    SUCCEEDED,
    UNKNOWN,
    Payment,
)


class FakeProvider:
    def __init__(self, outcome=APPROVED, raise_after=None):
        self.outcome = outcome
        self.raise_after = raise_after
        self.charges: dict[str, ChargeResult] = {}
        self.calls: list[tuple[str, str]] = []
        self.refunded: set[str] = set()

    def charge(self, key, amount_cents, currency, token, simulate):
        self.calls.append((key, simulate))
        if simulate == "error_before_processing":
            raise ProviderUnavailable("sin procesar")
        result = self.charges.get(key)
        if result is None:
            result = ChargeResult(self.outcome, f"sim_{key}")
            self.charges[key] = result
        if self.raise_after is not None:
            exc = self.raise_after
            self.raise_after = None
            raise exc
        if simulate in ("process_then_drop_response", "slow"):
            raise ProviderTimeout("sin respuesta")
        return result

    def lookup(self, key):
        return self.charges.get(key)

    def refund(self, key):
        self.refunded.add(key)


class FakeRepo:
    def __init__(self):
        self.by_key: dict[str, Payment] = {}
        self.by_id: dict[uuid.UUID, Payment] = {}
        self.attempts: list[dict] = []
        self.ledger: list[dict] = []

    def _save(self, payment):
        self.by_key[payment.idempotency_key] = payment
        self.by_id[payment.id] = payment
        return payment

    def insert_initiated(
        self, reservation_id, idempotency_key, request_hash, amount_cents, currency, method
    ):
        if idempotency_key in self.by_key:
            return self.by_key[idempotency_key], False
        if any(p.reservation_id == reservation_id for p in self.by_key.values()):
            raise IdempotencyKeyReused("ya existe un pago para esta reserva")
        now = dt.datetime.now(dt.UTC)
        payment = Payment(
            id=uuid.uuid4(),
            reservation_id=reservation_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            amount_cents=amount_cents,
            currency=currency,
            method=method,
            status=INITIATED,
            provider_ref=None,
            created_at=now,
            updated_at=now,
        )
        return self._save(payment), True

    def get(self, payment_id):
        if payment_id not in self.by_id:
            raise PaymentNotFound()
        return self.by_id[payment_id]

    def get_by_reservation(self, reservation_id):
        for p in self.by_key.values():
            if p.reservation_id == reservation_id:
                return p
        raise PaymentNotFound()

    def start_attempt(self, payment_id, simulate):
        attempt_id = uuid.uuid4()
        self.attempts.append({"id": attempt_id, "payment_id": payment_id, "outcome": None})
        return attempt_id

    def finish_attempt(self, attempt_id, outcome, error):
        for a in self.attempts:
            if a["id"] == attempt_id:
                a["outcome"] = outcome
                a["error"] = error

    def record_result(self, payment_id, from_statuses, to_status, provider_ref=None):
        p = self.by_id[payment_id]
        if p.status not in from_statuses:
            return None
        updated = dataclasses.replace(
            p,
            status=to_status,
            provider_ref=provider_ref if provider_ref is not None else p.provider_ref,
            updated_at=dt.datetime.now(dt.UTC),
        )
        self._save(updated)
        if to_status == SUCCEEDED and not self._has_ledger(payment_id, "CHARGE"):
            self.ledger.append({"payment_id": payment_id, "kind": "CHARGE"})
        return updated

    def _has_ledger(self, payment_id, kind):
        return any(x["payment_id"] == payment_id and x["kind"] == kind for x in self.ledger)

    def refund(self, payment_id):
        p = self.by_id[payment_id]
        if p.status == REFUNDED:
            return p
        if p.status != SUCCEEDED:
            raise InvalidState(f"no se puede reembolsar desde {p.status}")
        updated = dataclasses.replace(p, status=REFUNDED, updated_at=dt.datetime.now(dt.UTC))
        self._save(updated)
        if not self._has_ledger(payment_id, "REFUND"):
            self.ledger.append({"payment_id": payment_id, "kind": "REFUND"})
        return updated

    def list_unknown(self, min_age_seconds, limit):
        return [p for p in self.by_key.values() if p.status == UNKNOWN][:limit]

    def ping(self):
        return None


__all__ = ["FakeProvider", "FakeRepo", "FAILED_TECHNICAL"]
