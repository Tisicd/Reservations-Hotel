.PHONY: up down test lint clean clean-all secrets deps snapshot-availability snapshot-payment

PYTHON ?= python
VENV := .venv
ifeq ($(OS),Windows_NT)
VENV_PY := $(VENV)/Scripts/python.exe
LINT_IMPORTS := $(VENV)/Scripts/lint-imports.exe
else
VENV_PY := $(VENV)/bin/python
LINT_IMPORTS := $(VENV)/bin/lint-imports
endif

COMPOSE_DEV = docker compose -f compose.yaml -f compose.dev.yaml

secrets:
	$(PYTHON) scripts/gen_secrets.py

deps:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PY) -m pip install -q --upgrade pip
	$(VENV_PY) -m pip install -q -r tests/requirements.txt

up: secrets
	docker compose up -d --build --wait

down:
	docker compose down

clean:
	docker compose down -v

clean-all:
	docker compose down -v

lint: deps
	docker compose config -q
	docker compose -f compose.yaml -f compose.dev.yaml config -q
	cd services/availability && $(CURDIR)/$(VENV_PY) -m ruff check .
	cd services/availability && $(CURDIR)/$(LINT_IMPORTS)
	cd services/payment && $(CURDIR)/$(VENV_PY) -m ruff check .
	cd services/payment && $(CURDIR)/$(LINT_IMPORTS)

test: deps
	$(COMPOSE_DEV) up -d --wait postgres
	$(VENV_PY) -m pytest tests/infra
	cd services/availability && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/payment && $(CURDIR)/$(VENV_PY) -m pytest

snapshot-availability: deps
	cd services/availability && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py

snapshot-payment: deps
	cd services/payment && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py
