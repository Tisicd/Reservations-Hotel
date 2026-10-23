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
import time
import uuid

import pytest

# Base aleatoria por ejecucion: repetir `make e2e` no reutiliza inventario
# ni reservas confirmadas de una corrida anterior. Rango amplio y disjunto
# del de test_notifications (evita colisiones al repetir el E2E muchas veces).
BASE = dt.date.today() + dt.timedelta(days=2_000_000 + int(time.time()) % 400_000)


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

        confirmed = []
        rejected = []
        others = []
        for response in responses:
            if response.status_code in (200, 201, 202):
                item = response.json()
                if item["status"] == "CONFIRMED":
                    confirmed.append(item)
                else:
                    rejected.append(item)
            else:
                # 429 del gateway (limit_req/limit_conn) o 502/503/504
                # transitorios: la solicitud no confirma. Se valida el
                # estado final por consulta, no por el cuerpo de la respuesta.
                others.append(response.status_code)

        # El 429/504 puede ocurrir por el runner (más lento) sin que haya
        # sobreventa; el estado final se sondea con tiempo límite.
        finals: list[dict] = []
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            finals = stack.confirmed_on(race_customers, day)
            if len(finals) == 1 and stack.available(day, admin=True) == 0:
                break
            time.sleep(0.5)

        assert not [s for s in others if s not in (429, 502, 503, 504)], \
            f"respuestas inesperadas: {others}"
        assert len(confirmed) <= 1, f"confirmadas en respuestas: {len(confirmed)}"
        assert len(finals) == 1, (
            f"esperaba 1 CONFIRMED final y hay {len(finals)}; "
            f"status HTTP={[r.status_code for r in responses]}")
        assert stack.available(day, admin=True) == 0
        assert stack.payment_of(finals[0]["id"])["status"] == "SUCCEEDED"
        assert all(stack.payment_of(item["id"]) is None for item in rejected)
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
