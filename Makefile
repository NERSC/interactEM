# Directories
SCRIPTS_DIR := ./scripts
DOCKER_DIR := ./docker
FRONTEND_DIR := ./frontend/interactEM
OPERATORS_DIR := ./operators

# Makefile configuration
.PHONY: help setup setup-docker-registry services docker-up docker-down clean lint operators check-docker-permission
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

# Reusable function
define success
	@echo "✓ $(1)"
endef

define section
	@echo "\n$(1)"
endef

define check_not_root
	@if [ "$$(id -u)" -eq 0 ]; then \
		echo "Error: This command should not be run as root" >&2; \
		echo "Please run 'make $(1)' without sudo" >&2; \
		exit 1; \
	fi
endef

define check_uv_installed
	@if ! command -v uv &> /dev/null; then \
		echo "Error: 'uv' is required to run 'make operators' but is not installed" >&2; \
		exit 1; \
	fi
endef

# Auto-generated help from target comments
help: ## Show this help message
	@echo "Available targets:"
	@grep -E "^[a-zA-Z_-]+:.*##" $(MAKEFILE_LIST) | \
		sed -E 's/^([a-zA-Z_-]+):.*## */\1|/' | \
		column -t -s '|' | sed 's/^/  /'
	@echo ""

# Check if we can run docker commands
check-docker-permission:
	$(SCRIPTS_DIR)/check-docker-permission.sh
	$(call success,Docker permission check passed)

setup: ## Setup .env file with generated secure secrets
	$(call check_not_root,setup)
	$(call section,Setting up environment...)
	@echo "Copying .env.example files to .env..."
	$(SCRIPTS_DIR)/copy-dotenv.sh
	$(SCRIPTS_DIR)/setup-podman-socket.sh
	$(SCRIPTS_DIR)/setup-secrets.sh
	$(call success,Environment setup complete! Next steps:)
	@echo "  1. Edit .env to add GITHUB_USERNAME and GITHUB_TOKEN"
	@echo "  2. Run 'make docker-up' to build + start services."

services: check-docker-permission ## Build Docker images for all services
	@echo "Building Docker images..."
	$(DOCKER_DIR)/bake.sh

docker-up: services ## Start all services with docker-compose
	@docker compose up --force-recreate --remove-orphans --build -d
	$(call success,Services started)
	@echo "  Visit http://localhost:5173 in your browser"
	@echo ""
	@echo "Login credentials:"
	@grep "FIRST_SUPERUSER_USERNAME\|FIRST_SUPERUSER_PASSWORD" .env | sed 's/^/  /'
	@echo ""

docker-down: ## Stop all services
	@docker compose down

clean: ## Stop services and remove volumes (WARNING: will delete database data)
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
	$(call success,Linting complete)

## Set up local Docker registry for operator builds
setup-docker-registry: check-docker-permission 
	$(call section,Setting up local Docker registry...)
	$(SCRIPTS_DIR)/setup-docker-registry.sh

operator: setup-docker-registry ## Build a specific operator and push to local podman registry (use target=OPERATOR_NAME)
	$(call check_uv_installed)
	@if [ -z "$(target)" ]; then \
		echo "Error: target variable not set. Usage: make operator target=OPERATOR_NAME" >&2; \
		exit 1; \
	fi
	$(call section,Building operator $(target)...)
	$(OPERATORS_DIR)/bake.sh --push-local --pull-local --build-base --target $(target)
	$(call success,Operator $(target) built and pushed to local registry)

operators: setup-docker-registry ## Build all operators and push to local podman registry
	$(call check_uv_installed)
	$(call section,Building operators...)
	$(OPERATORS_DIR)/bake.sh --push-local --pull-local --build-base
	$(call success,Operators built and pushed to local registry)
