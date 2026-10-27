-- DDL de payment_db extraído del PostgreSQL real con:
-- pg_dump -U postgres -d payment_db --schema-only --no-owner --no-privileges
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
-- Name: ledger_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ledger_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'ledger es append-only';
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
-- Name: ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ledger (
    id uuid NOT NULL,
    payment_id uuid NOT NULL,
    kind text NOT NULL,
    amount_cents integer NOT NULL,
    currency text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ledger_kind_check CHECK ((kind = ANY (ARRAY['CHARGE'::text, 'REFUND'::text])))
);


--
-- Name: payment_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_attempts (
    id uuid NOT NULL,
    payment_id uuid NOT NULL,
    attempt_no integer NOT NULL,
    simulate text,
    outcome text,
    error text,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone
);


--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    id uuid NOT NULL,
    reservation_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    amount_cents integer NOT NULL,
    currency text NOT NULL,
    method text NOT NULL,
    status text NOT NULL,
    provider_ref text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT payments_amount_cents_check CHECK ((amount_cents > 0)),
    CONSTRAINT payments_status_check CHECK ((status = ANY (ARRAY['INITIATED'::text, 'SUCCEEDED'::text, 'DECLINED'::text, 'FAILED_TECHNICAL'::text, 'UNKNOWN'::text, 'REFUNDED'::text])))
);


--
-- Name: sim_provider_charges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sim_provider_charges (
    idempotency_key text NOT NULL,
    provider_ref text NOT NULL,
    status text NOT NULL,
    amount_cents integer NOT NULL,
    currency text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    refunded_at timestamp with time zone,
    CONSTRAINT sim_provider_charges_status_check CHECK ((status = ANY (ARRAY['APPROVED'::text, 'DECLINED'::text])))
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: ledger ledger_payment_id_kind_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger
    ADD CONSTRAINT ledger_payment_id_kind_key UNIQUE (payment_id, kind);


--
-- Name: ledger ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger
    ADD CONSTRAINT ledger_pkey PRIMARY KEY (id);


--
-- Name: payment_attempts payment_attempts_payment_id_attempt_no_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_attempts
    ADD CONSTRAINT payment_attempts_payment_id_attempt_no_key UNIQUE (payment_id, attempt_no);


--
-- Name: payment_attempts payment_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_attempts
    ADD CONSTRAINT payment_attempts_pkey PRIMARY KEY (id);


--
-- Name: payments payments_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_idempotency_key_key UNIQUE (idempotency_key);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: payments payments_reservation_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_reservation_id_key UNIQUE (reservation_id);


--
-- Name: sim_provider_charges sim_provider_charges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sim_provider_charges
    ADD CONSTRAINT sim_provider_charges_pkey PRIMARY KEY (idempotency_key);


--
-- Name: idx_payments_unknown; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_unknown ON public.payments USING btree (updated_at) WHERE (status = 'UNKNOWN'::text);


--
-- Name: ledger ledger_no_update_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ledger_no_update_delete BEFORE DELETE OR UPDATE ON public.ledger FOR EACH ROW EXECUTE FUNCTION public.ledger_append_only();


--
-- Name: ledger ledger_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger
    ADD CONSTRAINT ledger_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id);


--
-- Name: payment_attempts payment_attempts_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_attempts
    ADD CONSTRAINT payment_attempts_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id);


--
-- PostgreSQL database dump complete
--


