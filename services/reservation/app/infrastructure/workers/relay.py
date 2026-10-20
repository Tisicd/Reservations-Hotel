import logging
import os
import pathlib
import signal
import time

from app.config import load_settings
from app.logging import configure_logging
from app.wiring import build_relay

HEARTBEAT = pathlib.Path(os.environ.get("WORKER_HEARTBEAT_FILE", "/tmp/heartbeat"))


def _beat() -> None:
    try:
        HEARTBEAT.write_text(str(time.time()))
    except OSError:
        pass


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("reservation.relay-worker")
    wiring = build_relay(settings)
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
                sent = wiring.relay.relay_due(settings.relay_batch)
                if sent:
                    logger.info("eventos entregados: %d", sent)
            except Exception as exc:  # noqa: BLE001
                logger.warning("error al entregar el outbox: %s", exc)
            _beat()
            time.sleep(settings.relay_interval_seconds)
    finally:
        wiring.close()


if __name__ == "__main__":
    main()