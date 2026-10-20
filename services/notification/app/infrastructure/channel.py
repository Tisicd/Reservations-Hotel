import logging

from app.domain.notification import Notification

logger = logging.getLogger("notification.channel")


class LogChannel:
    """Canal simulado: registra la notificación y siempre acepta."""

    def send(self, notification: Notification) -> None:
        logger.info(
            "notificacion %s para reserva %s (cliente %s)",
            notification.type,
            notification.reservation_id,
            notification.customer_id,
            extra={
                "reservation_id": str(notification.reservation_id),
                "notification_id": str(notification.id),
            },
        )
