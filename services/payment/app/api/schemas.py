import uuid

from pydantic import BaseModel


class PaymentCreateBody(BaseModel):
    reservation_id: uuid.UUID
    amount_cents: int
    currency: str
    method: str
    token: str
    simulate: str = "ok"
