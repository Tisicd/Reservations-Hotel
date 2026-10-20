import logging
import uuid

from fastapi import FastAPI, Request

from app.application.use_cases import PaymentService
from app.config import load_settings
from app.infrastructure.db.engine import make_engine
from app.infrastructure.db.repository import SqlPaymentRepository
from app.infrastructure.provider_sim import SimulatedProvider
from app.logging import configure_logging

from .api.errors import register_error_handlers
from .api.routes import router

logger = logging.getLogger("payment.access")


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.db_url, settings.db_pool_size, settings.db_pool_timeout)
    repo = SqlPaymentRepository(engine)
    provider = SimulatedProvider(
        engine,
        timeout_seconds=settings.provider_timeout_seconds,
        slow_seconds=settings.provider_slow_seconds,
    )
    service = PaymentService(
        repo,
        provider,
        simulation_enabled=settings.payment_simulation_enabled,
        reconcile_min_age_seconds=settings.reconcile_min_age_seconds,
    )

    app = FastAPI(title="payment-service", version="0.1.0")
    app.state.service = service
    app.state.settings = settings

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={"request_id": request_id},
        )
        return response

    register_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
