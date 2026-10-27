-- =====================================================================
-- Consultas de demostracion (SOLO LECTURA) - reservas-platform
--
-- Requiere el perfil dev levantado (`make up`) y PostgreSQL publicado en
-- 127.0.0.1:5433. Se ejecuta con el superusuario porque cambia de base con
-- \c; los roles de servicio NO pueden conectarse a bases ajenas.
--
-- Uso (PowerShell, desde reservas-platform/):
--   Get-Content -Raw docs/database-evidence/queries.sql |
--     docker exec -i reservas-platform-postgres-1 psql -U postgres
--
-- O dentro del contenedor:
--   docker exec -it reservas-platform-postgres-1 psql -U postgres
--   \i /ruta/queries.sql
--
-- Privacidad: no se seleccionan password_hash, token_hash, payment_token,
-- request_hash ni provider_ref. El email se enmascara. Los payloads de outbox
-- y notifications no se vuelcan (pueden contener datos del cliente).
-- =====================================================================

\set ON_ERROR_STOP on
\pset pager off
\pset border 2
\pset null '(NULL)'
\encoding UTF8
\timing off

\echo ''
\echo '############################################################'
\echo '# customer_db - cuentas y sesiones                         #'
\echo '############################################################'
\c customer_db

\echo '-- Q1. Clientes (email enmascarado; sin hash de contrasena)'
SELECT id,
       name,
       regexp_replace(email, '^(.).*(@.*)$', '\1***\2') AS email_masked,
       created_at,
       last_login_at
FROM customers
ORDER BY created_at DESC
LIMIT 10;

\echo '-- Q2. Sesiones vigentes vs expiradas (sin token_hash)'
SELECT count(*) FILTER (WHERE expires_at > now()) AS vigentes,
       count(*) FILTER (WHERE expires_at <= now()) AS expiradas,
       count(*) AS total
FROM sessions;

\echo '-- Q3. Senales de proteccion de login (sin datos personales)'
SELECT count(*) FILTER (WHERE locked_until > now()) AS bloqueados_ahora,
       count(*) FILTER (WHERE failed_attempts > 0) AS con_intentos_fallidos,
       count(*) AS clientes
FROM customers;


\echo ''
\echo '############################################################'
\echo '# hotel_db - hoteles y habitaciones                        #'
\echo '############################################################'
\c hotel_db

\echo '-- Q4. Hoteles con numero de habitaciones y rango de precio'
SELECT h.id,
       h.name AS hotel,
       h.city AS ciudad,
       count(r.id) AS habitaciones,
       min(r.price_per_night_cents) AS precio_min_cents,
       max(r.price_per_night_cents) AS precio_max_cents
FROM hotels h
LEFT JOIN rooms r ON r.hotel_id = h.id
GROUP BY h.id, h.name, h.city
ORDER BY h.name;

\echo '-- Q5. Catalogo de habitaciones (FK fisica rooms -> hotels)'
SELECT r.id,
       h.name AS hotel,
       r.name AS habitacion,
       r.capacity AS capacidad,
       r.price_per_night_cents AS precio_noche_cents,
       r.currency AS moneda
FROM rooms r
JOIN hotels h ON h.id = r.hotel_id
ORDER BY h.name, r.price_per_night_cents;

\echo '-- Q6. Restricciones de dominio vigentes (CHECK)'
SELECT conname AS restriccion,
       pg_get_constraintdef(oid) AS definicion
FROM pg_constraint
WHERE conrelid = 'rooms'::regclass AND contype = 'c'
ORDER BY conname;


\echo ''
\echo '############################################################'
\echo '# availability_db - inventario y holds                     #'
\echo '############################################################'
\c availability_db

\echo '-- Q7. Inventario agregado por hotel (hotel_id es referencia logica a hotel_db)'
SELECT hotel_id,
       count(*) AS noches,
       sum(total) AS unidades_total,
       sum(held) AS retenidas,
       sum(confirmed) AS confirmadas,
       sum(total - held - confirmed) AS libres
FROM inventory
GROUP BY hotel_id
ORDER BY hotel_id;

\echo '-- Q8. Ocupacion por noche (proximas 14 noches)'
SELECT night,
       count(*) AS habitaciones,
       sum(total) AS total,
       sum(held) AS retenidas,
       sum(confirmed) AS confirmadas,
       sum(total - held - confirmed) AS libres
FROM inventory
WHERE night >= current_date
GROUP BY night
ORDER BY night
LIMIT 14;

\echo '-- Q9. Holds por estado (maquina de estados de disponibilidad)'
SELECT status,
       count(*) AS holds,
       min(created_at) AS primero,
       max(created_at) AS ultimo
FROM holds
GROUP BY status
ORDER BY status;

\echo '-- Q10. Holds HELD proximos a expirar'
SELECT hold_id,
       room_id,
       check_in,
       check_out,
       units,
       expires_at
FROM holds
WHERE status = 'HELD'
ORDER BY expires_at
LIMIT 10;

\echo '-- Q11. Invariante de inventario: held + confirmed <= total (debe ser 0)'
SELECT count(*) AS filas_invalidas
FROM inventory
WHERE held + confirmed > total;


\echo ''
\echo '############################################################'
\echo '# payment_db - pagos, intentos y ledger                    #'
\echo '############################################################'
\c payment_db

\echo '-- Q12. Pagos por estado'
SELECT status,
       count(*) AS pagos,
       sum(amount_cents) AS total_cents
FROM payments
GROUP BY status
ORDER BY status;

\echo '-- Q13. Intentos por resultado'
SELECT outcome,
       count(*) AS intentos
