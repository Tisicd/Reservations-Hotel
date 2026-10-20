from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class OutboxEvent:
    id: UUID
    aggregate_id: UUID
    type: str
    payload: dict
    attempts: int
