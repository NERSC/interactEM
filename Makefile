.SHELLFLAGS := -e -c
.PHONY: help setup images docker-up docker-down clean lint

help:
	@echo "interactEM - Local Development Setup"
	@echo ""
	@echo "Available targets:"
	@echo "  make setup          - Setup .env file with generated secure secrets"
	@echo "  make images         - Build Docker images for all services"
	@echo "  make docker-up      - Start all services with docker-compose"
	@echo "  make docker-down    - Stop all services"
	@echo "  make clean          - Stop services and remove volumes"
	@echo "  make lint           - Run backend (ruff) and frontend (biome) linters"
	@echo ""

setup:
	@echo "Setting up environment, do not run this as root..."
	@echo "Copying .env.example files to .env..."
	./scripts/copy-dotenv.sh
	@echo "Generating secure secrets..."
	./scripts/setup-secrets.sh
	@echo "✓ Environment setup complete! Next steps:"
	@echo "  1. Edit .env to add GITHUB_USERNAME and GITHUB_TOKEN"
	@echo "  2. Run 'make docker-up' to build + start services (NOTE: may need to run this as root)."

images:
	@echo "Building Docker images (may need to run this as root if it fails)..."
	./docker/bake.sh

docker-up: images
	@docker compose up --force-recreate --remove-orphans --build -d
	@echo "✓ Services started"
	@echo "  Visit http://localhost:5173 in your browser"
	@echo ""
	@echo "Login credentials:"
	@grep "FIRST_SUPERUSER_USERNAME\|FIRST_SUPERUSER_PASSWORD" .env | sed 's/^/  /'
	@echo ""

docker-down:
	docker compose down

clean: docker-down
	docker compose down -v
	@echo "✓ Services stopped and volumes removed"

lint:
	@echo "Running ruff linter..."
	. .venv/bin/activate && poetry run ruff check .
	@echo "Running biome linter..."
	cd frontend/interactEM && npx biome check \
	    --formatter-enabled=true \
	    --linter-enabled=true \
	    --organize-imports-enabled=true \
	    --write \
	    ./src
	@echo "✓ Linting complete"
