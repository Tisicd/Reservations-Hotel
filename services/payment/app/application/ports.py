import dataclasses
import uuid
from typing import Protocol

from app.domain.payment import Payment


class ProviderUnavailable(Exception):
    """No se llegó a procesar el cobro (conexión rechazada antes de enviar)."""


class ProviderTimeout(Exception):
    """Se envió la operación y no se conoce el resultado."""


APPROVED = "APPROVED"
DECLINED = "DECLINED"


@dataclasses.dataclass(frozen=True)
class ChargeResult:
    status: str
    provider_ref: str


class PaymentProvider(Protocol):
    def charge(
        self,
        idempotency_key: str,
        amount_cents: int,
        currency: str,
        token: str,
        simulate: str,
    ) -> ChargeResult: ...

    def lookup(self, idempotency_key: str) -> ChargeResult | None: ...

    def refund(self, idempotency_key: str) -> None: ...


class PaymentRepository(Protocol):
    def ping(self) -> None: ...

    def insert_initiated(
        self,
        reservation_id: uuid.UUID,
        idempotency_key: str,
        request_hash: str,
        amount_cents: int,
        currency: str,
        method: str,
    ) -> tuple[Payment, bool]: ...

    def get(self, payment_id: uuid.UUID) -> Payment: ...

    def get_by_reservation(self, reservation_id: uuid.UUID) -> Payment: ...

    def start_attempt(self, payment_id: uuid.UUID, simulate: str) -> uuid.UUID: ...

    def finish_attempt(self, attempt_id: uuid.UUID, outcome: str, error: str | None) -> None: ...

    def record_result(
        self,
        payment_id: uuid.UUID,
        from_statuses: set[str],
        to_status: str,
        provider_ref: str | None = None,
    ) -> Payment | None: ...

    def refund(self, payment_id: uuid.UUID) -> Payment | None: ...

    def list_unknown(self, min_age_seconds: int, limit: int) -> list[Payment]: ...
