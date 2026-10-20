import datetime as dt
import uuid
from dataclasses import dataclass

from .errors import HoldExpired, InvalidState

HELD = "HELD"
CONFIRMED = "CONFIRMED"
RELEASED = "RELEASED"
EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class Hold:
    hold_id: uuid.UUID
    room_id: uuid.UUID
    check_in: dt.date
    check_out: dt.date
    units: int
    status: str
    expires_at: dt.datetime
    created_at: dt.datetime
    updated_at: dt.datetime

    def is_expired(self, now: dt.datetime) -> bool:
        return self.status == HELD and self.expires_at <= now


def transition(hold: Hold, action: str, now: dt.datetime) -> str:
    """Devuelve el nuevo estado, o lanza un error de dominio. Pura."""
    if action == "confirm":
        if hold.status == CONFIRMED:
            return CONFIRMED  # idempotente
        if hold.status == HELD:
            if hold.expires_at <= now:
                raise HoldExpired("el hold expiró")
            return CONFIRMED
        if hold.status == EXPIRED:
            raise HoldExpired("el hold expiró")
        raise InvalidState(f"no se puede confirmar desde {hold.status}")
    if action == "release":
        if hold.status in (HELD, CONFIRMED):
            return RELEASED
        if hold.status in (RELEASED, EXPIRED):
            return hold.status  # sin cambios
        raise InvalidState(f"no se puede liberar desde {hold.status}")
    if action == "extend":
        if hold.status == HELD:
            if hold.expires_at <= now:
                raise HoldExpired("el hold expiró")
            return HELD
        raise InvalidState(f"no se puede extender desde {hold.status}")
    raise InvalidState(f"acción desconocida: {action}")
