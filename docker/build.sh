#!/usr/bin/env bash

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)
ORG=${1:-interactem}
PODMAN=${2:-p}

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

$DOCKER build $PLATFORM -t interactem/interactem:$TAG -t interactem/interactem:latest -f $SCRIPT_DIR/Containerfile.base $ROOT_DIR/backend
if [ $? -ne 0 ]; then
    echo "Failed to build interactem/interactem"
    exit 1
fi

$DOCKER build $PLATFORM -t interactem/operator:latest -t interactem/operator:$TAG -t $ORG/operator:$TAG -t $ORG/operator:latest -f $SCRIPT_DIR/Containerfile.operator $ROOT_DIR/backend
if [ $? -ne 0 ]; then
    echo "Failed to build interactem/operator"
    exit 1
fi
