import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from .service import CustomerService

router = APIRouter()


class CustomerCreate(BaseModel):
    name: str
    email: str


def get_service(request: Request) -> CustomerService:
    return request.app.state.service


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(service: CustomerService = Depends(get_service)) -> dict:
    service.ping()
    return {"status": "ready"}


@router.post("/customers", status_code=201)
def create_customer(
    body: CustomerCreate, service: CustomerService = Depends(get_service)
) -> dict:
    return service.create(body.name, body.email)


@router.get("/customers/{customer_id}")
def get_customer(
    customer_id: uuid.UUID, service: CustomerService = Depends(get_service)
) -> dict:
    return service.get(customer_id)
