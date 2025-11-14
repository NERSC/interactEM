# AGENTS instructions

## Repository structure

- we are using a namespace package, where `interactem` is the top-level module, followed by the different directories in `backend/`.
- core modules are under `interactem.core`, fastapi in `interactem.app`, orchestrator in `interactem.orchestrator`, agent in `interactem.agent`, etc.

## Dev environment

### Backend

- for backend, we use poetry for package management. for each subdirectory, we first use `uv` to set up a `.venv` with a suitable python installation, and then activate it with `source .venv/bin/activate`, and then use `poetry install` to install the packages into that `.venv`
- we use ruff for formatting. we have the ruff rules set up in `pyproject.toml`, run a `ruff check . --fix` after making changes 

### Frontend

- use `npm`
- to check formatting, run biome:
- we run `npm run dev` to bring up interactEM in web page

### Linting

- `make lint` in repo root

### Docker compose

- Docker compose services needed for local development. `docker compose up --remove-orphans --force-recreate --build -d`
- For development development, we don't want `interactEM` frontend container running here

## Interaction with nats

- to check out what is going on with nats, you can use commands like `nats --creds={repo_root}/conf/nats-conf/out_jwt/backend.creds stream ls` to access information in the nats cluster running in docker compose
- find the stream names in interactem.core.constants

## Auto-generation

- generate the frontend client with `scripts/generate-client.sh` followed by `make lint`
