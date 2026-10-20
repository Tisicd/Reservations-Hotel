import uuid

from fastapi import APIRouter, Depends, Response

from app.application.use_cases import NotificationService
from app.domain.notification import Notification

from .deps import get_service
from .schemas import NotificationCreateBody

router = APIRouter()


def _list_item(notification: Notification) -> dict:
    return {
        "id": str(notification.id),
        "event_id": str(notification.event_id),
        "type": notification.type,
        "status": notification.status,
        "attempts": notification.attempts,
        "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(service: NotificationService = Depends(get_service)) -> dict:
    service.ping()
    return {"status": "ready"}


@router.post("/notifications")
def create_notification(
    body: NotificationCreateBody,
    response: Response,
    service: NotificationService = Depends(get_service),
) -> dict:
    notification, created = service.create(
        event_id=body.event_id,
        type=body.type,
        reservation_id=body.reservation_id,
        customer_id=body.customer_id,
        payload=body.payload,
    )
    response.status_code = 202 if created else 200
    return {"id": str(notification.id), "status": notification.status}


@router.get("/notifications")
def list_notifications(
    reservation_id: uuid.UUID,
    service: NotificationService = Depends(get_service),
) -> list[dict]:
    return [_list_item(n) for n in service.list_by_reservation(reservation_id)]
