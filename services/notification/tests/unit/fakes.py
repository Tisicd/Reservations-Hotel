from __future__ import annotations

import datetime as dt
import uuid

from app.domain.notification import Notification


class FakeRepo:
    def __init__(self) -> None:
        self.items: list[Notification] = []
        self.sent: list[uuid.UUID] = []

    def ping(self) -> None:
        return None

    def insert_inbox(self, event_id, type, reservation_id, customer_id, payload):
        for item in self.items:
            if item.event_id == event_id:
                return item, False
        now = dt.datetime.now(dt.UTC)
        item = Notification(
            id=uuid.uuid4(),
            event_id=event_id,
            type=type,
            reservation_id=reservation_id,
            customer_id=customer_id,
            payload=payload,
            status="PENDING",
            attempts=0,
            created_at=now,
            next_attempt_at=now,
        )
        self.items.append(item)
        return item, True

    def list_by_reservation(self, reservation_id):
        return [i for i in self.items if i.reservation_id == reservation_id]

    def claim_due(self, limit, lease_seconds):
        now = dt.datetime.now(dt.UTC)
        claimed = []
        for index, item in enumerate(self.items):
            if item.status != "PENDING" or item.next_attempt_at > now:
                continue
            claimed.append(
                Notification(
                    **{**item.__dict__, "attempts": item.attempts + 1}
                )
            )
            self.items[index] = claimed[-1]
            if len(claimed) >= limit:
                break
        return claimed

    def mark_sent(self, notification_id):
        self.sent.append(notification_id)
        self._set(notification_id, "SENT")

    def mark_retry(self, notification_id, failed, next_attempt_at, error):
        self._set(notification_id, "FAILED" if failed else "PENDING", error)

    def _set(self, notification_id, status, error=None):
        for index, item in enumerate(self.items):
            if item.id == notification_id:
                self.items[index] = Notification(
                    **{
                        **item.__dict__,
                        "status": status,
                        "last_error": error,
                    }
                )


class FlakyChannel:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.sent: list[uuid.UUID] = []

    def send(self, notification):
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError("canal caído")
        self.sent.append(notification.id)
