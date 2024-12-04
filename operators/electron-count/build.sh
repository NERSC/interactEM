#!/bin/bash

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)

podman build -t interactem/electron-count -f $SCRIPT_DIR/Containerfile $ROOT_DIR