-- DDL de availability_db extraído del PostgreSQL real con:
-- pg_dump -U postgres -d availability_db --schema-only --no-owner --no-privileges
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
-- Name: holds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.holds (
    hold_id uuid NOT NULL,
    room_id uuid NOT NULL,
    check_in date NOT NULL,
    check_out date NOT NULL,
    units integer NOT NULL,
    status text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT holds_check CHECK ((check_out > check_in)),
    CONSTRAINT holds_status_check CHECK ((status = ANY (ARRAY['HELD'::text, 'CONFIRMED'::text, 'RELEASED'::text, 'EXPIRED'::text]))),
    CONSTRAINT holds_units_check CHECK ((units > 0))
);


--
-- Name: inventory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventory (
    room_id uuid NOT NULL,
    hotel_id uuid NOT NULL,
    night date NOT NULL,
    total integer NOT NULL,
    held integer DEFAULT 0 NOT NULL,
    confirmed integer DEFAULT 0 NOT NULL,
    CONSTRAINT inventory_check CHECK (((held + confirmed) <= total)),
    CONSTRAINT inventory_confirmed_check CHECK ((confirmed >= 0)),
    CONSTRAINT inventory_held_check CHECK ((held >= 0)),
    CONSTRAINT inventory_total_check CHECK ((total >= 0))
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: holds holds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holds
    ADD CONSTRAINT holds_pkey PRIMARY KEY (hold_id);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (room_id, night);


--
-- Name: idx_holds_expires_held; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_holds_expires_held ON public.holds USING btree (expires_at) WHERE (status = 'HELD'::text);


--
-- Name: idx_inventory_hotel_night; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_inventory_hotel_night ON public.inventory USING btree (hotel_id, night);


--
-- PostgreSQL database dump complete
--


