#!/bin/bash

GIT_ROOT_DIR=$(git rev-parse --show-toplevel)
cd $GIT_ROOT_DIR

cd backend/core
poetry lock

cd ../sfapi_models
poetry lock

cd ../app
poetry lock

cd ../agent
poetry lock

cd ../orchestrator
poetry lock

cd ../operators
poetry lock

cd ../metrics
poetry lock