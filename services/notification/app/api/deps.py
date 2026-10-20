from fastapi import Request

from app.application.use_cases import NotificationService


def get_service(request: Request) -> NotificationService:
    return request.app.state.service
