.PHONY: up up-dev down test lint clean clean-all secrets deps seed invariants e2e smoke gateway-refresh snapshot-availability snapshot-payment snapshot-reservation snapshot-customer snapshot-hotel snapshot-notification build images prune ensure-images

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

# Construye las imagenes :local de los 6 servicios (cache de capas reutilizable).
build:
	docker compose build

# Tabla de imagenes del proyecto + recuento de huerfanas.
images:
	$(PYTHON) scripts/docker_images.py

# Elimina imagenes dangling del proyecto. Filtra por label para no tocar
# imagenes de otros proyectos. NO usa prune global.
prune:
	docker image prune -f --filter "label=com.docker.compose.project=reservas-platform"
	docker image prune -f --filter "label=com.reservas.project=reservas-platform"

# Verifica que existan las imagenes :local. Si falta alguna, falla indicando
# 'make build'. up/test/e2e/smoke NUNCA construyen imagenes.
ensure-images:
	@$(PYTHON) scripts/docker_images.py --check

up: secrets ensure-images
	docker compose up -d --no-build --wait

up-dev: secrets ensure-images
	$(COMPOSE_DEV) up -d --no-build --wait

# Tras recrear contenedores, nginx puede conservar IPs viejas hasta el TTL del
# resolver. Reiniciarlo deja el stack determinista para pruebas y smoke.
gateway-refresh:
	$(COMPOSE_DEV) up -d --no-build --wait
	$(COMPOSE_DEV) restart gateway
	$(COMPOSE_DEV) up -d --no-build --wait gateway

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
	cd services/notification && $(CURDIR)/$(VENV_PY) -m ruff check .
	cd services/notification && $(CURDIR)/$(LINT_IMPORTS)

test: deps ensure-images gateway-refresh
	$(VENV_PY) -m pytest tests/infra
	-$(COMPOSE_DEV) stop availability-worker payment-worker reservation-worker
	cd services/availability && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/payment && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/customer && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/hotel && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/reservation && $(CURDIR)/$(VENV_PY) -m pytest
	cd services/notification && $(CURDIR)/$(VENV_PY) -m pytest
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

e2e: up-dev gateway-refresh seed
	$(VENV_PY) -m pytest tests/e2e -q

smoke: deps ensure-images gateway-refresh
	$(VENV_PY) -m pytest tests/infra/test_gateway.py -q

snapshot-customer: deps
	cd services/customer && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py

snapshot-hotel: deps
	cd services/hotel && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py

snapshot-notification: deps
	cd services/notification && $(CURDIR)/$(VENV_PY) tests/contract/gen_snapshot.py