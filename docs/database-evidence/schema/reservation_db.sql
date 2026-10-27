-- DDL de reservation_db extraído del PostgreSQL real con:
-- pg_dump -U postgres -d reservation_db --schema-only --no-owner --no-privileges
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

--
-- Name: reservation_events_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.reservation_events_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'reservation_events es append-only';
        END
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: outbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outbox (
    id uuid NOT NULL,
    aggregate_id uuid NOT NULL,
    type text NOT NULL,
    payload jsonb NOT NULL,
    status text DEFAULT 'PENDING'::text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    sent_at timestamp with time zone,
    CONSTRAINT outbox_status_check CHECK ((status = ANY (ARRAY['PENDING'::text, 'SENT'::text])))
);


--
-- Name: reservation_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reservation_events (
    id bigint NOT NULL,
    reservation_id uuid NOT NULL,
    from_status text,
    to_status text NOT NULL,
    reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: reservation_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reservation_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reservation_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reservation_events_id_seq OWNED BY public.reservation_events.id;


--
-- Name: reservations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reservations (
    id uuid NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    customer_id uuid NOT NULL,
    hotel_id uuid NOT NULL,
    room_id uuid NOT NULL,
    check_in date NOT NULL,
    check_out date NOT NULL,
    nights integer NOT NULL,
    amount_cents integer NOT NULL,
    currency text NOT NULL,
    payment_method text NOT NULL,
    payment_token text NOT NULL,
    payment_simulate text NOT NULL,
    payment_id uuid,
    payment_status text,
    status text NOT NULL,
    status_reason text,
    attempts integer DEFAULT 0 NOT NULL,
    next_attempt_at timestamp with time zone,
    phase_started_at timestamp with time zone NOT NULL,
    locked_until timestamp with time zone,
    version integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT reservations_amount_cents_check CHECK ((amount_cents > 0)),
    CONSTRAINT reservations_check CHECK ((check_out > check_in)),
    CONSTRAINT reservations_nights_check CHECK ((nights > 0)),
    CONSTRAINT reservations_payment_simulate_check CHECK ((payment_simulate = ANY (ARRAY['ok'::text, 'decline'::text, 'error_before_processing'::text, 'process_then_drop_response'::text, 'slow'::text]))),
    CONSTRAINT reservations_status_check CHECK ((status = ANY (ARRAY['RECEIVED'::text, 'HELD'::text, 'PAYMENT_PENDING'::text, 'PAYMENT_UNKNOWN'::text, 'PAID'::text, 'CONFIRMED'::text, 'PAYMENT_DECLINED'::text, 'REFUND_REQUIRED'::text, 'CANCELLING'::text, 'CANCELLED'::text, 'REJECTED_NO_INVENTORY'::text, 'FAILED_TECHNICAL'::text, 'MANUAL_REVIEW'::text])))
);


--
-- Name: reservation_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservation_events ALTER COLUMN id SET DEFAULT nextval('public.reservation_events_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: outbox outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outbox
    ADD CONSTRAINT outbox_pkey PRIMARY KEY (id);


--
-- Name: reservation_events reservation_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservation_events
    ADD CONSTRAINT reservation_events_pkey PRIMARY KEY (id);


--
-- Name: reservations reservations_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT reservations_idempotency_key_key UNIQUE (idempotency_key);


--
-- Name: reservations reservations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservations
    ADD CONSTRAINT reservations_pkey PRIMARY KEY (id);


--
-- Name: idx_outbox_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outbox_pending ON public.outbox USING btree (next_attempt_at) WHERE (status = 'PENDING'::text);


--
-- Name: idx_reservation_events_reservation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reservation_events_reservation ON public.reservation_events USING btree (reservation_id, id);


--
-- Name: idx_reservations_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reservations_customer ON public.reservations USING btree (customer_id, created_at DESC);


--
-- Name: idx_reservations_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reservations_due ON public.reservations USING btree (next_attempt_at) WHERE (status <> ALL (ARRAY['CONFIRMED'::text, 'REJECTED_NO_INVENTORY'::text, 'FAILED_TECHNICAL'::text, 'CANCELLED'::text, 'MANUAL_REVIEW'::text]));


--
-- Name: reservation_events reservation_events_no_update_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER reservation_events_no_update_delete BEFORE DELETE OR UPDATE ON public.reservation_events FOR EACH ROW EXECUTE FUNCTION public.reservation_events_append_only();


--
-- Name: reservation_events reservation_events_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservation_events
    ADD CONSTRAINT reservation_events_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservations(id);


--
-- PostgreSQL database dump complete
--


