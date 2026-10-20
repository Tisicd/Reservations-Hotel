#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
CREATE ROLE customer LOGIN PASSWORD '${CUSTOMER_DB_PASSWORD}';
CREATE ROLE hotel LOGIN PASSWORD '${HOTEL_DB_PASSWORD}';
CREATE ROLE availability LOGIN PASSWORD '${AVAILABILITY_DB_PASSWORD}';
CREATE ROLE reservation LOGIN PASSWORD '${RESERVATION_DB_PASSWORD}';
CREATE ROLE payment LOGIN PASSWORD '${PAYMENT_DB_PASSWORD}';
CREATE ROLE notification LOGIN PASSWORD '${NOTIFICATION_DB_PASSWORD}';

CREATE DATABASE customer_db OWNER customer;
CREATE DATABASE hotel_db OWNER hotel;
CREATE DATABASE availability_db OWNER availability;
CREATE DATABASE reservation_db OWNER reservation;
CREATE DATABASE payment_db OWNER payment;
CREATE DATABASE notification_db OWNER notification;

REVOKE CONNECT ON DATABASE customer_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE hotel_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE availability_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE reservation_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE payment_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE notification_db FROM PUBLIC;

-- Timeouts por rol (ADR-0002). No se fijan globalmente en el servidor para que
-- un lock_timeout alto de un rol no exceda la espera síncrona de la saga (5 s).
ALTER ROLE customer SET statement_timeout = '5s';
ALTER ROLE customer SET lock_timeout = '2s';
ALTER ROLE customer SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE hotel SET statement_timeout = '5s';
ALTER ROLE hotel SET lock_timeout = '2s';
ALTER ROLE hotel SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE availability SET statement_timeout = '5s';
ALTER ROLE availability SET lock_timeout = '2s';
ALTER ROLE availability SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE reservation SET statement_timeout = '5s';
ALTER ROLE reservation SET lock_timeout = '2s';
ALTER ROLE reservation SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE payment SET statement_timeout = '5s';
ALTER ROLE payment SET lock_timeout = '2s';
ALTER ROLE payment SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE notification SET statement_timeout = '5s';
ALTER ROLE notification SET lock_timeout = '2s';
ALTER ROLE notification SET idle_in_transaction_session_timeout = '10s';
EOSQL
