#!/bin/bash
# Setup secure secrets in .env files across the project
# Only replaces values if they still have default placeholder values

set -euo pipefail

echo "Generating secure secrets..."

# Generate all secrets
SECRET_KEY=$(podman run --rm alpine/openssl rand -hex 32) || { echo "Failed to generate SECRET_KEY"; exit 1; }
POSTGRES_PASSWORD=$(podman run --rm alpine/openssl rand -hex 32) || { echo "Failed to generate POSTGRES_PASSWORD"; exit 1; }
FIRST_SUPERUSER_PASSWORD=$(podman run --rm alpine/openssl rand -hex 16) || { echo "Failed to generate FIRST_SUPERUSER_PASSWORD"; exit 1; }
EXTERNAL_SECRET_KEY=$(podman run --rm alpine/openssl rand -hex 32) || { echo "Failed to generate EXTERNAL_SECRET_KEY"; exit 1; }
ORCHESTRATOR_API_KEY=$(podman run --rm alpine/openssl rand -hex 32) || { echo "Failed to generate ORCHESTRATOR_API_KEY"; exit 1; }
INTERACTEM_PW=$FIRST_SUPERUSER_PASSWORD

echo "Secrets generated. Updating .env files..."

# Helper function to safely replace values in a file only if they have default placeholder values
update_env_file() {
    local file=$1
    local key=$2
    local default_value=$3
    local new_value=$4
    
    if [ ! -f "$file" ]; then
        return 0
    fi
    
    # Check if the current value matches the default placeholder
    local current_value
    current_value=$(grep "^${key}=" "$file" 2>/dev/null | cut -d= -f2- || true)
    
    # Only update if current value matches the default placeholder
    if [ "$current_value" = "$default_value" ]; then
        local tmp_file
        tmp_file=$(mktemp) || { echo "Failed to create temporary file"; exit 1; }
        
        if sed "s/^${key}=.*/${key}=${new_value}/" "$file" > "$tmp_file"; then
            if mv "$tmp_file" "$file"; then
                echo "  ✓ Updated ${key} in ${file}"
            else
                echo "  ✗ Failed to update ${file}" >&2
                rm -f "$tmp_file"
                exit 1
            fi
        else
            echo "  ✗ Failed to process ${file}" >&2
            rm -f "$tmp_file"
            exit 1
        fi
    else
        echo "  ⊘ Skipped ${key} in ${file} (already has custom value)"
    fi
}

# Update root .env
update_env_file ".env" "SECRET_KEY" "changethis" "$SECRET_KEY"
update_env_file ".env" "FIRST_SUPERUSER_PASSWORD" "changethis" "$FIRST_SUPERUSER_PASSWORD"
update_env_file ".env" "POSTGRES_PASSWORD" "changethis" "$POSTGRES_PASSWORD"
update_env_file ".env" "EXTERNAL_SECRET_KEY" "changeme" "$EXTERNAL_SECRET_KEY"
update_env_file ".env" "ORCHESTRATOR_API_KEY" "changethis" "$ORCHESTRATOR_API_KEY"

# Update backend/orchestrator/.env if it exists
update_env_file "backend/orchestrator/.env" "ORCHESTRATOR_API_KEY" "changethis" "$ORCHESTRATOR_API_KEY"

# Update cli/.env if it exists
update_env_file "cli/.env" "INTERACTEM_PASSWORD" "changethis" "$INTERACTEM_PW"

# Update backend/callout/service/.env if it exists
update_env_file "backend/callout/service/.env" "JWT_SECRET_KEYS" "changethis" "$SECRET_KEY"