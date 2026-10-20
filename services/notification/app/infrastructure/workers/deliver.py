import logging
import os
import pathlib
import signal
import time

from app.application.use_cases import NotificationService
from app.config import load_settings
from app.infrastructure.channel import LogChannel
from app.infrastructure.db.engine import make_engine
from app.infrastructure.db.repository import SqlNotificationRepository
from app.logging import configure_logging

HEARTBEAT = pathlib.Path(os.environ.get("WORKER_HEARTBEAT_FILE", "/tmp/heartbeat"))


def _beat() -> None:
    try:
        HEARTBEAT.write_text(str(time.time()))
    except OSError:
        pass


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("notification.worker")
    engine = make_engine(settings.db_url, settings.db_pool_size, settings.db_pool_timeout)
    service = NotificationService(
        SqlNotificationRepository(engine),
        LogChannel(),
        max_attempts=settings.max_attempts,
        backoff_base_seconds=settings.backoff_base_seconds,
        backoff_max_seconds=settings.backoff_max_seconds,
        lease_seconds=settings.lease_seconds,
    )
    running = True

    def stop(signum, frame):
        nonlocal running
        logger.info("señal recibida, terminando")
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        while running:
            try:
                sent = service.deliver_due(settings.worker_batch)
                if sent:
                    logger.info("notificaciones enviadas: %d", sent)
            except Exception as exc:  # noqa: BLE001
                logger.warning("error al entregar notificaciones: %s", exc)
            _beat()
            time.sleep(settings.worker_interval_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
