from fastapi import Request

from app.application.use_cases import AvailabilityService


def get_service(request: Request) -> AvailabilityService:
    return request.app.state.service
