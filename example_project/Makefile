COMPOSE_FILE := docker-compose.yml

.PHONY: dev devd down logs shell migrate bootstrap

dev:
	docker compose -f $(COMPOSE_FILE) up --build

devd:
	docker compose -f $(COMPOSE_FILE) up --build -d

down:
	docker compose -f $(COMPOSE_FILE) down

logs:
	docker compose -f $(COMPOSE_FILE) logs -f web

shell:
	docker compose -f $(COMPOSE_FILE) exec web sh

migrate:
	docker compose -f $(COMPOSE_FILE) exec web python manage.py migrate

bootstrap:
	docker compose -f $(COMPOSE_FILE) exec web python manage.py bootstrap_demo
