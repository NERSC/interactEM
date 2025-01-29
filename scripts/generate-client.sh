#! /usr/bin/env bash

set -e
set -x

# activate backend/app environment using poetry shell command before running
THIS_DIR=$(dirname "$0")
cd $THIS_DIR/..
python -c "import interactem.app.main; import json; print(json.dumps(interactem.app.main.app.openapi()))" > openapi.json
mv openapi.json frontend/interactEM/openapi.json
cd frontend/interactEM
npm run generate-client
npx biome check \
    --formatter-enabled=true \
    --linter-enabled=true \
    --organize-imports-enabled=true \
    --write \
    ./src/client/ ./openapi.json