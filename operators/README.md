<!-- Generated from docs/source/authoring-operators.md using docs/scripts/sync_readmes.py. Do not edit directly. -->

# Authoring Operators

Operators are pieces of code that perform work on data coming from other operators. You chain them together to build a data pipeline.

## Getting operators into podman storage

Premade operators live under [`operators/`](/operators). Podman needs to know about them before a pipeline can run.

### docker bake + podman pull

We can use `docker bake` and `podman pull` for operators defined in [`docker-bake.hcl`](/operators/docker-bake.hcl).

```bash
cd interactEM
make setup # no need to run this if you already have

# Build all operators and pull them into podman storage
make operators

# Or build a specific operator and pull it into podman storage
make operator target=center-of-mass-partial
```

For faster iteration during development, you can omit the `--build-base` flag by using the lower-level `bake.sh` script directly:

```bash
./operators/bake.sh --push-local --pull-local --target center-of-mass-partial
```

If you [create an operator](#creating-an-operator), you can add it to the HCL file so it becomes part of this build process. This does not happen automatically—update the file manually when you are ready.

### `podman build`

If you create an operator using the instructions below, you can also use a regular `podman build`.

For example, if you have an operator named `my-operator` in the `my-operator/` directory:

```bash
cd my-operator
# tag should match what is found in the "image" field in your operator.json
podman build -t ghcr.io/nersc/interactem/my-operator:latest .
```

## Creating an operator

At minimum, each operator needs three files:

1. [`run.py`](#runpy)
2. [`Containerfile`](#containerfile)
3. [`operator.json`](#specification)

The CLI ships with templates to get you started:

```bash
uv sync
uv run interactem operator new
```

or with `poetry`:

```bash
poetry install
poetry run interactem operator new
```

Or, if you prefer pip:

```bash
pip install .
interactem operator new
```

> **Note:** Operators refresh only in the operators panel during a UI refresh. Existing pipelines are not updated automatically—replace operators manually if needed.

### run.py

Implement the operator logic in `run.py`. Incoming messages are [`BytesMessages`](/backend/core/interactem/core/models/messages.py) that carry data, metadata, and tracking information. Before building, you can quickly check importability with:

```bash
python -m py_compile run.py
```

### Containerfile

Use the operator [base image](/docker/Dockerfile.operator) as the parent image for your `Containerfile`. For example, the [`distiller-streaming`](/operators/distiller-streaming/Containerfile) image includes utilities for processing 4D Camera frames, so other operators can build FROM it.

### Specification

Operator specifications live in `operator.json`. The schema is defined in [`spec.py`](/backend/core/interactem/core/models/spec.py), and an example is provided in [`operators/center-of-mass-partial/operator.json`](/operators/center-of-mass-partial/operator.json).
