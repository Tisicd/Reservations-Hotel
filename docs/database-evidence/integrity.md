# Integridad referencial y lógica

Dos niveles distintos:

1. **Física**: FK reales dentro de cada base. PostgreSQL las garantiza.
2. **Lógica**: referencias entre bases de servicios distintos. **No hay FK**
   entre bases (ADR-0002); las garantiza la aplicación/saga y aquí solo se
   comprueban. Un huérfano lógico no rompe la base, pero es un dato a revisar.

## Integridad física (FK dentro de la misma base)

| Base | Constraint | Referencia | Huérfanos |
|---|---|---|---:|
| `customer_db` | `sessions_customer_id_fkey` | `sessions(customer_id) -> customers(id)` | OK |
| `hotel_db` | `rooms_hotel_id_fkey` | `rooms(hotel_id) -> hotels(id)` | OK |
| `payment_db` | `ledger_payment_id_fkey` | `ledger(payment_id) -> payments(id)` | OK |
| `payment_db` | `payment_attempts_payment_id_fkey` | `payment_attempts(payment_id) -> payments(id)` | OK |
| `reservation_db` | `reservation_events_reservation_id_fkey` | `reservation_events(reservation_id) -> reservations(id)` | OK |

## Integridad lógica (referencias entre bases)

Comprobación: ¿todo id referenciado existe en la base destino?

| Referencia | Origen | Destino | Huérfanos | Muestra |
|---|---|---|---:|---|
| Reserva -> cliente | `reservation_db.reservations.customer_id` | `customer_db.customers.id` | OK | - |
| Reserva -> hotel | `reservation_db.reservations.hotel_id` | `hotel_db.hotels.id` | OK | - |
| Reserva -> habitacion | `reservation_db.reservations.room_id` | `hotel_db.rooms.id` | OK | - |
| Reserva -> pago | `reservation_db.reservations.payment_id` | `payment_db.payments.id` | OK | - |
| Inventario -> habitacion | `availability_db.inventory.room_id` | `hotel_db.rooms.id` | REVISAR (2) | 9361e813-a0c2-4212-a5a4-05e42ae23d76, b3b66ea0-8a5e-48b4-8c8d-556c753d883b |
| Inventario -> hotel | `availability_db.inventory.hotel_id` | `hotel_db.hotels.id` | REVISAR (2) | 9147fbc8-f85e-4bc9-abbd-d8131f9eff57, 9e971d07-a170-48b1-acd6-01474ad65591 |
| Hold -> habitacion | `availability_db.holds.room_id` | `hotel_db.rooms.id` | REVISAR (2) | 9361e813-a0c2-4212-a5a4-05e42ae23d76, b3b66ea0-8a5e-48b4-8c8d-556c753d883b |
| Pago -> reserva | `payment_db.payments.reservation_id` | `reservation_db.reservations.id` | OK | - |
| Notificacion -> reserva | `notification_db.notifications.reservation_id` | `reservation_db.reservations.id` | REVISAR (1) | 447f501c-219b-46c9-8b54-a53a7089e966 |
| Notificacion -> cliente | `notification_db.notifications.customer_id` | `customer_db.customers.id` | REVISAR (1) | dc33a165-5ede-44b0-999d-b37c2aa00408 |
| Notificacion -> evento outbox | `notification_db.notifications.event_id` | `reservation_db.outbox.id` | REVISAR (1) | 60073fcb-c6f1-4a3e-a170-5690967c73a3 |

## Otras comprobaciones de dominio

| Comprobación | Resultado |
|---|---|
| reservas con hotel distinto al hotel de la habitacion | OK |
| filas de inventario cuyo room_id no existe o no coincide con hotel_id | REVISAR (2 pares room/hotel) |
| reservas con nights != check_out - check_in | 0 |
| pagos SUCCEEDED sin asiento CHARGE en ledger | 0 |
| notificaciones SENT sin sent_at | 0 |
| reservas sin evento inicial (from_status NULL) | 0 |

> Los huérfanos lógicos, si aparecen, son residuo de pruebas E2E que crean
> holds/inventario/notificaciones con ids de habitaciones o reservas que no
> pasan por el servicio dueño. No violan el esquema (no hay FK entre bases).
> Para una demo limpia: `make clean && make build && make up && make seed`.
