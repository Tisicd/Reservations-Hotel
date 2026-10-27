# Resultados verificados de `queries.sql`

Ejecutado contra el stack dev real (PostgreSQL 16, `127.0.0.1:5433`) con:

```powershell
Get-Content -Raw docs/database-evidence/queries.sql |
  docker exec -i reservas-platform-postgres-1 psql -U postgres
```

Salida íntegra de esa ejecución (sin `ERROR`; `\c` confirma cada base). Los
emails van enmascarados y no se seleccionan `password_hash`, `token_hash`,
`payment_token`, `request_hash`, `provider_ref` ni payloads. Las fechas
corresponden a los datos de prueba presentes al momento de la inspección.

```text
Pager usage is off.
Border style is 2.
Null display is "(NULL)".
Timing is off.

############################################################
# customer_db - cuentas y sesiones                         #
############################################################
You are now connected to database "customer_db" as user "postgres".
-- Q1. Clientes (email enmascarado; sin hash de contrasena)
+--------------------------------------+----------+------------------+-------------------------------+-------------------------------+
|                  id                  |   name   |   email_masked   |          created_at           |         last_login_at         |
+--------------------------------------+----------+------------------+-------------------------------+-------------------------------+
| c67e3543-cea4-4845-a361-c833ad545354 | E2E Auth | e***@example.com | 2026-10-25 02:22:16.69585+00  | 2026-10-25 02:22:16.807499+00 |
| ccde209c-3d38-4f9c-8239-4951b40c9763 | E2E      | e***@example.com | 2026-10-25 02:22:05.346863+00 | (NULL)                        |
| 693d25b2-ee04-4759-8568-f45e3b739178 | E2E      | e***@example.com | 2026-10-25 02:22:02.082546+00 | (NULL)                        |
| 0259f541-3ff6-4aaa-b717-ee532f554a5c | E2E      | e***@example.com | 2026-10-25 02:21:55.465292+00 | (NULL)                        |
| fe89ecff-af49-44e8-b66f-a145277b1a16 | E2E      | e***@example.com | 2026-10-25 02:21:55.45923+00  | (NULL)                        |
| c353abe9-faad-495c-8995-9332518acc70 | E2E      | e***@example.com | 2026-10-25 02:21:55.450626+00 | (NULL)                        |
| 5324f2f1-5f05-444f-9fce-7c4b465923e3 | E2E      | e***@example.com | 2026-10-25 02:21:55.445033+00 | (NULL)                        |
| 317a7753-3e22-461f-8493-a3ffb3aee845 | E2E      | e***@example.com | 2026-10-25 02:21:55.438599+00 | (NULL)                        |
| 25d3bb9f-cde5-4f6e-9399-82c655ee481a | E2E      | e***@example.com | 2026-10-25 02:21:55.431906+00 | (NULL)                        |
| bb5ac819-453b-40de-a834-7e6c94af560b | E2E      | e***@example.com | 2026-10-25 02:21:55.426014+00 | (NULL)                        |
+--------------------------------------+----------+------------------+-------------------------------+-------------------------------+
(10 rows)

-- Q2. Sesiones vigentes vs expiradas (sin token_hash)
+----------+-----------+-------+
| vigentes | expiradas | total |
+----------+-----------+-------+
|        1 |         0 |     1 |
+----------+-----------+-------+
(1 row)

-- Q3. Senales de proteccion de login (sin datos personales)
+------------------+-----------------------+----------+
| bloqueados_ahora | con_intentos_fallidos | clientes |
+------------------+-----------------------+----------+
|                0 |                     0 |       16 |
+------------------+-----------------------+----------+
(1 row)


############################################################
# hotel_db - hoteles y habitaciones                        #
############################################################
You are now connected to database "hotel_db" as user "postgres".
-- Q4. Hoteles con numero de habitaciones y rango de precio
+--------------------------------------+-------------------------+-----------+--------------+------------------+------------------+
|                  id                  |          hotel          |  ciudad   | habitaciones | precio_min_cents | precio_max_cents |
+--------------------------------------+-------------------------+-----------+--------------+------------------+------------------+
| 11035923-7cf3-5951-a472-295bd039297a | Hotel Cuenca Histórico  | Cuenca    |            5 |             3900 |            12500 |
| 68144359-0b0c-5656-927d-b46c5dfa59ce | Hotel Guayaquil Malecón | Guayaquil |            5 |             3900 |            12500 |
| 2b6f0f0e-0000-4000-8000-000000000003 | Hotel Quito             | Quito     |            0 |           (NULL) |           (NULL) |
| 1a3f887e-c256-5207-a341-6ea9e66ae869 | Hotel Quito Centro      | Quito     |            6 |             3900 |            12500 |
+--------------------------------------+-------------------------+-----------+--------------+------------------+------------------+
(4 rows)

-- Q5. Catalogo de habitaciones (FK fisica rooms -> hotels)
+--------------------------------------+-------------------------+--------------+-----------+--------------------+--------+
|                  id                  |          hotel          |  habitacion  | capacidad | precio_noche_cents | moneda |
+--------------------------------------+-------------------------+--------------+-----------+--------------------+--------+
| edf4436b-1c48-55e6-b3f7-2737ae3ddfc2 | Hotel Cuenca Histórico  | Simple       |         1 |               3900 | USD    |
| cc2d69c3-d8e3-5eca-bebc-dc30855a188e | Hotel Cuenca Histórico  | Doble        |         2 |               5200 | USD    |
| bb66f137-5746-5c9e-834a-4b99164714a3 | Hotel Cuenca Histórico  | Matrimonial  |         2 |               6100 | USD    |
| d180412d-a900-5cea-87ee-005bcf3b568f | Hotel Cuenca Histórico  | Suite        |         3 |               9400 | USD    |
| bee36045-29f2-5ef5-9728-1ee0e3b6419f | Hotel Cuenca Histórico  | Familiar     |         4 |              12500 | USD    |
| 908d42d1-fa1c-5496-88cd-a13420d54871 | Hotel Guayaquil Malecón | Simple       |         1 |               3900 | USD    |
| 46a5e3d0-0136-5ef2-bf44-5069c9574c32 | Hotel Guayaquil Malecón | Doble        |         2 |               5200 | USD    |
| 3f0ed574-fe59-5d70-abf4-d9ce8fe53f28 | Hotel Guayaquil Malecón | Matrimonial  |         2 |               6100 | USD    |
| 276edc6e-5eb9-5541-ab98-4959016cc3cb | Hotel Guayaquil Malecón | Suite        |         3 |               9400 | USD    |
| 86166c1e-444f-5057-9fd0-fda1fdd17ba2 | Hotel Guayaquil Malecón | Familiar     |         4 |              12500 | USD    |
| 763a7e96-94b4-598f-8019-a6cf3d0aa7f7 | Hotel Quito Centro      | Simple       |         1 |               3900 | USD    |
| 6d0fc272-448a-5127-9841-b5d1948eee65 | Hotel Quito Centro      | E2E 753636b7 |         2 |               5000 | USD    |
| 245bb95e-d685-5e6f-b7c1-cb1c2314278e | Hotel Quito Centro      | Doble        |         2 |               5200 | USD    |
| 997c4541-2537-5c12-b0b8-6f2fc4c8bcf6 | Hotel Quito Centro      | Matrimonial  |         2 |               6100 | USD    |
| dd6684bb-cad7-58e2-8cf2-58a557ec75c5 | Hotel Quito Centro      | Suite        |         3 |               9400 | USD    |
| 33e5baf5-18ff-53c1-89a0-98cbf283a790 | Hotel Quito Centro      | Familiar     |         4 |              12500 | USD    |
+--------------------------------------+-------------------------+--------------+-----------+--------------------+--------+
(16 rows)

-- Q6. Restricciones de dominio vigentes (CHECK)
+----------------------+------------------------------------------------+
|     restriccion      |                   definicion                   |
+----------------------+------------------------------------------------+
| rooms_capacity_check | CHECK (((capacity >= 1) AND (capacity <= 10))) |
| rooms_currency_check | CHECK (((currency)::text = 'USD'::text))       |
| rooms_price_check    | CHECK ((price_per_night_cents > 0))            |
+----------------------+------------------------------------------------+
(3 rows)


############################################################
# availability_db - inventario y holds                     #
############################################################
You are now connected to database "availability_db" as user "postgres".
-- Q7. Inventario agregado por hotel (hotel_id es referencia logica a hotel_db)
+--------------------------------------+--------+----------------+-----------+-------------+--------+
|               hotel_id               | noches | unidades_total | retenidas | confirmadas | libres |
+--------------------------------------+--------+----------------+-----------+-------------+--------+
| 11035923-7cf3-5951-a472-295bd039297a |    305 |           1525 |         0 |           0 |   1525 |
| 1a3f887e-c256-5207-a341-6ea9e66ae869 |    331 |           1607 |         0 |          24 |   1583 |
| 68144359-0b0c-5656-927d-b46c5dfa59ce |    305 |           1525 |         0 |           0 |   1525 |
| 9147fbc8-f85e-4bc9-abbd-d8131f9eff57 |      1 |              1 |         0 |           0 |      1 |
| 9e971d07-a170-48b1-acd6-01474ad65591 |      1 |              1 |         0 |           0 |      1 |
+--------------------------------------+--------+----------------+-----------+-------------+--------+
(5 rows)

-- Q8. Ocupacion por noche (proximas 14 noches)
+------------+--------------+-------+-----------+-------------+--------+
|   night    | habitaciones | total | retenidas | confirmadas | libres |
+------------+--------------+-------+-----------+-------------+--------+
| 2026-10-26 |           15 |    75 |         0 |           0 |     75 |
| 2026-10-27 |           15 |    75 |         0 |           0 |     75 |
| 2026-10-28 |           15 |    75 |         0 |           0 |     75 |
| 2026-10-29 |           15 |    75 |         0 |           0 |     75 |
| 2026-10-30 |           15 |    75 |         0 |           0 |     75 |
| 2026-10-31 |           15 |    75 |         0 |           0 |     75 |
| 2026-11-01 |           15 |    75 |         0 |           0 |     75 |
| 2026-11-02 |           15 |    75 |         0 |           0 |     75 |
| 2026-11-03 |           15 |    75 |         0 |           0 |     75 |
| 2026-11-04 |           15 |    75 |         0 |           0 |     75 |
| 2026-11-05 |           15 |    75 |         0 |           0 |     75 |
| 2026-11-06 |           15 |    75 |         0 |           0 |     75 |
| 2026-11-07 |           15 |    75 |         0 |           0 |     75 |
| 2026-11-08 |           15 |    75 |         0 |           0 |     75 |
+------------+--------------+-------+-----------+-------------+--------+
(14 rows)

-- Q9. Holds por estado (maquina de estados de disponibilidad)
+-----------+-------+-------------------------------+-------------------------------+
|  status   | holds |            primero            |            ultimo             |
+-----------+-------+-------------------------------+-------------------------------+
| CONFIRMED |    24 | 2026-10-25 02:21:51.890308+00 | 2026-10-25 02:22:05.402903+00 |
| EXPIRED   |     2 | 2026-10-25 02:22:44.189849+00 | 2026-10-25 02:39:20.055665+00 |
| RELEASED  |     3 | 2026-10-25 02:21:52.365148+00 | 2026-10-25 02:22:16.891807+00 |
+-----------+-------+-------------------------------+-------------------------------+
(3 rows)

-- Q10. Holds HELD proximos a expirar
+---------+---------+----------+-----------+-------+------------+
| hold_id | room_id | check_in | check_out | units | expires_at |
+---------+---------+----------+-----------+-------+------------+
+---------+---------+----------+-----------+-------+------------+
(0 rows)

-- Q11. Invariante de inventario: held + confirmed <= total (debe ser 0)
+-----------------+
| filas_invalidas |
+-----------------+
|               0 |
+-----------------+
(1 row)


############################################################
# payment_db - pagos, intentos y ledger                    #
############################################################
You are now connected to database "payment_db" as user "postgres".
-- Q12. Pagos por estado
+-----------+-------+-------------+
|  status   | pagos | total_cents |
+-----------+-------+-------------+
| DECLINED  |     1 |        5000 |
| REFUNDED  |     2 |       10200 |
| SUCCEEDED |    24 |      120000 |
+-----------+-------+-------------+
(3 rows)

-- Q13. Intentos por resultado
+----------+----------+
| outcome  | intentos |
+----------+----------+
| APPROVED |       25 |
| DECLINED |        1 |
| UNKNOWN  |        1 |
+----------+----------+
(3 rows)

-- Q14. Asientos del ledger (CHARGE / REFUND)
+--------+----------+-------------+
|  kind  | asientos | total_cents |
+--------+----------+-------------+
| CHARGE |       26 |      130200 |
| REFUND |        2 |       10200 |
+--------+----------+-------------+
(2 rows)

-- Q15. Ultimos pagos (sin provider_ref ni idempotency_key)
+--------------------------------------+--------------------------------------+--------------+----------+--------+-----------+-------------------------------+
|                  id                  |            reservation_id            | amount_cents | currency | method |  status   |          created_at           |
+--------------------------------------+--------------------------------------+--------------+----------+--------+-----------+-------------------------------+
| af6d288c-2f61-46ed-bf02-0fa9a8a585cf | eda0ca32-13ee-459b-acd3-ad876e38da45 |         5200 | USD      | card   | REFUNDED  | 2026-10-25 02:22:16.962368+00 |
| 6a9f612e-a432-48ef-b771-2dee9b12302b | 332c114b-568f-4dc4-9f90-a96d74ace5ab |         5000 | USD      | card   | SUCCEEDED | 2026-10-25 02:22:05.473889+00 |
| 26e3e6e2-43f7-4c65-9226-0005dc250ca5 | b11a8650-e5a0-4b4e-9601-defa9788a3f5 |         5000 | USD      | card   | SUCCEEDED | 2026-10-25 02:22:02.185806+00 |
| 86a81b5f-b62e-4221-acdd-5a6b3d56b0da | 6f8bc643-6f04-4c12-ba92-47a884626dcb |         5000 | USD      | card   | REFUNDED  | 2026-10-25 02:22:01.541089+00 |
| 77a0822b-3281-42b3-8dfe-1c4c960841a4 | 049039c0-7371-4702-8138-6c9b64fa8a42 |         5000 | USD      | card   | SUCCEEDED | 2026-10-25 02:22:00.788693+00 |
| 1d883855-a65a-496a-94a6-d0a1be28086b | 1b435526-be81-4727-b8af-8b29573f63a6 |         5000 | USD      | card   | SUCCEEDED | 2026-10-25 02:22:00.275834+00 |
| e83f966d-43c5-4422-9d67-5112c694ad2a | ac40c8bc-820c-4d01-a7a3-598145ed622b |         5000 | USD      | card   | SUCCEEDED | 2026-10-25 02:21:59.694889+00 |
| 89d7ebd6-d4e1-4e20-96c2-72f5cc5c37a1 | 6e345473-5653-48dc-bb0c-2b330b23a52b |         5000 | USD      | card   | SUCCEEDED | 2026-10-25 02:21:59.262145+00 |
| 1d8f35c2-a88d-4914-9f37-0ce9321451c9 | 3af94173-9bf7-4fce-ae5c-bc4c075f0329 |         5000 | USD      | card   | SUCCEEDED | 2026-10-25 02:21:58.822349+00 |
| 638fa93f-e6cd-4593-9b6c-7386796fc577 | 32716155-34ea-43e3-9205-7c2c7a2e5b2e |         5000 | USD      | card   | SUCCEEDED | 2026-10-25 02:21:58.353999+00 |
+--------------------------------------+--------------------------------------+--------------+----------+--------+-----------+-------------------------------+
(10 rows)

-- Q16. Integridad pago<->ledger: SUCCEEDED sin asiento CHARGE (debe ser 0)
+------------------+
| pagos_sin_charge |
+------------------+
|                0 |
+------------------+
(1 row)

-- Q17. Un solo pago por reserva (UNIQUE payments.reservation_id)
+-----------------------------+
| reservas_con_mas_de_un_pago |
+-----------------------------+
|                           0 |
+-----------------------------+
(1 row)


############################################################
# reservation_db - saga, eventos y outbox                  #
############################################################
You are now connected to database "reservation_db" as user "postgres".
-- Q18. Reservas por estado (maquina de estados de F0)
+-----------------------+----------+-------------+
|        status         | reservas | total_cents |
+-----------------------+----------+-------------+
| REJECTED_NO_INVENTORY |       90 |      450000 |
| CONFIRMED             |       24 |      120000 |
| CANCELLED             |        3 |       15200 |
+-----------------------+----------+-------------+
(3 rows)

-- Q19. Embudo por estado del pago
+----------------+----------+
| payment_status | reservas |
+----------------+----------+
| (NULL)         |       90 |
| DECLINED       |        1 |
| SUCCEEDED      |       26 |
+----------------+----------+
(3 rows)

-- Q20. Ultimas reservas (sin payment_token ni request_hash)
+--------------------------------------+--------------------------------------+--------------------------------------+--------------------------------------+------------+------------+--------+--------------+----------+----------------+-----------------------+-------------------------------+
|                  id                  |             customer_id              |               hotel_id               |               room_id                |  check_in  | check_out  | nights | amount_cents | currency | payment_status |        status         |          created_at           |
+--------------------------------------+--------------------------------------+--------------------------------------+--------------------------------------+------------+------------+--------+--------------+----------+----------------+-----------------------+-------------------------------+
| eda0ca32-13ee-459b-acd3-ad876e38da45 | c67e3543-cea4-4845-a361-c833ad545354 | 11035923-7cf3-5951-a472-295bd039297a | cc2d69c3-d8e3-5eca-bebc-dc30855a188e | 2026-11-18 | 2026-11-19 |      1 |         5200 | USD      | SUCCEEDED      | CANCELLED             | 2026-10-25 02:22:16.879048+00 |
| 332c114b-568f-4dc4-9f90-a96d74ace5ab | ccde209c-3d38-4f9c-8239-4951b40c9763 | 1a3f887e-c256-5207-a341-6ea9e66ae869 | 6d0fc272-448a-5127-9841-b5d1948eee65 | 9268-05-03 | 9268-05-04 |      1 |         5000 | USD      | SUCCEEDED      | CONFIRMED             | 2026-10-25 02:22:05.388339+00 |
| b11a8650-e5a0-4b4e-9601-defa9788a3f5 | 693d25b2-ee04-4759-8568-f45e3b739178 | 1a3f887e-c256-5207-a341-6ea9e66ae869 | 6d0fc272-448a-5127-9841-b5d1948eee65 | 9268-05-01 | 9268-05-02 |      1 |         5000 | USD      | SUCCEEDED      | CONFIRMED             | 2026-10-25 02:22:02.108701+00 |
| 6f8bc643-6f04-4c12-ba92-47a884626dcb | df7bd3fd-c1bd-439d-8d64-d5a601f04379 | 1a3f887e-c256-5207-a341-6ea9e66ae869 | 6d0fc272-448a-5127-9841-b5d1948eee65 | 7762-07-12 | 7762-07-13 |      1 |         5000 | USD      | SUCCEEDED      | CANCELLED             | 2026-10-25 02:22:01.464255+00 |
| 049039c0-7371-4702-8138-6c9b64fa8a42 | e01fac92-5240-4817-8ac2-38cd8c1f5139 | 1a3f887e-c256-5207-a341-6ea9e66ae869 | 6d0fc272-448a-5127-9841-b5d1948eee65 | 7762-07-10 | 7762-07-11 |      1 |         5000 | USD      | SUCCEEDED      | CONFIRMED             | 2026-10-25 02:22:00.710255+00 |
| 6aa306d3-b177-47b8-a288-7a87a8906f10 | 317a7753-3e22-461f-8493-a3ffb3aee845 | 1a3f887e-c256-5207-a341-6ea9e66ae869 | 6d0fc272-448a-5127-9841-b5d1948eee65 | 7762-08-09 | 7762-08-10 |      1 |         5000 | USD      | (NULL)         | REJECTED_NO_INVENTORY | 2026-10-25 02:22:00.141265+00 |
| 1ecd3f52-41b0-4d21-990d-a9cf6ed50f78 | fe89ecff-af49-44e8-b66f-a145277b1a16 | 1a3f887e-c256-5207-a341-6ea9e66ae869 | 6d0fc272-448a-5127-9841-b5d1948eee65 | 7762-08-09 | 7762-08-10 |      1 |         5000 | USD      | (NULL)         | REJECTED_NO_INVENTORY | 2026-10-25 02:22:00.131142+00 |
| 2e1f2477-8bed-47f4-9718-31fd41a70749 | 25d3bb9f-cde5-4f6e-9399-82c655ee481a | 1a3f887e-c256-5207-a341-6ea9e66ae869 | 6d0fc272-448a-5127-9841-b5d1948eee65 | 7762-08-09 | 7762-08-10 |      1 |         5000 | USD      | (NULL)         | REJECTED_NO_INVENTORY | 2026-10-25 02:22:00.127929+00 |
| 649b6285-6643-48d5-bd69-a055f2dcd47a | 631bff74-f8b3-4a0f-be59-4ba5e724e280 | 1a3f887e-c256-5207-a341-6ea9e66ae869 | 6d0fc272-448a-5127-9841-b5d1948eee65 | 7762-08-09 | 7762-08-10 |      1 |         5000 | USD      | (NULL)         | REJECTED_NO_INVENTORY | 2026-10-25 02:22:00.127031+00 |
| b5dc6810-fe0f-4420-a542-35d12cc02633 | c353abe9-faad-495c-8995-9332518acc70 | 1a3f887e-c256-5207-a341-6ea9e66ae869 | 6d0fc272-448a-5127-9841-b5d1948eee65 | 7762-08-09 | 7762-08-10 |      1 |         5000 | USD      | (NULL)         | REJECTED_NO_INVENTORY | 2026-10-25 02:22:00.120378+00 |
+--------------------------------------+--------------------------------------+--------------------------------------+--------------------------------------+------------+------------+--------+--------------+----------+----------------+-----------------------+-------------------------------+
(10 rows)

-- Q21. Transiciones registradas por estado destino
+-----------------------+--------------+
|       to_status       | transiciones |
+-----------------------+--------------+
| RECEIVED              |          117 |
| REJECTED_NO_INVENTORY |           90 |
| HELD                  |           27 |
| PAYMENT_PENDING       |           27 |
| PAID                  |           26 |
| CONFIRMED             |           26 |
| CANCELLED             |            3 |
| CANCELLING            |            2 |
| PAYMENT_DECLINED      |            1 |
| PAYMENT_UNKNOWN       |            1 |
+-----------------------+--------------+
(10 rows)

-- Q22. Outbox transaccional por estado
+--------+---------+
| status | eventos |
+--------+---------+
| SENT   |      28 |
+--------+---------+
(1 row)

-- Q23. Outbox pendiente de relay
+----+--------------+------+----------+-----------------+
| id | aggregate_id | type | attempts | next_attempt_at |
+----+--------------+------+----------+-----------------+
+----+--------------+------+----------+-----------------+
(0 rows)

-- Q24. Toda reserva tiene su evento inicial (from_status NULL). Debe ser 0
+-----------------------------+
| reservas_sin_evento_inicial |
+-----------------------------+
|                           0 |
+-----------------------------+
(1 row)

-- Q25. Consistencia de noches y monto
+-----------------------+------------------+
| noches_inconsistentes | montos_invalidos |
+-----------------------+------------------+
|                     0 |                0 |
+-----------------------+------------------+
(1 row)


############################################################
# notification_db - outbox de notificaciones               #
############################################################
You are now connected to database "notification_db" as user "postgres".
-- Q26. Notificaciones por tipo y estado
+-----------------------+--------+-------+
|         type          | status | total |
+-----------------------+--------+-------+
| reservation.cancelled | SENT   |     2 |
| reservation.confirmed | SENT   |    27 |
+-----------------------+--------+-------+
(2 rows)

-- Q27. Ultimas notificaciones (sin volcar payload)
+--------------------------------------+--------------------------------------+--------------------------------------+--------------------------------------+-----------------------+--------+----------+-------------------------------+-------------------------------+
|                  id                  |               event_id               |            reservation_id            |             customer_id              |         type          | status | attempts |        next_attempt_at        |            sent_at            |
+--------------------------------------+--------------------------------------+--------------------------------------+--------------------------------------+-----------------------+--------+----------+-------------------------------+-------------------------------+
| b9998596-6f3d-4c8c-bcd2-9f69c84dc954 | 8bcb9877-c99a-4171-92ad-e52fbc7eedd3 | eda0ca32-13ee-459b-acd3-ad876e38da45 | c67e3543-cea4-4845-a361-c833ad545354 | reservation.cancelled | SENT   |        1 | 2026-10-25 02:22:49.896429+00 | 2026-10-25 02:22:19.900402+00 |
| f417b517-2adb-45a0-a672-b50f0f7a28eb | ba7fe26f-d27c-4e1b-b26f-eb761e78846b | eda0ca32-13ee-459b-acd3-ad876e38da45 | c67e3543-cea4-4845-a361-c833ad545354 | reservation.confirmed | SENT   |        1 | 2026-10-25 02:22:47.888727+00 | 2026-10-25 02:22:17.891506+00 |
| d86412d0-8e43-4526-8927-4106c43af1e7 | 4637a7dc-3f81-4bdd-be3b-cde23a3d0613 | 332c114b-568f-4dc4-9f90-a96d74ace5ab | ccde209c-3d38-4f9c-8239-4951b40c9763 | reservation.confirmed | SENT   |        1 | 2026-10-25 02:22:44.878324+00 | 2026-10-25 02:22:14.880532+00 |
| c2de795e-8c7a-43ca-bb1d-eb60be768fe8 | 60073fcb-c6f1-4a3e-a170-5690967c73a3 | 447f501c-219b-46c9-8b54-a53a7089e966 | dc33a165-5ede-44b0-999d-b37c2aa00408 | reservation.confirmed | SENT   |        1 | 2026-10-25 02:22:34.851352+00 | 2026-10-25 02:22:04.854436+00 |
| 57bfef6e-5a11-4809-8494-3bcee3cda22b | 66501e93-41e5-4c69-837e-48ab04c9325c | b11a8650-e5a0-4b4e-9601-defa9788a3f5 | 693d25b2-ee04-4759-8568-f45e3b739178 | reservation.confirmed | SENT   |        1 | 2026-10-25 02:22:33.845684+00 | 2026-10-25 02:22:03.848187+00 |
| aa860dc1-3a57-4d42-a5ed-8ecb0e44acde | 913db306-86fa-402f-817e-87b3fdbba928 | 6f8bc643-6f04-4c12-ba92-47a884626dcb | df7bd3fd-c1bd-439d-8d64-d5a601f04379 | reservation.cancelled | SENT   |        1 | 2026-10-25 02:22:32.837556+00 | 2026-10-25 02:22:02.84322+00  |
| 42cb863d-16e3-4dce-8296-5148ca2ca557 | ed78534f-3050-4e97-b1ea-173e63449fa4 | 6f8bc643-6f04-4c12-ba92-47a884626dcb | df7bd3fd-c1bd-439d-8d64-d5a601f04379 | reservation.confirmed | SENT   |        1 | 2026-10-25 02:22:32.837556+00 | 2026-10-25 02:22:02.841806+00 |
| 78d5bb4d-6245-4828-91b1-cb42019a490e | 1dc37cd5-1202-40c0-a3fa-4e9eb19f62ee | 049039c0-7371-4702-8138-6c9b64fa8a42 | e01fac92-5240-4817-8ac2-38cd8c1f5139 | reservation.confirmed | SENT   |        1 | 2026-10-25 02:22:32.837556+00 | 2026-10-25 02:22:02.840298+00 |
| ae5e5eb6-1f8f-44d2-97ec-c24fff8a1154 | 2909d5d9-d297-486a-a0e4-26ec6eeb5d84 | 1b435526-be81-4727-b8af-8b29573f63a6 | 5324f2f1-5f05-444f-9fce-7c4b465923e3 | reservation.confirmed | SENT   |        1 | 2026-10-25 02:22:31.830493+00 | 2026-10-25 02:22:01.833425+00 |
| c34ab84b-0b89-46f8-81d2-0bf343fe2077 | c8217124-6614-4dfd-b01e-1a43a7b26335 | 3af94173-9bf7-4fce-ae5c-bc4c075f0329 | 065ec474-9f7e-4906-916f-4ca82e3c3bea | reservation.confirmed | SENT   |        1 | 2026-10-25 02:22:30.822806+00 | 2026-10-25 02:22:00.828108+00 |
+--------------------------------------+--------------------------------------+--------------------------------------+--------------------------------------+-----------------------+--------+----------+-------------------------------+-------------------------------+
(10 rows)

-- Q28. Deduplicacion por event_id (UNIQUE; debe ser 0)
+---------------------+
| event_id_duplicados |
+---------------------+
|                   0 |
+---------------------+
(1 row)

-- Q29. Enviadas sin fecha de envio (debe ser 0)
+--------------------+
| enviadas_sin_fecha |
+--------------------+
|                  0 |
+--------------------+
(1 row)


############################################################
# Referencias logicas entre servicios (sin FK)             #
############################################################
You are now connected to database "reservation_db" as user "postgres".
-- Q30. Ids referenciados por reservation_db
+------------------------+-----------------------+----------------------------+
| clientes_referenciados | hoteles_referenciados | habitaciones_referenciadas |
+------------------------+-----------------------+----------------------------+
|                     15 |                     2 |                          2 |
+------------------------+-----------------------+----------------------------+
(1 row)

You are now connected to database "customer_db" as user "postgres".
-- Q31. Clientas/clientes existentes en customer_db (comparar con Q30)
+----------------------+
| clientes_registrados |
+----------------------+
|                   16 |
+----------------------+
(1 row)


=== Fin de las consultas de demostracion ===
```
