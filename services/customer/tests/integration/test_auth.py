import concurrent.futures
import hashlib
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth_service import AuthService
from app.config import Settings
from app.errors import EmailExists
from app.main import create_app
from app.service import CustomerService

PASSWORD = "Reserva-UCE-2026!"


def settings(**overrides) -> Settings:
    base = dict(
        db_host="127.0.0.1", db_port=5433, db_name="customer_db",
        db_user="customer", db_password="x", db_pool_size=5,
        db_pool_timeout=5, log_level="INFO",
        scrypt_n=1024, scrypt_r=8, scrypt_p=1,
        auth_session_ttl_seconds=60, login_max_failures=3,
        login_lock_seconds=1,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture()
def client(store):
    service = CustomerService(store)
    return TestClient(create_app(service, AuthService(store, settings())))


def register(client, email="Ana@Example.com", password=PASSWORD):
    return client.post("/auth/register", json={
        "name": "Ana Reservas", "email": email, "password": password})


def login(client, email="ana@example.com", password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_registro_login_me_validate_logout(store, client):
    created = register(client)
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "ana@example.com"
    assert "password" not in body
    assert "password_hash" not in body

    with store.engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, password_hash FROM customers WHERE email='ana@example.com'"
        )).one()
        assert row.password_hash.startswith("scrypt$1024$8$1$")
        assert PASSWORD not in row.password_hash

    logged = login(client)
    assert logged.status_code == 200
    assert logged.headers.get("Cache-Control") == "no-store"
    data = logged.json()
    token = data["access_token"]
    assert data["token_type"] == "Bearer"
    assert data["customer"]["id"] == str(row.id)

    with store.engine.connect() as conn:
        session = conn.execute(text(
            "SELECT token_hash FROM sessions WHERE customer_id=:id"
        ), {"id": row.id}).one()
        assert session.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert session.token_hash != token

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ana@example.com"

    validated = client.get(
        "/auth/validate", headers={"Authorization": f"Bearer {token}"})
    assert validated.status_code == 204
    assert validated.headers["X-User-Id"] == str(row.id)

    assert client.get(
        "/auth/me", headers={"Authorization": "Bearer invalido"}).status_code == 401
    assert client.get("/auth/me").status_code == 401
    assert client.get(
        "/auth/validate", headers={"Authorization": "Bearer invalido"}
    ).status_code == 401

    out = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert out.status_code == 204
    assert client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_duplicado_case_insensitive_409(client):
    assert register(client).status_code == 201
    duplicate = register(client, email="ANA@EXAMPLE.COM")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_EXISTS"


def test_registro_concurrente_un_solo_cliente(store):
    service = AuthService(store, settings())
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [
            pool.submit(service.register, f"Cliente {i}", "race-auth@example.com",
                        PASSWORD)
            for i in range(10)
        ]
    kinds = []
    for future in futures:
        try:
            future.result()
            kinds.append("ok")
        except EmailExists:
            kinds.append("conflict")
    assert kinds.count("ok") == 1
    assert kinds.count("conflict") == 9
    with store.engine.connect() as conn:
        assert conn.execute(text(
            "SELECT count(*) FROM customers WHERE email='race-auth@example.com'"
        )).scalar_one() == 1


def test_login_generico_bloqueo_y_desbloqueo(store, client):
    assert register(client).status_code == 201
    wrong = login(client, password="Otra-Clave-2026!")
    missing = login(client, email="nadie@example.com", password="Otra-Clave-2026!")
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    assert wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"

    for _ in range(2):
        assert login(client, password="Otra-Clave-2026!").status_code == 401
    # 3.er fallo -> bloqueo
    assert login(client, password="Otra-Clave-2026!").status_code == 401
    assert login(client).status_code == 401  # correcta, pero bloqueada
    time.sleep(1.2)
    assert login(client).status_code == 200

    with store.engine.connect() as conn:
        row = conn.execute(text(
            "SELECT failed_attempts, locked_until FROM customers "
            "WHERE email='ana@example.com'")).one()
        assert row.failed_attempts == 0
        assert row.locked_until is None


def test_sesion_expirada_y_limpieza(store, client):
    assert register(client).status_code == 201
    token = login(client).json()["access_token"]
    with store.engine.begin() as conn:
        conn.execute(text(
            "UPDATE sessions SET expires_at = now() - interval '1 second'"))
    assert client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert login(client).status_code == 200  # login limpia expiradas
    with store.engine.connect() as conn:
        assert conn.execute(text(
            "SELECT count(*) FROM sessions WHERE expires_at <= now()"
        )).scalar_one() == 0


def test_politica_debil_422(client):
    weak = client.post("/auth/register", json={
        "name": "Ana", "email": "weak@example.com", "password": "1234567890"})
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"
    short = client.post("/auth/register", json={
        "name": "Ana", "email": "short@example.com", "password": "corta"})
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "WEAK_PASSWORD"


def test_no_hay_password_ni_token_en_logs(client, caplog):
    with caplog.at_level("INFO", logger="customer"):
        assert register(client).status_code == 201
        token = login(client).json()["access_token"]
    text_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert PASSWORD not in text_logs
    assert token not in text_logs
