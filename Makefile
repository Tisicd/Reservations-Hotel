.PHONY: up down test lint clean

COMPOSE_DEV = docker compose -f compose.yaml -f compose.dev.yaml

up:
	docker compose up -d --wait

down:
	docker compose down

clean:
	docker compose down -v

lint:
	docker compose config -q
	docker compose -f compose.yaml -f compose.dev.yaml config -q

test:
	$(COMPOSE_DEV) up -d --wait postgres
	$(COMPOSE_DEV) exec -T postgres bash /scripts/test_role_isolation.sh
