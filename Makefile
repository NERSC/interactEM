# Directories
SCRIPTS_DIR := ./scripts
DOCKER_DIR := ./docker
FRONTEND_DIR := ./frontend/interactEM
OPERATORS_DIR := ./operators

# Makefile configuration
.PHONY: help setup setup-docker-registry images docker-up docker-down clean lint build-operators
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

# Reusable function
define success
	@echo "✓ $(1)"
endef

define section
	@echo "\n$(1)"
endef

# Auto-generated help from target comments
help: ## Show this help message
	@echo "Available targets:"
	@grep -E "^[a-zA-Z_-]+:.*##" $(MAKEFILE_LIST) | \
		sed -E 's/^([a-zA-Z_-]+):.*## */\1|/' | sort | \
		column -t -s '|' | sed 's/^/  /'
	@echo ""

setup: ## Setup .env file with generated secure secrets
	$(call section,Setting up environment, do not run this as root...)
	@echo "Copying .env.example files to .env..."
	$(SCRIPTS_DIR)/copy-dotenv.sh
	@echo "Generating secure secrets..."
	$(SCRIPTS_DIR)/setup-secrets.sh
	$(call success,Environment setup complete! Next steps:)
	@echo "  1. Edit .env to add GITHUB_USERNAME and GITHUB_TOKEN"
	@echo "  2. Run 'make docker-up' to build + start services (NOTE: may need to run this as root)."

images: ## Build Docker images for all services
	@echo "Building Docker images (may need to run this as root if it fails)..."
	$(DOCKER_DIR)/bake.sh

docker-up: images ## Start all services with docker-compose
	@docker compose up --force-recreate --remove-orphans --build -d
	$(call success,Services started)
	@echo "  Visit http://localhost:5173 in your browser"
	@echo ""
	@echo "Login credentials:"
	@grep "FIRST_SUPERUSER_USERNAME\|FIRST_SUPERUSER_PASSWORD" .env | sed 's/^/  /'
	@echo ""

docker-down: ## Stop all services
	@docker compose down

clean: ## Stop services and remove volumes
	@docker compose down -v
	$(call success,Services stopped and volumes removed)

lint: ## Run backend (ruff) and frontend (biome) linters
	@echo "Running ruff linter..."
	. .venv/bin/activate && poetry run ruff check .
	@echo "Running biome linter..."
	cd $(FRONTEND_DIR) && npx biome check \
	    --formatter-enabled=true \
	    --linter-enabled=true \
	    --organize-imports-enabled=true \
	    --write \
	    ./src
	@echo "✓ Linting complete"
