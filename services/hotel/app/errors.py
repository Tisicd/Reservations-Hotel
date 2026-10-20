class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status_code = 400


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    status_code = 422


class HotelNotFound(DomainError):
    code = "NOT_FOUND"
    status_code = 404


class IdConflict(DomainError):
    code = "ID_CONFLICT"
    status_code = 409


class DependencyUnavailable(DomainError):
    code = "DEPENDENCY_UNAVAILABLE"
    status_code = 503


def register_error_handlers(app):
    from fastapi.responses import JSONResponse

    @app.exception_handler(DomainError)
    async def handle_domain_error(request, exc: DomainError):
        headers = {"Retry-After": "5"} if exc.status_code == 503 else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc)}},
            headers=headers,
        )
