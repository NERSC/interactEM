#!/usr/bin/env bash

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)

podman build -t interactem/interactem -f $SCRIPT_DIR/Containerfile.base $ROOT_DIR/backend
if [ $? -ne 0 ]; then
    echo "Failed to build interactem/interactem"
    exit 1
fi

podman build -t interactem/operator -f $SCRIPT_DIR/Containerfile.operator $ROOT_DIR/backend
if [ $? -ne 0 ]; then
    echo "Failed to build interactem/operator"
    exit 1
fi
