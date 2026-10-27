-- DDL de notification_db extraído del PostgreSQL real con:
-- pg_dump -U postgres -d notification_db --schema-only --no-owner --no-privileges
-- Sin datos, sin credenciales. Regenerar: docs/database-evidence/generate.py

--
-- PostgreSQL database dump
--


-- Dumped from database version 16.14 (Debian 16.14-1.pgdg13+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid NOT NULL,
    event_id uuid NOT NULL,
    type text NOT NULL,
    reservation_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    status text DEFAULT 'PENDING'::text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    sent_at timestamp with time zone,
    CONSTRAINT notifications_status_check CHECK ((status = ANY (ARRAY['PENDING'::text, 'SENT'::text, 'FAILED'::text]))),
    CONSTRAINT notifications_type_check CHECK ((type = ANY (ARRAY['reservation.confirmed'::text, 'reservation.cancelled'::text])))
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: notifications notifications_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_event_id_key UNIQUE (event_id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: idx_notifications_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_pending ON public.notifications USING btree (next_attempt_at) WHERE (status = 'PENDING'::text);


--
-- Name: idx_notifications_reservation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_reservation ON public.notifications USING btree (reservation_id);


--
-- PostgreSQL database dump complete
--


