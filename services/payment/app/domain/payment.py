import dataclasses
import datetime as dt
import hashlib
import json
import uuid

from .errors import InvalidState

INITIATED = "INITIATED"
SUCCEEDED = "SUCCEEDED"
DECLINED = "DECLINED"
FAILED_TECHNICAL = "FAILED_TECHNICAL"
UNKNOWN = "UNKNOWN"
REFUNDED = "REFUNDED"

ALLOWED_TRANSITIONS = {
    INITIATED: {SUCCEEDED, DECLINED, FAILED_TECHNICAL, UNKNOWN},
    UNKNOWN: {SUCCEEDED, DECLINED, FAILED_TECHNICAL},
    FAILED_TECHNICAL: {INITIATED},
    SUCCEEDED: {REFUNDED},
    DECLINED: set(),
    REFUNDED: set(),
}

SIMULATION_MODES = {
    "ok",
    "decline",
    "error_before_processing",
    "process_then_drop_response",
    "slow",
}


@dataclasses.dataclass(frozen=True)
class Payment:
    id: uuid.UUID
    reservation_id: uuid.UUID
    idempotency_key: str
    request_hash: str
    amount_cents: int
    currency: str
    method: str
    status: str
    provider_ref: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    def can_transition_to(self, status: str) -> bool:
        return status in ALLOWED_TRANSITIONS.get(self.status, set())

    def transition(self, status: str, provider_ref: str | None = None) -> "Payment":
        if not self.can_transition_to(status):
            raise InvalidState(f"transición inválida {self.status} -> {status}")
        return dataclasses.replace(
            self,
            status=status,
            provider_ref=provider_ref if provider_ref is not None else self.provider_ref,
        )


def request_hash(
    reservation_id: uuid.UUID,
    amount_cents: int,
    currency: str,
    method: str,
    token: str,
) -> str:
    payload = {
        "reservation_id": str(reservation_id),
        "amount_cents": amount_cents,
        "currency": currency,
        "method": method,
        "token": token,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
