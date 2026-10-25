import uuid

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel

from .auth_service import AuthService
from .errors import InvalidCredentials
from .service import CustomerService

router = APIRouter()


class CustomerCreate(BaseModel):
    name: str
    email: str


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


def get_service(request: Request) -> CustomerService:
    return request.app.state.service


def get_auth(request: Request) -> AuthService:
    return request.app.state.auth


def _bearer(authorization: str | None) -> str:
    if not authorization:
        raise InvalidCredentials("credenciales inválidas")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise InvalidCredentials("credenciales inválidas")
    return token.strip()


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


@router.post("/auth/register", status_code=201)
def register(
    body: RegisterIn,
    response: Response,
    auth: AuthService = Depends(get_auth),
) -> dict:
    customer = auth.register(body.name, body.email, body.password)
    response.headers["Cache-Control"] = "no-store"
    return customer


@router.post("/auth/login")
def login(
    body: LoginIn,
    response: Response,
    auth: AuthService = Depends(get_auth),
) -> dict:
    result = auth.login(body.email, body.password)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/auth/logout", status_code=204)
def logout(
    response: Response,
    authorization: str | None = Header(default=None),
    auth: AuthService = Depends(get_auth),
) -> Response:
    token = _bearer(authorization)
    auth.logout(token)
    response.status_code = 204
    return response


@router.get("/auth/me")
def me(
    authorization: str | None = Header(default=None),
    auth: AuthService = Depends(get_auth),
) -> dict:
    return auth.me(_bearer(authorization))


@router.get("/auth/validate", status_code=204)
def validate(
    response: Response,
    authorization: str | None = Header(default=None),
    auth: AuthService = Depends(get_auth),
) -> Response:
    customer = auth.validate(_bearer(authorization))
    if customer is None:
        raise InvalidCredentials("credenciales inválidas")
    response.status_code = 204
    response.headers["X-User-Id"] = str(customer["id"])
    return response
