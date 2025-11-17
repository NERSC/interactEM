#!/bin/bash
# Ensure credential files exist as files (not directories) before docker-compose mount
# This prevents Docker from creating directories during bind mounting of non-existent files

set -euo pipefail

# Find the git repository root
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "Error: Not in a git repository" >&2
    exit 1
}

CREDS_DIR="$GIT_ROOT/conf/nats-conf/out_jwt"

# Credential files that are bind-mounted in docker-compose
credential_files=(
    "backend.creds"
    "frontend.creds"
    "operator.creds"
    "callout.creds"
)

# Create parent directory if it doesn't exist
mkdir -p "$CREDS_DIR"

# Check and fix credential files
for file in "${credential_files[@]}"; do
    filepath="$CREDS_DIR/$file"

    if [ -d "$filepath" ]; then
        # If it's a directory, remove it and create as file
        echo "⚠ Found directory instead of file: $filepath, fixing..."
        rm -rf "$filepath"
        touch "$filepath"
        echo "✓ Converted directory to file: $filepath"
    elif [ ! -e "$filepath" ]; then
        # If it doesn't exist, create as empty file
        touch "$filepath"
        echo "✓ Created placeholder file: $filepath"
    fi
done
