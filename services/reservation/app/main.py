import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.config import load_settings
from app.logging import configure_logging, request_id_var
from app.wiring import build

from .api.errors import register_error_handlers
from .api.routes import router

logger = logging.getLogger("reservation.access")


def create_app(service=None) -> FastAPI:
    wiring = None
    if service is None:
        settings = load_settings()
        configure_logging(settings.log_level)
        wiring = build(settings)
        service = wiring.service

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        if wiring is not None:
            wiring.close()

    app = FastAPI(title="reservation-service", version="0.1.0", lifespan=lifespan)
    app.state.service = service
    app.state.wiring = wiring

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
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
