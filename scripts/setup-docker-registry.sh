#!/bin/bash
set -euo pipefail

# Set up local Docker registry for operator builds
echo "Setting up local Docker registry for operator builds..."

REGISTRY_NAME="docker-registry"
REGISTRY_PORT="5001"
REGISTRY_CONTAINER_PORT="5000"

if docker ps --filter "name=$REGISTRY_NAME" --format "{{.Names}}" | grep -q "$REGISTRY_NAME"; then
    echo "✓ Docker registry already running on localhost:$REGISTRY_PORT"
else
    docker run -d \
        -p "$REGISTRY_PORT:$REGISTRY_CONTAINER_PORT" \
        --restart always \
        --name "$REGISTRY_NAME" \
        registry:3
    echo "✓ Docker registry started on localhost:$REGISTRY_PORT"
fi