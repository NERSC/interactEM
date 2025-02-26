#!/bin/bash

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)
ORG=${1:-interactem}
PODMAN=${2:-p}

# Build all images
$SCRIPT_DIR/build.sh $ORG $PODMAN
if [ $? -ne 0 ]; then
    echo "Failed to build images"
    exit 1
fi

# Function to push both tags of an image
push_image() {
    local name=$1
    local logfile="/tmp/push_${name}.log"
    
    echo "Pushing $ORG/interactem-${name}:$TAG..."
    docker push $ORG/interactem-${name}:$TAG > "$logfile" 2>&1
    echo $? > "/tmp/push_${name}.tag.exit"
    echo "Pushing $ORG/interactem-${name}:latest..."
    docker push $ORG/interactem-${name}:latest >> "$logfile" 2>&1
    echo $? > "/tmp/push_${name}.latest.exit"
}

# Define services
SERVICES="operator callout fastapi launcher orchestrator frontend"

# Push all images in parallel
for service in $SERVICES; do
    push_image "$service" &
done

# Wait for all pushes to complete
wait

# Check results
failed=0
for service in $SERVICES; do
    tag_exit_code=$(cat "/tmp/push_${service}.tag.exit")
    latest_exit_code=$(cat "/tmp/push_${service}.latest.exit")
    
    if [ "$tag_exit_code" != "0" ] || [ "$latest_exit_code" != "0" ]; then
        echo "Push failed for ${service}:"
        cat "/tmp/push_${service}.log"
        failed=1
    else
        echo "Successfully pushed ${service}:$TAG and ${service}:latest"
    fi
    
    # Cleanup
    rm -f "/tmp/push_${service}.log" "/tmp/push_${service}.tag.exit" "/tmp/push_${service}.latest.exit"
done

if [ "$failed" == "1" ]; then
    echo "One or more pushes failed"
    exit 1
fi

echo "All images pushed successfully"