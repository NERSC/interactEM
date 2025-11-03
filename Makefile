.PHONY: setup help env-setup docker-up docker-down clean

help:
	@echo "interactEM - Local Development Setup"
	@echo ""
	@echo "Available targets:"
	@echo "  make setup          - Complete setup (copies .env and generates secrets)"
	@echo "  make env-setup      - Setup .env file with generated secure secrets"
	@echo "  make docker-up      - Start all services with docker-compose"
	@echo "  make docker-down    - Stop all services"
	@echo "  make clean          - Stop services and remove volumes"

env-setup:
	@echo "Setting up environment..."
	@echo "Copying .env.example files to .env..."
	@bash scripts/copy-dotenv.sh
	@echo "Generating secure secrets..."
	@bash scripts/setup-secrets.sh

setup: env-setup
	@echo ""
	@echo "Building Docker images..."
	@bash docker/bake.sh
	@echo ""
	@echo "✓ Setup complete! Next steps:"
	@echo "  1. Edit .env to add GITHUB_USERNAME and GITHUB_TOKEN"
	@echo "  2. Run 'make docker-up' to start services"
	@echo "  3. Visit http://localhost:5173 in your browser"
	@echo ""
	@echo "Frontend login credentials:"
	@grep "FIRST_SUPERUSER_USERNAME\|FIRST_SUPERUSER_PASSWORD" .env | sed 's/^/  /'

docker-up:
	docker compose up --force-recreate --remove-orphans --build -d
	@echo "✓ Services started"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Backend: http://localhost:8080"
	@echo ""
	@echo "Frontend login credentials:"
	@grep "FIRST_SUPERUSER_USERNAME\|FIRST_SUPERUSER_PASSWORD" .env | sed 's/^/  /'

docker-down:
	docker compose down

clean: docker-down
	docker compose down -v
	@echo "✓ Services stopped and volumes removed"