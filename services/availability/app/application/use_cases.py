import datetime as dt
import uuid

from app.domain.date_range import DateRange
from app.domain.errors import ValidationError
from app.domain.hold import Hold

from .ports import InventoryStore


class AvailabilityService:
    def __init__(
        self,
        store: InventoryStore,
        hold_default_ttl_seconds: int = 600,
        hold_max_ttl_seconds: int = 3600,
        max_nights: int = 30,
        max_units: int = 10,
    ) -> None:
        self.store = store
        self.hold_default_ttl = hold_default_ttl_seconds
        self.hold_max_ttl = hold_max_ttl_seconds
        self.max_nights = max_nights
        self.max_units = max_units

    def _range(self, check_in: dt.date, check_out: dt.date) -> DateRange:
        return DateRange(check_in, check_out, self.max_nights)

    def search(self, hotel_id: uuid.UUID, check_in: dt.date, check_out: dt.date) -> list[dict]:
        rng = self._range(check_in, check_out)
        return self.store.search(hotel_id, rng.check_in, rng.check_out)

    def put_inventory(
        self,
        hotel_id: uuid.UUID,
        room_id: uuid.UUID,
        check_in: dt.date,
        check_out: dt.date,
        total: int,
    ) -> None:
        rng = self._range(check_in, check_out)
        if total < 0:
            raise ValidationError("total no puede ser negativo")
        self.store.put_inventory(hotel_id, room_id, rng.check_in, rng.check_out, total)

    def create_hold(
        self,
        hold_id: uuid.UUID,
        room_id: uuid.UUID,
        check_in: dt.date,
        check_out: dt.date,
        units: int,
        ttl_seconds: int | None = None,
    ) -> tuple[Hold, bool]:
        rng = self._range(check_in, check_out)
        if not (1 <= units <= self.max_units):
            raise ValidationError(f"units debe estar entre 1 y {self.max_units}")
        ttl = ttl_seconds if ttl_seconds is not None else self.hold_default_ttl
        if not (1 <= ttl <= self.hold_max_ttl):
            raise ValidationError(f"ttl debe estar entre 1 y {self.hold_max_ttl}")
        return self.store.create_hold(hold_id, room_id, rng.check_in, rng.check_out, units, ttl)

    def extend_hold(self, hold_id: uuid.UUID, ttl_seconds: int) -> Hold:
        if not (1 <= ttl_seconds <= self.hold_max_ttl):
            raise ValidationError(f"ttl debe estar entre 1 y {self.hold_max_ttl}")
        return self.store.extend_hold(hold_id, ttl_seconds)

    def confirm_hold(self, hold_id: uuid.UUID) -> Hold:
        return self.store.confirm_hold(hold_id)

    def release_hold(self, hold_id: uuid.UUID) -> Hold:
        return self.store.release_hold(hold_id)

    def get_hold(self, hold_id: uuid.UUID) -> Hold:
        return self.store.get_hold(hold_id)

    def expire_due(self, limit: int) -> list[uuid.UUID]:
        return self.store.expire_due(limit)

    def ping(self) -> None:
        self.store.ping()
