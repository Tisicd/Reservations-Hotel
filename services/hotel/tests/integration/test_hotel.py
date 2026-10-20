import concurrent.futures

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app
from app.models import HotelStore
from app.service import HotelService


@pytest.fixture()
def client(store):
    return TestClient(create_app(HotelService(store)))


def _hotel(client, hotel_id=None, name="Hotel Quito", city="Quito"):
    body = {"name": name, "city": city}
    if hotel_id is not None:
        body["id"] = str(hotel_id)
    return client.post("/hotels", json=body)


def test_alta_listado_y_detalle(client):
    hotel = _hotel(client)
    assert hotel.status_code == 201
    listing = client.get("/hotels", params={"city": "Quito"})
    assert [item["id"] for item in listing.json()] == [hotel.json()["id"]]
    assert client.get("/hotels", params={"city": "Cuenca"}).json() == []
    detail = client.get(f"/hotels/{hotel.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["rooms"] == []


def test_alta_idempotente_y_conflicto(client):
    hotel_id = "2b6f0f0e-0000-4000-8000-000000000001"
    assert _hotel(client, hotel_id).status_code == 201
    assert _hotel(client, hotel_id).status_code == 200
    conflict = _hotel(client, hotel_id, city="Guayaquil")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "ID_CONFLICT"


def test_habitaciones(client):
    hotel_id = _hotel(client).json()["id"]
    room_id = "2b6f0f0e-0000-4000-8000-000000000002"
    body = {"id": room_id, "name": "101", "capacity": 2, "price_per_night_cents": 4500}
    assert client.post(f"/hotels/{hotel_id}/rooms", json=body).status_code == 201
    assert client.post(f"/hotels/{hotel_id}/rooms", json=body).status_code == 200
    conflict = client.post(
        f"/hotels/{hotel_id}/rooms", json={**body, "capacity": 3}
    )
    assert conflict.status_code == 409
    detail = client.get(f"/hotels/{hotel_id}").json()
    assert [room["id"] for room in detail["rooms"]] == [room_id]
    assert client.get(f"/rooms/{room_id}").json()["price_per_night_cents"] == 4500


def test_habitacion_sin_hotel_404(client):
    response = client.post(
        "/hotels/00000000-0000-0000-0000-000000000000/rooms",
        json={"name": "101", "capacity": 2, "price_per_night_cents": 4500},
    )
    assert response.status_code == 404


def test_concurrencia_alta_idempotente(store):
    service = HotelService(store)
    hotel_id = "2b6f0f0e-0000-4000-8000-000000000003"
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(
            pool.map(
                lambda _: service.create_hotel(hotel_id, "Hotel Quito", "Quito"), range(10)
            )
        )
    assert sum(1 for _, created in results if created) == 1
    assert all(str(item["id"]) == hotel_id for item, _ in results)
    with store.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM hotels")).scalar_one() == 1


def test_fail_closed_si_la_bd_no_responde():
    broken = create_engine(
        "postgresql+psycopg://hotel:x@127.0.0.1:1/hotel_db",
        connect_args={"connect_timeout": 1},
    )
    with TestClient(create_app(HotelService(HotelStore(broken)))) as test_client:
        assert test_client.get("/ready").status_code == 503
        response = test_client.post("/hotels", json={"name": "H", "city": "Quito"})
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "5"
