"""E2E del flujo completo (escenarios 1-7 del cierre F1).

`make e2e` levanta el stack dev, re-siembra de forma idempotente y ejecuta
    los escenarios (los tests de integración truncan las BDs y borran la
    semilla; `make test` detiene los workers para no interferir).

El escenario 8 (simulación deshabilitada -> 422) se omite: el reservation-service
trata el 422 del proveedor como error técnico reintentable, así que exigiría
reiniciar payment con PAYMENT_SIMULATION_ENABLED=false y un cambio de código
fuera del alcance del cierre. Ver docs/resultados/F1.md.
"""

import concurrent.futures
import datetime as dt
import uuid

import pytest

# Base aleatoria por ejecucion: repetir `make e2e` no reutiliza inventario
# ni reservas confirmadas de una corrida anterior.
BASE = dt.date.today() + dt.timedelta(days=400 + uuid.uuid4().int % 3000)


def _today(offset: int) -> dt.date:
    return BASE + dt.timedelta(days=offset)


@pytest.fixture(scope="module")
def race_customers(stack):
    return [
        stack.create_customer(f"e2e-{stack.run_id}-race-{index}@example.com")
        for index in range(10)
    ]


def test_01_camino_feliz(stack, invariants):
    day = _today(10)
    stack.put_inventory(day, 5)
    before = stack.available(day)
    response = stack.create_reservation(
        f"e2e-{stack.run_id}-s1", day, stack.customers[0]["id"]
    )
    assert response.status_code in (200, 201)
    reservation = response.json()
    assert reservation["status"] == "CONFIRMED"
    assert reservation["amount_cents"] == stack.room["price_per_night_cents"]
    assert reservation["nights"] == 1
    payment = stack.payment_of(reservation["id"])
    assert payment is not None and payment["status"] == "SUCCEEDED"
    assert stack.available(day) == before - 1
    chain = [(event["from"], event["to"]) for event in stack.events(reservation["id"])]
    assert chain == [
        (None, "RECEIVED"),
        ("RECEIVED", "HELD"),
        ("HELD", "PAYMENT_PENDING"),
        ("PAYMENT_PENDING", "PAID"),
        ("PAID", "CONFIRMED"),
    ]
    invariants()


def test_02_pago_rechazado_libera_inventario(stack, invariants):
    day = _today(12)
    stack.put_inventory(day, 5)
    before = stack.available(day)
    response = stack.create_reservation(
        f"e2e-{stack.run_id}-s2", day, stack.customers[1]["id"], simulate="decline"
    )
    assert response.status_code == 201
    reservation = response.json()
    assert reservation["status"] == "CANCELLED"
    assert reservation["status_reason"] == "DECLINED"
    payment = stack.payment_of(reservation["id"])
    assert payment is not None and payment["status"] == "DECLINED"
    assert stack.available(day) == before
    invariants()


def test_03_doble_envio_idempotente(stack, invariants):
    for rep in range(10):
        day = _today(20 + rep)
        stack.put_inventory(day, 5)
        before = stack.available(day)
        key = f"e2e-{stack.run_id}-dup-{rep}"

        def send(_):
            return stack.create_reservation(key, day, stack.customers[0]["id"])

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            responses = list(pool.map(send, range(5)))
        assert all(response.status_code in (200, 201, 202) for response in responses)
        ids = {response.json()["id"] for response in responses}
        assert len(ids) == 1, f"respuestas con ids distintos: {ids}"
        reservation_id = ids.pop()
        final = stack.wait_status(reservation_id, {"CONFIRMED"})
        assert final["status"] == "CONFIRMED"
        payment = stack.payment_of(reservation_id)
        assert payment is not None and payment["status"] == "SUCCEEDED"
        assert stack.available(day) == before - 1
    invariants()


def test_04_carrera_por_la_ultima_unidad(stack, race_customers, invariants):
    for rep in range(10):
        day = _today(35 + rep)
        stack.put_inventory(day, 1)
        assert stack.available(day) == 1

        def race(index):
            return stack.create_reservation(
                f"e2e-{stack.run_id}-race-{rep}-{index}",
                day,
                race_customers[index]["id"],
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            responses = list(pool.map(race, range(10)))
        reservations = [response.json() for response in responses]
        confirmed = [item for item in reservations if item["status"] == "CONFIRMED"]
        rejected = [
            item for item in reservations if item["status"] == "REJECTED_NO_INVENTORY"
        ]
        assert len(confirmed) == 1, f"confirmadas: {len(confirmed)}"
        assert len(rejected) == 9, f"rechazadas: {len(rejected)}"
        assert stack.payment_of(confirmed[0]["id"])["status"] == "SUCCEEDED"
        assert all(stack.payment_of(item["id"]) is None for item in rejected)
        assert stack.available(day) == 0
    invariants()


def test_05_pago_ambiguo_se_reconcilia(stack, invariants):
    day = _today(14)
    stack.put_inventory(day, 5)
    before = stack.available(day)
    response = stack.create_reservation(
        f"e2e-{stack.run_id}-s5",
        day,
        stack.customers[0]["id"],
        simulate="process_then_drop_response",
    )
    assert response.status_code in (200, 201, 202)
    reservation_id = response.json()["id"]
    final = stack.wait_status(reservation_id, {"CONFIRMED"}, timeout=120)
    assert final["status"] == "CONFIRMED"
    payment = stack.payment_of(reservation_id)
    assert payment is not None and payment["status"] == "SUCCEEDED"
    assert stack.available(day) == before - 1
    invariants()


def test_06_cancelacion_reembolsa_y_libera(stack, invariants):
    day = _today(16)
    stack.put_inventory(day, 5)
    before = stack.available(day)
    created = stack.create_reservation(
        f"e2e-{stack.run_id}-s6", day, stack.customers[1]["id"]
    )
    assert created.status_code in (200, 201)
    reservation_id = created.json()["id"]
    assert created.json()["status"] == "CONFIRMED"

    response = stack.cancel(reservation_id)
    assert response.status_code in (200, 202)
    final = stack.wait_status(reservation_id, {"CANCELLED"}, timeout=60)
    assert final["status"] == "CANCELLED"
    payment = stack.payment_of(reservation_id)
    assert payment is not None and payment["status"] == "REFUNDED"
    assert stack.available(day) == before
    chain = [(event["from"], event["to"]) for event in stack.events(reservation_id)]
    assert ("CONFIRMED", "CANCELLING") in chain
    assert ("CANCELLING", "CANCELLED") in chain
    invariants()


def test_07_datos_inconsistentes_no_crean_reserva(stack, invariants):
    day = _today(18)
    missing_customer = str(uuid.uuid4())
    response = stack.create_reservation(
        f"e2e-{stack.run_id}-s7a", day, missing_customer
    )
    assert response.status_code == 404
    assert stack.list_reservations(missing_customer) == []

    customer_id = stack.customers[0]["id"]
    before = len(stack.list_reservations(customer_id))
    response = stack.create_reservation(
        f"e2e-{stack.run_id}-s7b", day, customer_id, hotel_id=str(uuid.uuid4())
    )
    assert response.status_code == 422
    after = len(stack.list_reservations(customer_id))
    assert after == before
    invariants()
