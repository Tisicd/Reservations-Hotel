from __future__ import annotations

import datetime as dt
import logging
import uuid

from app.application.ports import NotificationChannel, NotificationRepository
from app.domain.errors import ValidationError
from app.domain.notification import EVENT_TYPES, Notification

logger = logging.getLogger("notification.delivery")


class NotificationService:
    def __init__(
        self,
        repo: NotificationRepository,
        channel: NotificationChannel,
        max_attempts: int = 5,
        backoff_base_seconds: float = 1.0,
        backoff_max_seconds: float = 30.0,
        lease_seconds: int = 30,
    ) -> None:
        self.repo = repo
        self.channel = channel
        self.max_attempts = max_attempts
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_max_seconds = backoff_max_seconds
        self.lease_seconds = lease_seconds

    def ping(self) -> None:
        self.repo.ping()

    def create(
        self,
        event_id: uuid.UUID,
        type: str,
        reservation_id: uuid.UUID,
        customer_id: uuid.UUID,
        payload: dict | None = None,
    ) -> tuple[Notification, bool]:
        if type not in EVENT_TYPES:
            raise ValidationError(f"tipo de evento no soportado: {type}")
        return self.repo.insert_inbox(
            event_id, type, reservation_id, customer_id, payload or {}
        )

    def list_by_reservation(self, reservation_id: uuid.UUID) -> list[Notification]:
        return self.repo.list_by_reservation(reservation_id)

    def deliver_due(self, limit: int) -> int:
        claimed = self.repo.claim_due(limit, self.lease_seconds)
        sent = 0
        for notification in claimed:
            try:
                self.channel.send(notification)
            except Exception as exc:  # noqa: BLE001 - el canal es externo
                failed = notification.attempts >= self.max_attempts
                delay = min(
                    self.backoff_base_seconds * (2 ** max(notification.attempts - 1, 0)),
                    self.backoff_max_seconds,
                )
                retry_at = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=delay)
                self.repo.mark_retry(notification.id, failed, retry_at, str(exc)[:500])
                logger.warning(
                    "envio fallido (intento %d): %s",
                    notification.attempts,
                    exc,
                    extra={"reservation_id": str(notification.reservation_id)},
                )
            else:
                self.repo.mark_sent(notification.id)
                sent += 1
        return sent
