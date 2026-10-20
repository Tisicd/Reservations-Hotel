.PHONY: up up-dev down test lint clean clean-all secrets deps seed invariants e2e snapshot-availability snapshot-payment snapshot-reservation snapshot-customer snapshot-hotel

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

up-dev: secrets
	$(COMPOSE_DEV) up -d --build --wait

down:
	docker compose down

clean:
	docker compose down -v

clean-all:
	docker compose down -v
	$(PYTHON) -c "import pathlib; pathlib.Path('secrets/seed.json').unlink(missing_ok=True)"

lint: deps
	docker compose config -q
	docker compose -f compose.yaml -f compose.dev.yaml config -q
	cd services/customer && $(CURDIR)/$(VENV_PY) -m ruff check .
	cd services/hotel && $(CURDIR)/$(VENV_PY) -m ruff check .
	cd services/availability && $(CURDIR)/$(VENV_PY) -m ruff check .
	cd services/availability && $(CURDIR)/$(LINT_IMPORTS)
	cd services/payment && $(CURDIR)/$(VENV_PY) -m ruff check .
	cd services/payment && $(CURDIR)/$(LINT_IMPORTS)
	cd services/reservation && $(CURDIR)/$(VENV_PY) -m ruff check .
	cd services/reservation && $(CURDIR)/$(LINT_IMPORTS)

test: deps
	$(COMPOSE_DEV) up -d --wait postgres availability availability-worker payment payment-worker reservation
	$(VENV_PY) -m pytest tests/infra
	-$(COMPOSE_DEV) stop availability-worker payment-worker reservation-worker
	cd services/availability && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/payment && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/customer && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/hotel && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/reservation && $(CURDIR)/$(VENV_PY) -m pytest
	$(VENV_PY) -m pytest tests/invariants

snapshot-availability: deps
	cd services/availability && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py

snapshot-payment: deps
	cd services/payment && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py

snapshot-reservation: deps
	cd services/reservation && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py

seed: deps
	$(VENV_PY) scripts/seed.py

invariants: deps
	$(VENV_PY) tests/invariants/checker.py --grace 60

e2e: up-dev seed
	$(VENV_PY) -m pytest tests/e2e -q

snapshot-customer: deps
	cd services/customer && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py

snapshot-hotel: deps
	cd services/hotel && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py