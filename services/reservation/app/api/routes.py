import uuid

from fastapi import APIRouter, Depends, Header, Response

from app.application.use_cases import CreateReservationCommand, ReservationService
from app.domain.errors import Forbidden, ReservationNotFound, ValidationError
from app.domain.reservation import Reservation
from app.domain.state_machine import CANCELLED, is_stable

from .deps import get_service
from .schemas import ReservationCreate

router = APIRouter()


def _representation(reservation: Reservation) -> dict:
    return {
        "id": str(reservation.id),
        "status": reservation.status,
        "status_reason": reservation.status_reason,
        "customer_id": str(reservation.customer_id),
        "hotel_id": str(reservation.hotel_id),
        "room_id": str(reservation.room_id),
        "check_in": reservation.check_in.isoformat(),
        "check_out": reservation.check_out.isoformat(),
        "nights": reservation.nights,
        "amount_cents": reservation.amount_cents,
        "currency": reservation.currency,
        "payment": {
            "payment_id": str(reservation.payment_id) if reservation.payment_id else None,
            "status": reservation.payment_status,
        },
        "created_at": reservation.created_at.isoformat() if reservation.created_at else None,
        "updated_at": reservation.updated_at.isoformat() if reservation.updated_at else None,
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(service: ReservationService = Depends(get_service)) -> dict:
    service.ping()
    return {"status": "ready"}


@router.post("/reservations", status_code=201)
def create_reservation(
    body: ReservationCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    service: ReservationService = Depends(get_service),
) -> dict:
    if not idempotency_key:
        raise ValidationError("Idempotency-Key es obligatoria")
    customer_id = body.customer_id
    if x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except (ValueError, TypeError) as exc:
            raise Forbidden("identidad inv?lida") from exc
        if body.customer_id != user_id:
            raise Forbidden("customer_id no corresponde a la sesi?n")
        customer_id = user_id
    reservation, replayed = service.create_reservation(
        idempotency_key,
        CreateReservationCommand(
            customer_id=customer_id,
            hotel_id=body.hotel_id,
            room_id=body.room_id,
            check_in=body.check_in,
            check_out=body.check_out,
            method=body.payment.method,
            token=body.payment.token,
            simulate=body.payment.simulate,
        ),
    )
    if replayed:
        response.status_code = 200
        response.headers["Idempotent-Replayed"] = "true"
    elif is_stable(reservation.status):
        response.status_code = 201
    else:
        response.status_code = 202
        response.headers["Location"] = f"/reservations/{reservation.id}"
    return _representation(reservation)


@router.get("/reservations")
def list_reservations(
    customer_id: uuid.UUID,
    service: ReservationService = Depends(get_service),
) -> list[dict]:
    return [_representation(r) for r in service.list_by_customer(customer_id)]


@router.get("/reservations/{reservation_id}")
def get_reservation(
    reservation_id: uuid.UUID,
    service: ReservationService = Depends(get_service),
) -> dict:
    return _representation(service.get_reservation(reservation_id))


@router.get("/reservations/{reservation_id}/events")
def get_events(
    reservation_id: uuid.UUID,
    service: ReservationService = Depends(get_service),
) -> list[dict]:
    return [
        {
            "from": event["from_status"],
            "to": event["to_status"],
            "reason": event["reason"],
            "at": event["at"].isoformat(),
        }
        for event in service.events(reservation_id)
    ]


@router.post("/reservations/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: uuid.UUID,
    response: Response,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    service: ReservationService = Depends(get_service),
) -> dict:
    if x_user_id:
        existing = service.get_reservation(reservation_id)
        if str(existing.customer_id) != x_user_id:
            raise ReservationNotFound("reserva no encontrada")
    reservation = service.cancel_reservation(reservation_id)
    if reservation.status != CANCELLED:
        response.status_code = 202
        response.headers["Location"] = f"/reservations/{reservation.id}"
    return _representation(reservation)
