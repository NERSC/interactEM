#!/bin/bash

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)
DOCKER=${1:-docker}

cd $ROOT_DIR

# Build all images using Docker Bake
echo "Building all images with tag $TAG..."
BUILDX_BAKE_ENTITLEMENTS_FS=0 $DOCKER buildx bake --file $ROOT_DIR/docker/docker-bake.hcl --set *.args.TAG=$TAG

if [ $? -ne 0 ]; then
    echo "Failed to build images"
    exit 1
fi

echo "All builds completed successfully"