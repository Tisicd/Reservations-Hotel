import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Response

from app.application.use_cases import AvailabilityService

from .deps import get_service
from .schemas import ExtendBody, HoldCreateBody, InventoryPutBody

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(service: AvailabilityService = Depends(get_service)) -> dict:
    service.ping()
    return {"status": "ready"}


@router.get("/availability")
def search(
    hotel_id: uuid.UUID,
    check_in: dt.date,
    check_out: dt.date,
    service: AvailabilityService = Depends(get_service),
) -> dict:
    rooms = service.search(hotel_id, check_in, check_out)
    return {
        "hotel_id": str(hotel_id),
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "rooms": [{"room_id": str(r["room_id"]), "available": r["available"]} for r in rooms],
    }


@router.put("/inventory/{room_id}")
def put_inventory(
    room_id: uuid.UUID,
    body: InventoryPutBody,
    service: AvailabilityService = Depends(get_service),
) -> dict:
    service.put_inventory(body.hotel_id, room_id, body.check_in, body.check_out, body.total)
    return {"status": "ok"}


@router.post("/holds")
def create_hold(
    body: HoldCreateBody,
    response: Response,
    service: AvailabilityService = Depends(get_service),
) -> dict:
    hold, created = service.create_hold(
        body.hold_id, body.room_id, body.check_in, body.check_out, body.units, body.ttl_seconds
    )
    response.status_code = 201 if created else 200
    return {
        "hold_id": str(hold.hold_id),
        "status": hold.status,
        "expires_at": hold.expires_at.isoformat(),
    }


@router.post("/holds/{hold_id}/extend")
def extend(
    hold_id: uuid.UUID,
    body: ExtendBody,
    service: AvailabilityService = Depends(get_service),
) -> dict:
    hold = service.extend_hold(hold_id, body.ttl_seconds)
    return {"expires_at": hold.expires_at.isoformat()}


@router.post("/holds/{hold_id}/confirm")
def confirm(hold_id: uuid.UUID, service: AvailabilityService = Depends(get_service)) -> dict:
    hold = service.confirm_hold(hold_id)
    return {"status": hold.status}


@router.post("/holds/{hold_id}/release")
def release(hold_id: uuid.UUID, service: AvailabilityService = Depends(get_service)) -> dict:
    hold = service.release_hold(hold_id)
    return {"status": hold.status}


@router.get("/holds/{hold_id}")
def get_hold(hold_id: uuid.UUID, service: AvailabilityService = Depends(get_service)) -> dict:
    hold = service.get_hold(hold_id)
    return {
        "hold_id": str(hold.hold_id),
        "room_id": str(hold.room_id),
        "check_in": hold.check_in.isoformat(),
        "check_out": hold.check_out.isoformat(),
        "units": hold.units,
        "status": hold.status,
        "expires_at": hold.expires_at.isoformat(),
    }
