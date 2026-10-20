from fastapi import Request

from app.application.use_cases import PaymentService


def get_service(request: Request) -> PaymentService:
    return request.app.state.service
