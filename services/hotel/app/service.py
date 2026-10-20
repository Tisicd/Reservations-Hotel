import uuid

from .errors import HotelNotFound, ValidationError
from .models import HotelStore


def _text(value: str, field: str, maximum: int = 120) -> str:
    value = (value or "").strip()
    if not 1 <= len(value) <= maximum:
        raise ValidationError(f"{field} debe tener entre 1 y {maximum} caracteres")
    return value


class HotelService:
    def __init__(self, store: HotelStore):
        self.store = store

    def create_hotel(self, hotel_id, name: str, city: str) -> tuple[dict, bool]:
        return self.store.create_hotel(
            hotel_id or uuid.uuid4(), _text(name, "name"), _text(city, "city")
        )

    def create_room(
        self,
        hotel_id,
        room_id,
        name: str,
        capacity: int,
        price_per_night_cents: int,
        currency: str,
    ) -> tuple[dict, bool]:
        name = _text(name, "name")
        if not 1 <= capacity <= 10:
            raise ValidationError("capacity debe estar entre 1 y 10")
        if price_per_night_cents <= 0:
            raise ValidationError("price_per_night_cents debe ser mayor que 0")
        if currency != "USD":
            raise ValidationError("currency no soportada")
        return self.store.create_room(
            room_id or uuid.uuid4(),
            hotel_id,
            name,
            capacity,
            price_per_night_cents,
            currency,
        )

    def list_hotels(self, city: str | None = None) -> list[dict]:
        return self.store.list_hotels(city.strip() if city else None)

    def get_hotel(self, hotel_id) -> dict:
        hotel = self.store.get_hotel(hotel_id)
        if hotel is None:
            raise HotelNotFound("hotel no encontrado")
        return hotel

    def get_room(self, room_id) -> dict:
        room = self.store.get_room(room_id)
        if room is None:
            raise HotelNotFound("habitación no encontrada")
        return room

    def ping(self) -> None:
        self.store.ping()
