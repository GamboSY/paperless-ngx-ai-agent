.PHONY: help build start stop restart logs test run clean

help:
	@echo "Paperless-NGX AI Agent - Docker Management"
	@echo ""
	@echo "Verfügbare Befehle:"
	@echo "  make build    - Docker Image bauen"
	@echo "  make start    - Container starten"
	@echo "  make stop     - Container stoppen"
	@echo "  make restart  - Container neustarten"
	@echo "  make logs     - Logs anzeigen"
	@echo "  make test     - Verbindung testen"
	@echo "  make run      - Einmalig ausführen"
	@echo "  make clean    - Container und Volumes entfernen"

build:
	@echo "Building Docker image..."
	docker-compose build

start:
	@echo "Starting container..."
	@mkdir -p logs
	docker-compose up -d
	@echo "Container gestartet! Logs: make logs"

stop:
	@echo "Stopping container..."
	docker-compose stop

restart:
	@echo "Restarting container..."
	docker-compose restart

logs:
	docker-compose logs -f

test:
	@echo "Testing connections..."
	docker-compose run --rm paperless-ai-agent python test_connection.py

run:
	@echo "Running agent once..."
	docker-compose run --rm paperless-ai-agent python main.py

run-dry:
	@echo "Running agent in dry-run mode..."
	docker-compose run --rm paperless-ai-agent python main.py --dry-run

clean:
	@echo "Removing containers and volumes..."
	docker-compose down -v
