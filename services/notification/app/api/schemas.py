import uuid

from pydantic import BaseModel, Field


class NotificationCreateBody(BaseModel):
    event_id: uuid.UUID
    type: str
    reservation_id: uuid.UUID
    customer_id: uuid.UUID
    payload: dict = Field(default_factory=dict)
