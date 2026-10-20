from fastapi import Request

from app.application.use_cases import ReservationService


def get_service(request: Request) -> ReservationService:
    return request.app.state.service
