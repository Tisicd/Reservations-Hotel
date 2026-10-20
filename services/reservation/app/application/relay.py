from __future__ import annotations

import logging

from app.application.ports import NotificationSender, ReservationRepository
from app.domain.outbox import OutboxEvent

logger = logging.getLogger("reservation.relay")


class OutboxRelay:
    def __init__(
        self,
        repo: ReservationRepository,
        sender: NotificationSender,
        lease_seconds: int = 30,
        backoff_base_seconds: float = 0.5,
        backoff_max_seconds: float = 30.0,
    ) -> None:
        self.repo = repo
        self.sender = sender
        self.lease_seconds = lease_seconds
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_max_seconds = backoff_max_seconds

    def relay_due(self, limit: int) -> int:
        events = self.repo.claim_outbox(limit, self.lease_seconds)
        sent = 0
        for event in events:
            try:
                self.sender.send(event)
            except Exception as exc:  # noqa: BLE001 - la entrega es externa
                self.repo.reschedule_outbox(event.id, self._delay(event.attempts))
                logger.warning(
                    "entrega fallida (intento %d, evento %s): %s",
                    event.attempts,
                    event.id,
                    exc,
                    extra={"reservation_id": str(event.aggregate_id)},
                )
            else:
                self.repo.mark_outbox_sent(event.id)
                sent += 1
        return sent

    def _delay(self, attempts: int) -> float:
        return min(
            self.backoff_base_seconds * (2 ** max(attempts - 1, 0)),
            self.backoff_max_seconds,
        )

    @staticmethod
    def event_body(event: OutboxEvent) -> dict:
        return {
            "event_id": str(event.id),
            "type": event.type,
            "reservation_id": str(event.aggregate_id),
            "customer_id": event.payload["customer_id"],
            "payload": event.payload,
        }
