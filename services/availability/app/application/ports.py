import datetime as dt
import uuid
from typing import Protocol

from app.domain.hold import Hold


class InventoryStore(Protocol):
    def put_inventory(
        self,
        hotel_id: uuid.UUID,
        room_id: uuid.UUID,
        check_in: dt.date,
        check_out: dt.date,
        total: int,
    ) -> None: ...

    def search(self, hotel_id: uuid.UUID, check_in: dt.date, check_out: dt.date) -> list[dict]: ...

    def create_hold(
        self,
        hold_id: uuid.UUID,
        room_id: uuid.UUID,
        check_in: dt.date,
        check_out: dt.date,
        units: int,
        ttl_seconds: int,
    ) -> tuple[Hold, bool]: ...

    def extend_hold(self, hold_id: uuid.UUID, ttl_seconds: int) -> Hold: ...

    def confirm_hold(self, hold_id: uuid.UUID) -> Hold: ...

    def release_hold(self, hold_id: uuid.UUID) -> Hold: ...

    def get_hold(self, hold_id: uuid.UUID) -> Hold: ...

    def expire_due(self, limit: int) -> list[uuid.UUID]: ...

    def ping(self) -> None: ...
