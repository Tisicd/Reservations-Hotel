import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import (
    ConcurrentModification,
    CustomerNotFound,
    DependencyUnavailable,
    DomainError,
    Forbidden,
    IdempotencyKeyReused,
    IllegalTransition,
    InvalidState,
    ReservationNotFound,
    RoomNotFound,
    ValidationError,
)

logger = logging.getLogger("reservation.errors")

_MAP = {
    ValidationError: (422, "VALIDATION_ERROR"),
    IdempotencyKeyReused: (422, "IDEMPOTENCY_KEY_REUSED"),
    CustomerNotFound: (404, "NOT_FOUND"),
    RoomNotFound: (404, "NOT_FOUND"),
    ReservationNotFound: (404, "NOT_FOUND"),
    InvalidState: (409, "INVALID_STATE"),
    IllegalTransition: (409, "INVALID_STATE"),
    ConcurrentModification: (409, "CONCURRENT_MODIFICATION"),
    DependencyUnavailable: (503, "DEPENDENCY_UNAVAILABLE"),
    Forbidden: (403, "FORBIDDEN"),
}


def _payload(request_id: str | None, code: str, message: str, details=None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details or {},
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError):
        request_id = getattr(request.state, "request_id", None)
        status, code = _MAP.get(type(exc), (500, "INTERNAL_ERROR"))
        logger.warning(
            "error de dominio: %s",
            code,
            extra={"request_id": request_id},
            exc_info=(status == 500),
        )
        headers = {"Retry-After": "1"} if status == 503 else None
        return JSONResponse(
            status_code=status,
            content=_payload(request_id, code, str(exc) or code),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content=_payload(
                request_id,
                "VALIDATION_ERROR",
                "cuerpo de la petición inválido",
                {"errors": exc.errors()},
            ),
        )
