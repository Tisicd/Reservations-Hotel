import logging
import os
import pathlib
import signal
import time

from app.application.use_cases import PaymentService
from app.config import load_settings
from app.infrastructure.db.engine import make_engine
from app.infrastructure.db.repository import SqlPaymentRepository
from app.infrastructure.provider_sim import SimulatedProvider
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
    logger = logging.getLogger("payment.worker")
    engine = make_engine(settings.db_url, settings.db_pool_size, settings.db_pool_timeout)
    service = PaymentService(
        SqlPaymentRepository(engine),
        SimulatedProvider(
            engine,
            timeout_seconds=settings.provider_timeout_seconds,
            slow_seconds=settings.provider_slow_seconds,
        ),
        simulation_enabled=settings.payment_simulation_enabled,
        reconcile_min_age_seconds=settings.reconcile_min_age_seconds,
    )
    running = True

    def stop(signum, frame):
        nonlocal running
        logger.info("señal recibida, terminando")
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while running:
        try:
            reconciled = service.reconcile_unknown(settings.reconcile_batch)
            if reconciled:
                logger.info("pagos UNKNOWN reconciliados: %d", reconciled)
        except Exception as e:  # noqa: BLE001
            logger.warning("error al reconciliar pagos: %s", e)
        _beat()
        time.sleep(settings.reconcile_interval_seconds)


if __name__ == "__main__":
    main()
