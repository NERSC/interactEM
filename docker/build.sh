#!/usr/bin/env bash

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)
PODMAN=${1:-p}

if [ $PODMAN == "p" ]; then
    DOCKER=podman
    platform=$(uname -m)
    if [ $platform == "x86_64" ]; then
        PLATFORM="--platform=linux/amd64"
    elif [ $platform == "aarch64" ]; then
        PLATFORM="--platform=linux/arm64"
    elif [ $platform == "arm64" ]; then
        PLATFORM="--platform=linux/arm64"
    else
        echo "Unsupported platform: $platform"
        exit 1
    fi
else
    DOCKER=docker
    PLATFORM="--platform=linux/amd64,linux/arm64"
fi

# Build function with context parameter
build_image() {
    local name=$1
    local dockerfile=$2
    local context=$3
    local logfile="/tmp/build_${name}.log"
    
    echo "Starting build for ghcr.io/nersc/interactem/${name}:$TAG..."
    $DOCKER build $PLATFORM \
        -t ghcr.io/nersc/interactem/${name}:latest \
        -t ghcr.io/nersc/interactem/${name}:$TAG \
        -f $SCRIPT_DIR/${dockerfile} \
        ${context} > $logfile 2>&1
    
    echo $? > "/tmp/build_${name}.exit"
}

# Build base image first
BASE_IMAGE="ghcr.io/nersc/interactem/interactem"
$DOCKER build $PLATFORM -t $BASE_IMAGE:latest -t $BASE_IMAGE:$TAG -f $SCRIPT_DIR/Dockerfile.base $ROOT_DIR/backend
if [ $? -ne 0 ]; then
    echo "Failed to build $BASE_IMAGE"
    exit 1
fi

# Define services, their Dockerfiles, and build contexts
SERVICES="operator callout fastapi launcher orchestrator frontend metrics"
DOCKERFILES="Dockerfile.operator Dockerfile.callout Dockerfile.fastapi Dockerfile.launcher Dockerfile.orchestrator Dockerfile.frontend Dockerfile.metrics"
CONTEXTS="$ROOT_DIR/backend $ROOT_DIR/backend $ROOT_DIR/backend $ROOT_DIR/backend $ROOT_DIR/backend $ROOT_DIR/frontend $ROOT_DIR/backend"

# Start all builds in parallel
i=0
for service in $SERVICES; do
    dockerfile=$(echo $DOCKERFILES | cut -d' ' -f$((i+1)))
    context=$(echo $CONTEXTS | cut -d' ' -f$((i+1)))
    build_image "$service" "$dockerfile" "$context" &
    i=$((i+1))
done

# Wait for all background processes to complete
wait

# Check results
failed=0
for service in $SERVICES; do
    exit_code=$(cat "/tmp/build_${service}.exit")
    if [ "$exit_code" != "0" ]; then
        echo "Build failed for ${service}:"
        cat "/tmp/build_${service}.log"
        failed=1
    else
        echo "Build succeeded for ${service}"
    fi
    # Cleanup
    rm -f "/tmp/build_${service}.log" "/tmp/build_${service}.exit"
done

if [ "$failed" == "1" ]; then
    echo "One or more builds failed"
    exit 1
fi

echo "All builds completed successfully"