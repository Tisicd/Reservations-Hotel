import uuid

from app.domain.errors import (
    IdempotencyKeyReused,
    InvalidState,
    SimulationDisabled,
    ValidationError,
)
from app.domain.payment import (
    DECLINED,
    FAILED_TECHNICAL,
    INITIATED,
    REFUNDED,
    SIMULATION_MODES,
    SUCCEEDED,
    UNKNOWN,
    Payment,
    request_hash,
)

from .ports import (
    APPROVED,
    PaymentProvider,
    PaymentRepository,
    ProviderTimeout,
    ProviderUnavailable,
)


class PaymentService:
    def __init__(
        self,
        repo: PaymentRepository,
        provider: PaymentProvider,
        simulation_enabled: bool = False,
        reconcile_min_age_seconds: int = 2,
    ) -> None:
        self.repo = repo
        self.provider = provider
        self.simulation_enabled = simulation_enabled
        self.reconcile_min_age_seconds = reconcile_min_age_seconds

    def create_payment(
        self,
        idempotency_key: str,
        reservation_id: uuid.UUID,
        amount_cents: int,
        currency: str,
        method: str,
        token: str,
        simulate: str = "ok",
    ) -> tuple[Payment, bool]:
        if idempotency_key != str(reservation_id):
            raise ValidationError("Idempotency-Key debe ser igual a reservation_id")
        if amount_cents <= 0:
            raise ValidationError("amount_cents debe ser mayor que 0")
        if not currency:
            raise ValidationError("currency es obligatoria")
        if not method:
            raise ValidationError("method es obligatorio")
        if simulate not in SIMULATION_MODES:
            raise ValidationError(f"simulate inválido: {simulate}")
        if simulate != "ok" and not self.simulation_enabled:
            raise SimulationDisabled("la simulación está deshabilitada")

        request = request_hash(reservation_id, amount_cents, currency, method, token)
        payment, created = self.repo.insert_initiated(
            reservation_id=reservation_id,
            idempotency_key=idempotency_key,
            request_hash=request,
            amount_cents=amount_cents,
            currency=currency,
            method=method,
        )
        if created:
            return self._charge(payment, token, simulate), True

        if payment.request_hash != request:
            raise IdempotencyKeyReused("la clave se reutilizó con otro cuerpo")
        if payment.status in (SUCCEEDED, DECLINED, REFUNDED):
            return payment, False
        if payment.status == UNKNOWN:
            return self._reconcile(payment), False
        if payment.status == FAILED_TECHNICAL:
            # Reintento explícito con la misma clave (el proveedor es idempotente).
            self.repo.record_result(payment.id, {FAILED_TECHNICAL}, INITIATED)
        return self._charge(payment, token, simulate), False

    def _resolve(
        self,
        payment_id: uuid.UUID,
        from_statuses: set[str],
        to_status: str,
        provider_ref: str | None = None,
    ) -> Payment:
        updated = self.repo.record_result(payment_id, from_statuses, to_status, provider_ref)
        return updated if updated is not None else self.repo.get(payment_id)

    def _charge(self, payment: Payment, token: str, simulate: str) -> Payment:
        attempt_id = self.repo.start_attempt(payment.id, simulate)
        try:
            result = self.provider.charge(
                payment.idempotency_key,
                payment.amount_cents,
                payment.currency,
                token,
                simulate,
            )
        except ProviderUnavailable as e:
            self.repo.finish_attempt(attempt_id, "ERROR", str(e))
            return self._resolve(payment.id, {INITIATED, FAILED_TECHNICAL}, FAILED_TECHNICAL)
        except ProviderTimeout as e:
            self.repo.finish_attempt(attempt_id, "UNKNOWN", str(e))
            return self._resolve(payment.id, {INITIATED, FAILED_TECHNICAL}, UNKNOWN)

        self.repo.finish_attempt(attempt_id, result.status, None)
        if result.status == APPROVED:
            return self._resolve(
                payment.id, {INITIATED, FAILED_TECHNICAL}, SUCCEEDED, result.provider_ref
            )
        return self._resolve(
            payment.id, {INITIATED, FAILED_TECHNICAL}, DECLINED, result.provider_ref
        )

    def _reconcile(self, payment: Payment) -> Payment:
        looked = self.provider.lookup(payment.idempotency_key)
        if looked is None:
            return self._resolve(payment.id, {UNKNOWN}, FAILED_TECHNICAL)
        if looked.status == APPROVED:
            return self._resolve(payment.id, {UNKNOWN}, SUCCEEDED, looked.provider_ref)
        return self._resolve(payment.id, {UNKNOWN}, DECLINED, looked.provider_ref)

    def get_payment(self, payment_id: uuid.UUID) -> Payment:
        return self.repo.get(payment_id)

    def get_by_reservation(self, reservation_id: uuid.UUID) -> Payment:
        payment = self.repo.get_by_reservation(reservation_id)
        if payment.status == UNKNOWN:
            return self._reconcile(payment)
        return payment

    def refund_payment(self, payment_id: uuid.UUID) -> Payment:
        payment = self.repo.get(payment_id)
        if payment.status == REFUNDED:
            return payment
        if payment.status != SUCCEEDED:
            raise InvalidState(f"no se puede reembolsar desde {payment.status}")
        self.provider.refund(payment.idempotency_key)
        updated = self.repo.refund(payment_id)
        return updated if updated is not None else self.repo.get(payment_id)

    def reconcile_unknown(self, limit: int = 100) -> int:
        count = 0
        for payment in self.repo.list_unknown(self.reconcile_min_age_seconds, limit):
            self._reconcile(payment)
            count += 1
        return count

    def ping(self) -> None:
        self.repo.ping()
