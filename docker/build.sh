#!/usr/bin/env bash

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)

docker build --platform=linux/amd64,linux/arm64 -t interactem/interactem:$TAG -t interactem/interactem:latest -f $SCRIPT_DIR/Containerfile.base $ROOT_DIR/backend
if [ $? -ne 0 ]; then
    echo "Failed to build interactem/interactem"
    exit 1
fi

docker build --platform=linux/amd64,linux/arm64 -t interactem/operator:$TAG -f $SCRIPT_DIR/Containerfile.operator $ROOT_DIR/backend
if [ $? -ne 0 ]; then
    echo "Failed to build interactem/operator"
    exit 1
fi
