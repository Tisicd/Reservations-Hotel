from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

PENDING = "PENDING"
SENT = "SENT"
FAILED = "FAILED"

EVENT_TYPES = frozenset({"reservation.confirmed", "reservation.cancelled"})


@dataclass(frozen=True)
class Notification:
    id: uuid.UUID
    event_id: uuid.UUID
    type: str
    reservation_id: uuid.UUID
    customer_id: uuid.UUID
    payload: dict
    status: str
    attempts: int
    created_at: dt.datetime
    next_attempt_at: dt.datetime
    sent_at: dt.datetime | None = None
    last_error: str | None = None
