import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import get_service
from app.errors import DependencyUnavailable, HotelNotFound, IdConflict
from app.main import app
from app.service import HotelService


def _hotel(hotel_id, name="Hotel Quito", city="Quito", created=True):
    return (
        {
            "id": hotel_id,
            "name": name,
            "city": city,
            "created_at": dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        },
        created,
    )


class FakeStore:
    def __init__(self):
        self.hotels = {}
        self.rooms = {}

    def create_hotel(self, hotel_id, name, city):
        existing = self.hotels.get(hotel_id)
        if existing is not None:
            if existing["name"] != name or existing["city"] != city:
                raise IdConflict("id repetido")
            return existing, False
        hotel, _ = _hotel(hotel_id, name, city)
        self.hotels[hotel_id] = hotel
        return hotel, True

    def create_room(self, room_id, hotel_id, name, capacity, price, currency):
        if hotel_id not in self.hotels:
            raise HotelNotFound("hotel no encontrado")
        existing = self.rooms.get(room_id)
        if existing is not None:
            if existing["hotel_id"] != hotel_id or existing["name"] != name:
                raise IdConflict("id repetido")
            return existing, False
        room = {
            "id": room_id,
            "hotel_id": hotel_id,
            "name": name,
            "capacity": capacity,
            "price_per_night_cents": price,
            "currency": currency,
            "created_at": dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        }
        self.rooms[room_id] = room
        return room, True

    def list_hotels(self, city=None):
        return [h for h in self.hotels.values() if city is None or h["city"] == city]

    def get_hotel(self, hotel_id):
        hotel = self.hotels.get(hotel_id)
        if hotel is None:
            return None
        return {
            **hotel,
            "rooms": [r for r in self.rooms.values() if r["hotel_id"] == hotel_id],
        }

    def get_room(self, room_id):
        return self.rooms.get(room_id)

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
    app.dependency_overrides[get_service] = lambda: HotelService(store)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_503_si_la_bd_no_responde():
    app.dependency_overrides[get_service] = lambda: HotelService(DownStore())
    with TestClient(app) as test_client:
        response = test_client.get("/ready")
    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"


def test_crear_hotel_201(client):
    response = client.post("/hotels", json={"name": "Hotel Quito", "city": "Quito"})
    assert response.status_code == 201
    uuid.UUID(response.json()["id"])


def test_alta_idempotente_devuelve_200(client):
    hotel_id = str(uuid.uuid4())
    body = {"id": hotel_id, "name": "Hotel Quito", "city": "Quito"}
    assert client.post("/hotels", json=body).status_code == 201
    assert client.post("/hotels", json=body).status_code == 200


def test_id_con_contenido_distinto_409(client):
    hotel_id = str(uuid.uuid4())
    client.post("/hotels", json={"id": hotel_id, "name": "Hotel Quito", "city": "Quito"})
    response = client.post(
        "/hotels", json={"id": hotel_id, "name": "Hotel Quito", "city": "Guayaquil"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ID_CONFLICT"


def test_crear_habitacion(client):
    hotel = client.post("/hotels", json={"name": "H", "city": "Quito"}).json()
    response = client.post(
        f"/hotels/{hotel['id']}/rooms",
        json={"name": "101", "capacity": 2, "price_per_night_cents": 5000},
    )
    assert response.status_code == 201
    assert response.json()["currency"] == "USD"


def test_habitacion_de_hotel_inexistente_404(client):
    response = client.post(
        f"/hotels/{uuid.uuid4()}/rooms",
        json={"name": "101", "capacity": 2, "price_per_night_cents": 5000},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "room",
    [
        {"name": "101", "capacity": 0, "price_per_night_cents": 5000},
        {"name": "101", "capacity": 11, "price_per_night_cents": 5000},
        {"name": "101", "capacity": 2, "price_per_night_cents": 0},
        {"name": "101", "capacity": 2, "price_per_night_cents": 5000, "currency": "EUR"},
    ],
)
def test_validacion_habitacion_422(client, room):
    hotel = client.post("/hotels", json={"name": "H", "city": "Quito"}).json()
    response = client.post(f"/hotels/{hotel['id']}/rooms", json=room)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_listado_y_detalle(client):
    hotel = client.post("/hotels", json={"name": "H", "city": "Quito"}).json()
    client.post(
        f"/hotels/{hotel['id']}/rooms",
        json={"name": "101", "capacity": 2, "price_per_night_cents": 5000},
    )
    listing = client.get("/hotels", params={"city": "Quito"}).json()
    assert [item["id"] for item in listing] == [hotel["id"]]
    detail = client.get(f"/hotels/{hotel['id']}").json()
    assert len(detail["rooms"]) == 1
    assert client.get(f"/rooms/{detail['rooms'][0]['id']}").status_code == 200


def test_inexistentes_404(client):
    assert client.get(f"/hotels/{uuid.uuid4()}").status_code == 404
    assert client.get(f"/rooms/{uuid.uuid4()}").status_code == 404


def test_propaga_x_request_id(client):
    response = client.get("/health", headers={"X-Request-ID": "req-9"})
    assert response.headers["X-Request-ID"] == "req-9"
