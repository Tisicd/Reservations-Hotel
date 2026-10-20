import uuid

from fastapi import APIRouter, Depends, Header, Response

from app.application.use_cases import PaymentService
from app.domain.errors import ValidationError
from app.domain.payment import Payment

from .deps import get_service
from .schemas import PaymentCreateBody

router = APIRouter()


def _representation(payment: Payment) -> dict:
    body = {
        "id": str(payment.id),
        "reservation_id": str(payment.reservation_id),
        "status": payment.status,
        "updated_at": payment.updated_at.isoformat(),
    }
    if payment.provider_ref is not None:
        body["provider_ref"] = payment.provider_ref
    return body


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(service: PaymentService = Depends(get_service)) -> dict:
    service.ping()
    return {"status": "ready"}


@router.post("/payments")
def create_payment(
    body: PaymentCreateBody,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    service: PaymentService = Depends(get_service),
) -> dict:
    if not idempotency_key:
        raise ValidationError("Idempotency-Key es obligatoria")
    payment, created = service.create_payment(
        idempotency_key=idempotency_key,
        reservation_id=body.reservation_id,
        amount_cents=body.amount_cents,
        currency=body.currency,
        method=body.method,
        token=body.token,
        simulate=body.simulate,
    )
    response.status_code = 201 if created else 200
    return _representation(payment)


@router.get("/payments")
def get_by_reservation(
    reservation_id: uuid.UUID,
    service: PaymentService = Depends(get_service),
) -> dict:
    return _representation(service.get_by_reservation(reservation_id))


@router.get("/payments/{payment_id}")
def get_payment(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_service),
) -> dict:
    return _representation(service.get_payment(payment_id))


@router.post("/payments/{payment_id}/refund")
def refund(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_service),
) -> dict:
    payment = service.refund_payment(payment_id)
    return {"id": str(payment.id), "status": payment.status}
