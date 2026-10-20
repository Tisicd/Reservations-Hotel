import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import get_service
from app.errors import DependencyUnavailable, EmailExists, ValidationError
from app.main import app
from app.service import CustomerService


class FakeStore:
    def __init__(self):
        self.items = {}

    def create(self, customer_id, name, email):
        if any(item["email"] == email for item in self.items.values()):
            raise EmailExists("email ya registrado")
        item = {
            "id": customer_id,
            "name": name,
            "email": email,
            "created_at": dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        }
        self.items[customer_id] = item
        return item

    def get(self, customer_id):
        return self.items.get(customer_id)

    def ping(self):
        pass


class DownStore(FakeStore):
    def ping(self):
        raise DependencyUnavailable("base de datos no disponible")


@pytest.fixture()
def store():
    return FakeStore()


@pytest.fixture()
def client(store):
    app.dependency_overrides[get_service] = lambda: CustomerService(store)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok(client):
    assert client.get("/ready").status_code == 200


def test_ready_503_si_la_bd_no_responde():
    app.dependency_overrides[get_service] = lambda: CustomerService(DownStore())
    with TestClient(app) as test_client:
        response = test_client.get("/ready")
    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


def test_crear_cliente_normaliza_y_devuelve_201(client):
    response = client.post(
        "/customers", json={"name": "  Ana Pérez ", "email": " ANA@Example.COM "}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ana Pérez"
    assert body["email"] == "ana@example.com"
    uuid.UUID(body["id"])


def test_email_duplicado_409(client, store):
    service = CustomerService(store)
    app.dependency_overrides[get_service] = lambda: service
    service.create("Ana", "ana@example.com")
    response = client.post("/customers", json={"name": "Otra", "email": "ANA@example.com"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_EXISTS"


def test_email_invalido_422(client):
    response = client.post("/customers", json={"name": "Ana", "email": "no-es-email"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_nombre_vacio_422(client):
    response = client.post("/customers", json={"name": "   ", "email": "ana@example.com"})
    assert response.status_code == 422


def test_obtener_cliente(client, store):
    service = CustomerService(store)
    app.dependency_overrides[get_service] = lambda: service
    created = service.create("Ana", "ana@example.com")
    response = client.get(f"/customers/{created['id']}")
    assert response.status_code == 200
    assert response.json()["email"] == "ana@example.com"


def test_obtener_cliente_inexistente_404(client):
    response = client.get(f"/customers/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_propaga_x_request_id(client):
    response = client.get("/health", headers={"X-Request-ID": "req-123"})
    assert response.headers["X-Request-ID"] == "req-123"


def test_servicio_valida_antes_de_escribir(store):
    service = CustomerService(store)
    with pytest.raises(ValidationError):
        service.create("Ana", "sin-arroba")
    assert store.items == {}
