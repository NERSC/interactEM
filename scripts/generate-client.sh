#! /usr/bin/env bash

set -e
set -x

# activate backend/app environment using poetry shell command before running
THIS_DIR=$(dirname "$0")
cd $THIS_DIR/..
python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > openapi.json
mv openapi.json frontend/interactEM/openapi.json
cd frontend/interactEM
npm run generate-client
npx biome format --write ./src/client/