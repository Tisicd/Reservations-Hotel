import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import (
    DependencyUnavailable,
    DomainError,
    HoldConflict,
    HoldExpired,
    HoldNotFound,
    InvalidDateRange,
    InvalidState,
    InventoryBelowCommitted,
    NoInventory,
    ValidationError,
)

logger = logging.getLogger("availability.errors")

_MAP = {
    NoInventory: (409, "NO_INVENTORY"),
    HoldConflict: (409, "HOLD_CONFLICT"),
    HoldExpired: (409, "HOLD_EXPIRED"),
    InvalidState: (409, "INVALID_STATE"),
    InventoryBelowCommitted: (409, "INVENTORY_BELOW_COMMITTED"),
    HoldNotFound: (404, "NOT_FOUND"),
    InvalidDateRange: (422, "VALIDATION_ERROR"),
    ValidationError: (422, "VALIDATION_ERROR"),
    DependencyUnavailable: (503, "DEPENDENCY_UNAVAILABLE"),
}


def _payload(request_id: str | None, code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id, "details": {}}}


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
