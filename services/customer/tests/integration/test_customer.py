import concurrent.futures

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.errors import EmailExists
from app.main import create_app
from app.models import CustomerStore
from app.service import CustomerService


@pytest.fixture()
def client(store):
    return TestClient(create_app(CustomerService(store)))


def test_crear_y_obtener(client):
    response = client.post("/customers", json={"name": "Ana", "email": "Ana@Example.com"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ana@example.com"
    fetched = client.get(f"/customers/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Ana"


def test_email_duplicado_case_insensitive_409(client):
    first = client.post("/customers", json={"name": "Ana", "email": "ana@example.com"})
    assert first.status_code == 201
    second = client.post("/customers", json={"name": "Otra", "email": "ANA@EXAMPLE.COM"})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EMAIL_EXISTS"


def test_concurrencia_un_solo_cliente(store):
    service = CustomerService(store)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [
            pool.submit(service.create, f"Cliente {index}", "race@example.com")
            for index in range(10)
        ]
    results = []
    for future in futures:
        try:
            results.append(("ok", future.result()))
        except EmailExists:
            results.append(("conflict", None))
    assert [kind for kind, _ in results].count("ok") == 1
    assert [kind for kind, _ in results].count("conflict") == 9
    with store.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM customers")).scalar_one() == 1


def test_email_invalido_422(client):
    response = client.post("/customers", json={"name": "Ana", "email": "ana@"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_inexistente_404(client):
    response = client.get("/customers/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_fail_closed_si_la_bd_no_responde():
    broken = create_engine(
        "postgresql+psycopg://customer:x@127.0.0.1:1/customer_db",
        connect_args={"connect_timeout": 1},
    )
    with TestClient(create_app(CustomerService(CustomerStore(broken)))) as test_client:
        assert test_client.get("/ready").status_code == 503
        response = test_client.post("/customers", json={"name": "Ana", "email": "a@b.co"})
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "5"
