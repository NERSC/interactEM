#!/bin/bash

GIT_ROOT_DIR=$(git rev-parse --show-toplevel)
cd $GIT_ROOT_DIR

export NATS_CREDS_FILE=$(pwd)/conf/nats-conf/out_jwt/backend.creds

cd $GIT_ROOT_DIR/backend/core
poetry install
poetry env info
poetry run pytest 

cd $GIT_ROOT_DIR/backend/orchestrator
poetry install
poetry env info
poetry run pytest

cd $GIT_ROOT_DIR/operators/distiller-streaming
poetry install
poetry env info
poetry run pytest