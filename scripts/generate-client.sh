#! /usr/bin/env bash

set -e
set -x

# activate backend/app environment using poetry shell command before running
THIS_DIR=$(dirname "$0")
ROOT_DIR=$(realpath $THIS_DIR/..)
cd $ROOT_DIR
uv run --project backend/app -- \
    python -c "import interactem.app.main; import json; print(json.dumps(interactem.app.main.app.openapi()))" \
    > $ROOT_DIR/openapi.json
cd $ROOT_DIR
mv openapi.json frontend/interactEM/openapi.json
cd frontend/interactEM
npm run generate-client
npx biome check \
    --formatter-enabled=true \
    --linter-enabled=true \
    --assist-enabled=true \
    --write \
    ./src/client/ ./openapi.json