#!/bin/bash

# Script to update PODMAN_SERVICE_URI in all .env files with the actual podman socket path

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Setting up PODMAN_SERVICE_URI in .env files..."

# Get the podman socket path in the unix:// format
PODMAN_SERVICE_URI=$("$SCRIPT_DIR/podman-socket-path.sh")

if [ -z "$PODMAN_SERVICE_URI" ]; then
    echo "Error: Could not determine podman socket URI" >&2
    exit 1
fi

echo "Using podman socket URI: $PODMAN_SERVICE_URI"
echo ""

# Find all .env files and update PODMAN_SERVICE_URI
updated_count=0

while IFS= read -r -d '' env_file; do
    if grep -q "PODMAN_SERVICE_URI=" "$env_file"; then
        # Use sed to replace the PODMAN_SERVICE_URI line
        # This handles both placeholder values and existing values
        sed -i.bak "s|^PODMAN_SERVICE_URI=.*|PODMAN_SERVICE_URI=$PODMAN_SERVICE_URI|" "$env_file"
        echo "✓ Updated: $env_file"
        # Clean up backup file
        rm -f "${env_file}.bak"
        updated_count=$((updated_count + 1))
    fi
done < <(find "$REPO_ROOT" -name ".env" -type f -print0)

echo ""
echo "Summary:"
echo "  Updated: $updated_count .env file(s)"
