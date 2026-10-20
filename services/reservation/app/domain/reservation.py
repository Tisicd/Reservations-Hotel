import dataclasses
import datetime as dt
import hashlib
import json
import uuid

SIMULATION_MODES = {
    "ok",
    "decline",
    "error_before_processing",
    "process_then_drop_response",
    "slow",
}

REASON_DECLINED = "DECLINED"
REASON_TECHNICAL = "TECHNICAL"
REASON_NO_INVENTORY = "NO_INVENTORY"
REASON_HOLD_LOST = "HOLD_LOST"
REASON_HOLD_LOST_REFUNDED = "HOLD_LOST_REFUNDED"
REASON_RECONCILE_TIMEOUT = "RECONCILE_TIMEOUT"
REASON_CONFIRM_TIMEOUT = "CONFIRM_TIMEOUT"
REASON_REFUND_TIMEOUT = "REFUND_TIMEOUT"


@dataclasses.dataclass(frozen=True)
class Reservation:
    id: uuid.UUID
    idempotency_key: str
    request_hash: str
    customer_id: uuid.UUID
    hotel_id: uuid.UUID
    room_id: uuid.UUID
    check_in: dt.date
    check_out: dt.date
    nights: int
    amount_cents: int
    currency: str
    payment_method: str
    payment_token: str
    payment_simulate: str
    status: str
    status_reason: str | None = None
    payment_id: uuid.UUID | None = None
    payment_status: str | None = None
    attempts: int = 0
    next_attempt_at: dt.datetime | None = None
    phase_started_at: dt.datetime | None = None
    locked_until: dt.datetime | None = None
    version: int = 0
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


def request_hash(
    customer_id: uuid.UUID,
    hotel_id: uuid.UUID,
    room_id: uuid.UUID,
    check_in: dt.date,
    check_out: dt.date,
    method: str,
    token: str,
) -> str:
    payload = {
        "customer_id": str(customer_id),
        "hotel_id": str(hotel_id),
        "room_id": str(room_id),
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "payment": {"method": method, "token": token},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
