import uuid

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from .service import HotelService

router = APIRouter()


class HotelCreate(BaseModel):
    id: uuid.UUID | None = None
    name: str
    city: str


class RoomCreate(BaseModel):
    id: uuid.UUID | None = None
    name: str
    capacity: int
    price_per_night_cents: int
    currency: str = "USD"


def get_service(request: Request) -> HotelService:
    return request.app.state.service


def _created(response: Response, created: bool) -> None:
    response.status_code = 201 if created else 200


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(service: HotelService = Depends(get_service)) -> dict:
    service.ping()
    return {"status": "ready"}


@router.post("/hotels")
def create_hotel(
    body: HotelCreate,
    response: Response,
    service: HotelService = Depends(get_service),
) -> dict:
    hotel, created = service.create_hotel(body.id, body.name, body.city)
    _created(response, created)
    return hotel


@router.get("/hotels")
def list_hotels(
    city: str | None = None, service: HotelService = Depends(get_service)
) -> list[dict]:
    return service.list_hotels(city)


@router.get("/hotels/{hotel_id}")
def get_hotel(
    hotel_id: uuid.UUID, service: HotelService = Depends(get_service)
) -> dict:
    return service.get_hotel(hotel_id)


@router.post("/hotels/{hotel_id}/rooms")
def create_room(
    hotel_id: uuid.UUID,
    body: RoomCreate,
    response: Response,
    service: HotelService = Depends(get_service),
) -> dict:
    room, created = service.create_room(
        hotel_id,
        body.id,
        body.name,
        body.capacity,
        body.price_per_night_cents,
        body.currency,
    )
    _created(response, created)
    return room


@router.get("/rooms/{room_id}")
def get_room(room_id: uuid.UUID, service: HotelService = Depends(get_service)) -> dict:
    return service.get_room(room_id)
