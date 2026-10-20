import logging
import os
import pathlib
import signal
import time

from app.config import load_settings
from app.infrastructure.db.engine import make_engine
from app.infrastructure.db.store import SqlInventoryStore
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
    logger = logging.getLogger("availability.worker")
    engine = make_engine(settings.db_url, settings.db_pool_size, settings.db_pool_timeout)
    store = SqlInventoryStore(engine)
    running = True

    def stop(signum, frame):
        nonlocal running
        logger.info("señal recibida, terminando")
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while running:
        try:
            released = store.expire_due(settings.expiry_batch)
            if released:
                logger.info("holds expirados liberados: %d", len(released))
        except Exception as e:  # noqa: BLE001
            logger.warning("error al expirar holds: %s", e)
        _beat()
        time.sleep(settings.expiry_interval_seconds)


if __name__ == "__main__":
    main()
