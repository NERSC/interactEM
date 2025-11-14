#!/bin/bash

set -euo pipefail

GIT_ROOT_DIR=$(git rev-parse --show-toplevel)
FAILED_DIR=""

# Error handler
trap 'error_handler' ERR

error_handler() {
    local line_num=$1
    echo "❌ Error in $FAILED_DIR at line $line_num" >&2
    exit 1
}

# Function to update locks in a directory
update_directory() {
    local dir=$1
    FAILED_DIR="$dir"

    # Validate directory exists
    if [[ ! -d "$GIT_ROOT_DIR/$dir" ]]; then
        echo "❌ Directory not found: $GIT_ROOT_DIR/$dir" >&2
        return 1
    fi

    # Validate pyproject.toml exists
    if [[ ! -f "$GIT_ROOT_DIR/$dir/pyproject.toml" ]]; then
        echo "❌ No pyproject.toml found in $dir" >&2
        return 1
    fi

    echo "Updating locks in $dir..."
    cd "$GIT_ROOT_DIR/$dir" || return 1

    uv venv .venv --clear || { echo "❌ Failed to create venv in $dir" >&2; return 1; }
    source .venv/bin/activate || { echo "❌ Failed to activate venv in $dir" >&2; return 1; }
    poetry lock || { echo "❌ Failed to lock dependencies in $dir" >&2; return 1; }
    poetry install || { echo "❌ Failed to install dependencies in $dir" >&2; return 1; }
    uv sync || { echo "❌ Failed to sync with uv in $dir" >&2; return 1; }

    echo "✓ Completed $dir"
}

# List of directories to update in order
directories=(
    "backend/core"
    "backend/sfapi_models"
    "backend/app"
    "backend/agent"
    "backend/orchestrator"
    "backend/operators"
    "backend/metrics"
    "backend/launcher"
    "operators/distiller-streaming"
    "docs"
    "cli"
    "."
)

# Run updates for each directory
for dir in "${directories[@]}"; do
    update_directory "$dir"
done

echo "All locks updated successfully!"
