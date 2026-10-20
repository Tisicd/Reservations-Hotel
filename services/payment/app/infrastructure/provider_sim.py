import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.application.ports import (
    APPROVED,
    DECLINED,
    ChargeResult,
    ProviderTimeout,
    ProviderUnavailable,
)


class SimulatedProvider:
    """Proveedor simulado persistente: escribe en su propia conexión/transacción.

    El cargo sobrevive aunque la transacción de `payments` falle, igual que un
    proveedor real que ya procesó la operación.
    """

    def __init__(self, engine: Engine, timeout_seconds: float = 3, slow_seconds: float = 6) -> None:
        self.engine = engine
        self.timeout_seconds = timeout_seconds
        self.slow_seconds = slow_seconds

    def charge(
        self,
        idempotency_key: str,
        amount_cents: int,
        currency: str,
        token: str,
        simulate: str,
    ) -> ChargeResult:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            self._perform_charge, idempotency_key, amount_cents, currency, simulate
        )
        try:
            return future.result(timeout=self.timeout_seconds)
        except FuturesTimeout as e:
            raise ProviderTimeout("el proveedor no respondió a tiempo") from e
        finally:
            executor.shutdown(wait=False)

    def _perform_charge(
        self, idempotency_key: str, amount_cents: int, currency: str, simulate: str
    ) -> ChargeResult:
        if simulate == "error_before_processing":
            raise ProviderUnavailable("fallo antes de procesar el cobro")
        status = DECLINED if simulate == "decline" else APPROVED
        result = self._upsert(idempotency_key, amount_cents, currency, status)
        if simulate == "process_then_drop_response":
            raise ProviderTimeout("el cobro se registró pero se perdió la respuesta")
        if simulate == "slow":
            time.sleep(self.slow_seconds)
        return result

    def _upsert(
        self, idempotency_key: str, amount_cents: int, currency: str, status: str
    ) -> ChargeResult:
        ref = f"sim_{idempotency_key}"
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO sim_provider_charges "
                    "(idempotency_key, provider_ref, status, amount_cents, currency) "
                    "VALUES (:k, :ref, :status, :amount, :currency) "
                    "ON CONFLICT (idempotency_key) DO NOTHING"
                ),
                {
                    "k": idempotency_key,
                    "ref": ref,
                    "status": status,
                    "amount": amount_cents,
                    "currency": currency,
                },
            )
            row = conn.execute(
                text(
                    "SELECT status, provider_ref FROM sim_provider_charges "
                    "WHERE idempotency_key = :k"
                ),
                {"k": idempotency_key},
            ).one()
        return ChargeResult(status=row.status, provider_ref=row.provider_ref)

    def lookup(self, idempotency_key: str) -> ChargeResult | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT status, provider_ref FROM sim_provider_charges "
                    "WHERE idempotency_key = :k"
                ),
                {"k": idempotency_key},
            ).first()
        if row is None:
            return None
        return ChargeResult(status=row.status, provider_ref=row.provider_ref)

    def refund(self, idempotency_key: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE sim_provider_charges SET refunded_at = now() "
                    "WHERE idempotency_key = :k AND status = 'APPROVED' "
                    "AND refunded_at IS NULL"
                ),
                {"k": idempotency_key},
            )
