.PHONY: up down test lint clean clean-all secrets deps

PYTHON ?= python
VENV := .venv
ifeq ($(OS),Windows_NT)
VENV_PY := $(VENV)/Scripts/python.exe
else
VENV_PY := $(VENV)/bin/python
endif

COMPOSE_DEV = docker compose -f compose.yaml -f compose.dev.yaml

secrets:
	$(PYTHON) scripts/gen_secrets.py

deps:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PY) -m pip install -q --upgrade pip
	$(VENV_PY) -m pip install -q -r tests/requirements.txt

up: secrets
	docker compose up -d --wait

down:
	docker compose down

clean:
	docker compose down -v

clean-all:
	docker compose down -v

lint: deps
	docker compose config -q
	docker compose -f compose.yaml -f compose.dev.yaml config -q

test: deps
	$(COMPOSE_DEV) up -d --wait postgres
	$(VENV_PY) -m pytest tests/infra
