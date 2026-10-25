import logging
import time

import sqlalchemy as sa
from fastapi import FastAPI, Request

from .api import router
from .auth_service import AuthService
from .config import Settings, load_settings
from .errors import register_error_handlers
from .logging import configure_logging, new_request_id, request_id_var
from .models import CustomerStore
from .service import CustomerService

logger = logging.getLogger("customer")

REQUEST_ID_HEADER = "X-Request-ID"


def make_engine(settings: Settings) -> sa.Engine:
    return sa.create_engine(
        settings.db_url,
        pool_size=settings.db_pool_size,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
    )


def create_app(service: CustomerService | None = None,
               auth: AuthService | None = None) -> FastAPI:
    settings = None
    if service is None:
        settings = load_settings()
        configure_logging(settings.log_level)
        service = CustomerService(CustomerStore(make_engine(settings)))
    if auth is None:
        if settings is None:
            settings = load_settings()
        auth = AuthService(service.store, settings)

    app = FastAPI(title="customer-service", version="1.0.0")
    app.state.service = service
    app.state.auth = auth

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "detail": f"{time.perf_counter() - started:.3f}s",
                },
            )
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            request_id_var.reset(token)

    register_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
