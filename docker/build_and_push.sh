#!/bin/bash

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)
PODMAN=${1:-p}

# Build all images
$SCRIPT_DIR/build.sh $PODMAN
if [ $? -ne 0 ]; then
    echo "Failed to build images"
    exit 1
fi

# Function to extract error context from log file
extract_error_context() {
    local logfile="$1"
    local lines=${2:-10}  # Default to last 10 lines
    
    if [ -s "$logfile" ]; then
        echo "Error context (last $lines lines):"
        echo "--------------------------------------------------------------------------------"
        tail -n "$lines" "$logfile"
        echo "--------------------------------------------------------------------------------"
    else
        echo "No log data available."
    fi
}

# Function to push both tags of an image
push_image() {
    local name=$1
    local logfile="/tmp/push_${name}.log"
    local success=true
    
    echo "Pushing ghcr.io/nersc/interactem/${name}:$TAG..."
    docker push ghcr.io/nersc/interactem/${name}:$TAG > "$logfile" 2>&1
    if [ $? -ne 0 ]; then
        echo "✗ Failed to push ghcr.io/nersc/interactem/${name}:$TAG"
        extract_error_context "$logfile"
        success=false
    else
        echo "✓ Successfully pushed ${name}:$TAG"
    fi
    
    echo "Pushing ghcr.io/nersc/interactem/${name}:latest..."
    docker push ghcr.io/nersc/interactem/${name}:latest >> "$logfile" 2>&1
    if [ $? -ne 0 ]; then
        echo "✗ Failed to push ghcr.io/nersc/interactem/${name}:latest"
        extract_error_context "$logfile"
        success=false
    else
        echo "✓ Successfully pushed ghcr.io/nersc/interactem/${name}:latest"
    fi
    
    # Cleanup
    rm -f "$logfile"
    
    if [ "$success" = true ]; then
        return 0
    else
        return 1
    fi
}

# Define services
SERVICES="operator callout fastapi launcher orchestrator frontend"

# Push images sequentially
failed_services=()
successful_services=()

echo "Starting push of all images..."
for service in $SERVICES; do
    echo ""
    echo "==== Pushing ${service} images ===="
    if push_image "$service"; then
        successful_services+=("$service")
    else
        failed_services+=("$service")
    fi
done

# Print summary
echo ""
echo "Push Summary:"
echo "- Successful pushes: ${#successful_services[@]}"
echo "- Failed pushes: ${#failed_services[@]}"
echo "- Total services: ${#SERVICES}"
echo ""

if [ ${#failed_services[@]} -gt 0 ]; then
    echo "Failed services: ${failed_services[*]}"
    exit 1
else
    echo "All images pushed successfully"
    exit 0
fi