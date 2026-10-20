import logging
import uuid

from fastapi import FastAPI, Request

from app.application.use_cases import NotificationService
from app.config import load_settings
from app.infrastructure.channel import LogChannel
from app.infrastructure.db.engine import make_engine
from app.infrastructure.db.repository import SqlNotificationRepository
from app.logging import configure_logging

from .api.errors import register_error_handlers
from .api.routes import router

logger = logging.getLogger("notification.access")


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.db_url, settings.db_pool_size, settings.db_pool_timeout)
    service = NotificationService(
        SqlNotificationRepository(engine),
        LogChannel(),
        max_attempts=settings.max_attempts,
        backoff_base_seconds=settings.backoff_base_seconds,
        backoff_max_seconds=settings.backoff_max_seconds,
        lease_seconds=settings.lease_seconds,
    )

    app = FastAPI(title="notification-service", version="0.1.0")
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