FROM payment_attempts
GROUP BY outcome
ORDER BY outcome NULLS FIRST;

\echo '-- Q14. Asientos del ledger (CHARGE / REFUND)'
SELECT kind,
       count(*) AS asientos,
       sum(amount_cents) AS total_cents
FROM ledger
GROUP BY kind
ORDER BY kind;

\echo '-- Q15. Ultimos pagos (sin provider_ref ni idempotency_key)'
SELECT id,
       reservation_id,
       amount_cents,
       currency,
       method,
       status,
       created_at
FROM payments
ORDER BY created_at DESC
LIMIT 10;

\echo '-- Q16. Integridad pago<->ledger: SUCCEEDED sin asiento CHARGE (debe ser 0)'
SELECT count(*) AS pagos_sin_charge
FROM payments p
LEFT JOIN ledger l ON l.payment_id = p.id AND l.kind = 'CHARGE'
WHERE p.status = 'SUCCEEDED' AND l.id IS NULL;

\echo '-- Q17. Un solo pago por reserva (UNIQUE payments.reservation_id)'
SELECT count(*) AS reservas_con_mas_de_un_pago
FROM (SELECT reservation_id
      FROM payments
      GROUP BY reservation_id
      HAVING count(*) > 1) duplicados;


\echo ''
\echo '############################################################'
\echo '# reservation_db - saga, eventos y outbox                  #'
\echo '############################################################'
\c reservation_db

\echo '-- Q18. Reservas por estado (maquina de estados de F0)'
SELECT status,
       count(*) AS reservas,
       sum(amount_cents) AS total_cents
FROM reservations
GROUP BY status
ORDER BY reservas DESC;

\echo '-- Q19. Embudo por estado del pago'
SELECT payment_status,
       count(*) AS reservas
FROM reservations
GROUP BY payment_status
ORDER BY payment_status NULLS FIRST;

\echo '-- Q20. Ultimas reservas (sin payment_token ni request_hash)'
SELECT id,
       customer_id,
       hotel_id,
       room_id,
       check_in,
       check_out,
       nights,
       amount_cents,
       currency,
       payment_status,
       status,
       created_at
FROM reservations
ORDER BY created_at DESC
LIMIT 10;

\echo '-- Q21. Transiciones registradas por estado destino'
SELECT to_status,
       count(*) AS transiciones
FROM reservation_events
GROUP BY to_status
ORDER BY transiciones DESC;

\echo '-- Q22. Outbox transaccional por estado'
SELECT status,
       count(*) AS eventos
FROM outbox
GROUP BY status
ORDER BY status;

\echo '-- Q23. Outbox pendiente de relay'
SELECT id,
       aggregate_id,
       type,
       attempts,
       next_attempt_at
FROM outbox
WHERE status = 'PENDING'
ORDER BY next_attempt_at
LIMIT 10;

\echo '-- Q24. Toda reserva tiene su evento inicial (from_status NULL). Debe ser 0'
SELECT count(*) AS reservas_sin_evento_inicial
FROM reservations r
WHERE NOT EXISTS (
    SELECT 1 FROM reservation_events e
    WHERE e.reservation_id = r.id AND e.from_status IS NULL
);

\echo '-- Q25. Consistencia de noches y monto'
SELECT count(*) FILTER (WHERE nights <> (check_out - check_in)) AS noches_inconsistentes,
       count(*) FILTER (WHERE amount_cents <= 0) AS montos_invalidos
FROM reservations;


\echo ''
\echo '############################################################'
\echo '# notification_db - outbox de notificaciones               #'
\echo '############################################################'
\c notification_db

\echo '-- Q26. Notificaciones por tipo y estado'
SELECT type,
       status,
       count(*) AS total
FROM notifications
GROUP BY type, status
ORDER BY type, status;

\echo '-- Q27. Ultimas notificaciones (sin volcar payload)'
SELECT id,
       event_id,
       reservation_id,
       customer_id,
       type,
       status,
       attempts,
       next_attempt_at,
       sent_at
FROM notifications
ORDER BY created_at DESC
LIMIT 10;

\echo '-- Q28. Deduplicacion por event_id (UNIQUE; debe ser 0)'
SELECT count(*) AS event_id_duplicados
FROM (SELECT event_id
      FROM notifications
      GROUP BY event_id
      HAVING count(*) > 1) duplicados;

\echo '-- Q29. Enviadas sin fecha de envio (debe ser 0)'
SELECT count(*) AS enviadas_sin_fecha
FROM notifications
WHERE status = 'SENT' AND sent_at IS NULL;


\echo ''
\echo '############################################################'
\echo '# Referencias logicas entre servicios (sin FK)             #'
\echo '############################################################'
-- No se puede hacer JOIN entre bases distintas sin FDW/dblink, que el
-- proyecto no usa (ADR-0002). Para comparar, ejecuta las dos consultas y
-- contrasta los ids a mano, o usa generate.py, que automatiza las 11
-- comprobaciones y escribe integrity.md.
\c reservation_db
\echo '-- Q30. Ids referenciados por reservation_db'
SELECT count(DISTINCT customer_id) AS clientes_referenciados,
       count(DISTINCT hotel_id) AS hoteles_referenciados,
       count(DISTINCT room_id) AS habitaciones_referenciadas
FROM reservations;

\c customer_db
\echo '-- Q31. Clientas/clientes existentes en customer_db (comparar con Q30)'
SELECT count(*) AS clientes_registrados FROM customers;

\echo ''
\echo '=== Fin de las consultas de demostracion ==='
