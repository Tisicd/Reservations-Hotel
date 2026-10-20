import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class InventoryPutBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    hotel_id: uuid.UUID
    check_in: dt.date = Field(alias="from")
    check_out: dt.date = Field(alias="to")
    total: int


class HoldCreateBody(BaseModel):
    hold_id: uuid.UUID
    room_id: uuid.UUID
    check_in: dt.date
    check_out: dt.date
    units: int
    ttl_seconds: int | None = None


class ExtendBody(BaseModel):
    ttl_seconds: int
