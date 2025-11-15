#!/bin/bash

# Script to update PODMAN_SERVICE_URI in all .env files with the actual podman socket path

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Setting up AGENT_PODMAN_SERVICE_URI in .env files..."

# Get the podman socket path in the unix:// format
PODMAN_SERVICE_URI=$("$SCRIPT_DIR/podman-socket-path.sh")

if [ -z "$PODMAN_SERVICE_URI" ]; then
    echo "Error: Could not determine podman socket URI" >&2
    exit 1
fi

echo "Using podman socket URI: $PODMAN_SERVICE_URI"
echo ""

# Update AGENT_PODMAN_SERVICE_URI in root .env
updated_count=0

if grep -q "AGENT_PODMAN_SERVICE_URI=" "$REPO_ROOT/.env"; then
    # Use sed to replace the AGENT_PODMAN_SERVICE_URI line
    # This handles both placeholder values and existing values
    sed -i.bak "s|^AGENT_PODMAN_SERVICE_URI=.*|AGENT_PODMAN_SERVICE_URI=$PODMAN_SERVICE_URI|" "$REPO_ROOT/.env"
    echo "✓ Updated: $REPO_ROOT/.env"
    # Clean up backup file
    rm -f "$REPO_ROOT/.env.bak"
    updated_count=$((updated_count + 1))
fi

# Also update legacy backend/agent/.env if it still exists as separate file
if grep -q "PODMAN_SERVICE_URI=" "$REPO_ROOT/backend/agent/.env" 2>/dev/null; then
    sed -i.bak "s|^PODMAN_SERVICE_URI=.*|PODMAN_SERVICE_URI=$PODMAN_SERVICE_URI|" "$REPO_ROOT/backend/agent/.env"
    echo "✓ Updated: $REPO_ROOT/backend/agent/.env"
    rm -f "$REPO_ROOT/backend/agent/.env.bak"
    updated_count=$((updated_count + 1))
fi

echo ""
echo "Summary:"
echo "  Updated: $updated_count .env file(s)"
