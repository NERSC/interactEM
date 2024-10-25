#! /usr/bin/env bash

set -e
set -x

cd backend
# activate backend/app environment using poetry shell command before running
python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
node frontend/interactEM/modify-openapi-operationids.js
mv openapi.json frontend/interactEM/openapi.json
cd frontend/interactEM
npm run generate-client
npx biome format --write ./src/generated/client