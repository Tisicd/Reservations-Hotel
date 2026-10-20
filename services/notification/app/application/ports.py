from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.notification import Notification


class NotificationRepository(Protocol):
    def ping(self) -> None: ...

    def insert_inbox(
        self,
        event_id: uuid.UUID,
        type: str,
        reservation_id: uuid.UUID,
        customer_id: uuid.UUID,
        payload: dict,
    ) -> tuple[Notification, bool]: ...

    def list_by_reservation(self, reservation_id: uuid.UUID) -> list[Notification]: ...

    def claim_due(self, limit: int, lease_seconds: int) -> list[Notification]: ...

    def mark_sent(self, notification_id: uuid.UUID) -> None: ...

    def mark_retry(
        self,
        notification_id: uuid.UUID,
        failed: bool,
        next_attempt_at: object,
        error: str,
    ) -> None: ...


class NotificationChannel(Protocol):
    def send(self, notification: Notification) -> None: ...
