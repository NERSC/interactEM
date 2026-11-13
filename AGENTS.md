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

## Frontend auto-generation

- use `make gen` to generate types after changing any models in the backend

## Testing

- use `make test` for tests

## Operator development patterns

### Operators that depend on a shared package

Operators needing code from a shared package (e.g. `distiller-streaming`,
`distiller-streaming-dense`) do **not** use a `pyproject.toml` path
dependency. Instead:

- The shared package has its own `target "<name>"` + `target "<name>-context"`
  pair in `operators/docker-bake.hcl` (the `-context` target maps the name to
  `target:<name>` as a named buildkit context).
- Consumer operators build `FROM <name>` in their `Containerfile` and inherit
  that image's installed environment directly — no local install step. Extra
  operator-specific deps are layered on with `RUN poetry add ...`. Consumer
  operators typically have **no `pyproject.toml` at all** — just
  `Containerfile` + `operator.json` + `run.py`.
- Adding a *new* shared package requires three things, all easy to miss:
  1. The `target`/`target-context` pair in `docker-bake.hcl`.
  2. Adding the new target name to `operators/bake.sh`'s `--build-base` step
     — it currently hardcodes `base`, `operator`, `distiller-streaming`, so a
     new shared package is silently skipped by `make operators` unless added
     there too.
  3. A real `poetry.lock` committed in the shared package's directory — its
     `Containerfile` unconditionally `COPY`s `poetry.lock`, so the build fails
     at that `COPY` step ("not found") if one was never generated via
     `poetry lock`.

### Triggered / streaming operators

Operators that stream a file out across multiple invocations (rather than
reacting to one input message at a time) use the `trigger` kernel parameter:
`kernel(inputs, parameters, trigger=None)`, returning `None` immediately if
`trigger is None`. Declare the trigger in `operator.json`'s `"triggers"`
array with `"mode": "drain"` (operator is invoked repeatedly until it returns
nothing — good for draining an entire file in one trigger press) or
`"single"`. See `distiller-counted-data-reader` or `read-tem-data` for the
pattern: module-level state holding the active emitter/cached file, reset on
`StopIteration`.

### Mount parameters

A `type: "mount"` parameter named `X` in `operator.json` gets bind-mounted
inside the container at `/mnt/X` (the fixed `DATA_DIRECTORY` constant plus
the parameter's literal `name` — not its `default`, which is only the
host-side source path). `run.py` must do `Path(f"{DATA_DIRECTORY}/X")` with
`X` matching the parameter name exactly.

### image-display's actual input contract

`image-display` does not parse message `meta` and does not decode raw numpy
bytes — it passes `inputs.data` straight to the frontend, which wraps it in
a JPEG-typed `Blob`. So `data` must already be encoded JPEG (or PNG) bytes,
not a raw `array.tobytes()` + shape/dtype meta dict. See `random-image`,
`dpc`, or `center-of-mass-plot` for the PIL/matplotlib encoding pattern to
follow.

### Deploying locally built images to Podman

After `make operators`, images land in the local registry but are not
automatically pulled into Podman's image store. If starting a pipeline fails
with `image not known`, run the pull step manually from `operators/`:

```
uv run --no-project \
  --with python-hcl2 \
  --with podman \
  --with pydantic \
  --with pydantic-settings \
  python pull_images_from_bake.py
```
