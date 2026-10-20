import datetime as dt
import uuid

from pydantic import BaseModel, Field


class PaymentIn(BaseModel):
    method: str = "card"
    token: str = "tok_demo"
    simulate: str = "ok"


class ReservationCreate(BaseModel):
    customer_id: uuid.UUID
    hotel_id: uuid.UUID
    room_id: uuid.UUID
    check_in: dt.date
    check_out: dt.date
    payment: PaymentIn = Field(default_factory=PaymentIn)
