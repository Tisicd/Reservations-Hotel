import threading
import uuid

from sqlalchemy import text

EVENT = uuid.uuid4()
RESERVATION = uuid.uuid4()
CUSTOMER = uuid.uuid4()


def test_duplicado_devuelve_el_existente(repo):
    first, created = repo.insert_inbox(EVENT, "reservation.confirmed", RESERVATION, CUSTOMER, {})
    second, created_again = repo.insert_inbox(
        EVENT, "reservation.confirmed", RESERVATION, CUSTOMER, {}
    )

    assert created is True
    assert created_again is False
    assert first.id == second.id


def test_diez_hilos_mismo_evento_una_fila(repo, engine):
    results = []
    barrier = threading.Barrier(10)

    def worker():
        barrier.wait()
        results.append(repo.insert_inbox(EVENT, "reservation.confirmed", RESERVATION, CUSTOMER, {}))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(1 for _, created in results if created) == 1
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM notifications")).scalar_one() == 1


def test_api_deduplica_y_lista(client):
    body = {
        "event_id": str(EVENT),
        "type": "reservation.confirmed",
        "reservation_id": str(RESERVATION),
        "customer_id": str(CUSTOMER),
        "payload": {"hotel_id": str(uuid.uuid4())},
    }
    first = client.post("/notifications", json=body)
    second = client.post("/notifications", json=body)

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    listing = client.get("/notifications", params={"reservation_id": str(RESERVATION)})
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert items[0]["status"] == "PENDING"
    assert items[0]["event_id"] == str(EVENT)


def test_api_rechaza_tipo_desconocido(client):
    response = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "type": "reservation.refunded",
            "reservation_id": str(RESERVATION),
            "customer_id": str(CUSTOMER),
            "payload": {},
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_entrega_con_canal_log(repo, client):
    from app.application.use_cases import NotificationService
    from app.infrastructure.channel import LogChannel

    notification, _ = repo.insert_inbox(
        EVENT, "reservation.confirmed", RESERVATION, CUSTOMER, {}
    )
    assert notification.status == "PENDING"
    service = NotificationService(repo, LogChannel())
    assert service.deliver_due(10) == 1

    listing = client.get("/notifications", params={"reservation_id": str(RESERVATION)}).json()
    assert listing[0]["status"] == "SENT"
    assert listing[0]["attempts"] == 1
    assert listing[0]["sent_at"] is not None
