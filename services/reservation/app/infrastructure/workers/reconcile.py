import logging
import os
import pathlib
import signal
import time

from app.config import load_settings
from app.logging import configure_logging
from app.wiring import build

HEARTBEAT = pathlib.Path(os.environ.get("WORKER_HEARTBEAT_FILE", "/tmp/heartbeat"))


def _beat() -> None:
    try:
        HEARTBEAT.write_text(str(time.time()))
    except OSError:
        pass


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("reservation.worker")
    wiring = build(settings)
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
                done = wiring.service.recover_due(settings.recovery_batch)
                if done:
                    logger.info("reservas procesadas: %d", len(done))
            except Exception as e:  # noqa: BLE001
                logger.warning("error al recuperar reservas: %s", e)
            _beat()
            time.sleep(settings.recovery_interval_seconds)
    finally:
        wiring.close()


if __name__ == "__main__":
    main()
