#!/bin/bash

GIT_ROOT_DIR=$(git rev-parse --show-toplevel)
cd $GIT_ROOT_DIR

cd backend/core
uv venv .venv --clear && source .venv/bin/activate
poetry lock
poetry install

cd ../sfapi_models
uv venv .venv --clear && source .venv/bin/activate
poetry lock
poetry install

cd ../app
uv venv .venv --clear && source .venv/bin/activate
poetry lock
poetry install

cd ../agent
uv venv .venv --clear && source .venv/bin/activate
poetry lock
poetry install

cd ../orchestrator
uv venv .venv --clear && source .venv/bin/activate
poetry lock
poetry install

cd ../operators
uv venv .venv --clear && source .venv/bin/activate
poetry lock
poetry install

cd ../metrics
uv venv .venv --clear && source .venv/bin/activate
poetry lock
poetry install

cd ../launcher
uv venv .venv --clear && source .venv/bin/activate
poetry lock
poetry install

cd ${GIT_ROOT_DIR}/operators/distiller-streaming
uv venv .venv --clear && source .venv/bin/activate
poetry lock --regenerate
poetry install

cd $GIT_ROOT_DIR
uv venv .venv --clear && source .venv/bin/activate
poetry lock
poetry install
