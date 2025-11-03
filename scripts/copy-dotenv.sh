#!/bin/bash

# Script to copy all .env.example files to .env in their respective folders
# Only copies if .env doesn't already exist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Searching for .env.example files in $REPO_ROOT..."
echo ""

copied_count=0
skipped_count=0

# Find all .env.example files and copy them
while IFS= read -r -d '' env_example_file; do
  env_dir="$(dirname "$env_example_file")"
  env_file="$env_dir/.env"
  
  if [ -f "$env_file" ]; then
    echo "⊘ Skipped: $env_file (already exists)"
    skipped_count=$((skipped_count + 1))
  else
    cp "$env_example_file" "$env_file"
    echo "✓ Copied: $env_example_file → $env_file"
    copied_count=$((copied_count + 1))
  fi
done < <(find "$REPO_ROOT" -name ".env.example" -type f -print0)

echo ""
echo "Summary:"
echo "  Copied: $copied_count"
echo "  Skipped: $skipped_count"
