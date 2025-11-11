# Authoring operators

## What is an Operator?

Operators are pieces of code that will perform some action on data coming from other operators. They are the bits of code that can be chained together to build a data pipeline.

### Creating an operator

At the very least, three files are required to make an operator:

1. [`run.py`](#runpy-file)
1. [Containerfile](#containerfile)
1. [Specification](#specification)

As a part of our `cli` tool, we have some templates that can get you started. Using `uv`:

```bash
cd cli
uv venv .venv
uv pip install .
source .venv/bin/activate
interactem operator new
```

One can similarly do this with `poetry install` (either way should work), or with a plain `pip install .`.

### `run.py` file

We need to define the code that will operate on incoming messages. The incoming messages will come in as [BytesMessages](https://github.com/NERSC/interactEM/blob/main/backend/core/interactem/core/models/messages.py), which contain data, metadata, and tracking information.

Here is an example of the [`run.py`](https://github.com/NERSC/interactEM/blob/main/operators/center-of-mass-partial/run.py) file for the partial center of mass operator. You can see that the parameters (defined in the [spec](#specification), see below).

### Containerfile

We need to use the operator base image (`ghcr.io/nersc/interactem/operator`) the parent image for our [`Containerfile`](https://github.com/NERSC/interactEM/blob/main/operators/center-of-mass-partial/Containerfile). In this case, we are using the [`distiller-streaming`](https://github.com/NERSC/interactEM/blob/main/operators/distiller-streaming/Containerfile) image as the base, as it contains a lot of utilities for processing 4D Camera frames.

### Specification

Operators specifications need to be defined in a `json` file. The specification can be found in [spec.py](https://github.com/NERSC/interactEM/blob/main/backend/core/interactem/core/models/spec.py).

Here's an example of an [`operator.json`](https://github.com/NERSC/interactEM/blob/main/operators/center-of-mass-partial/operator.json) for the partial center of mass operator.

## Building locally

Operators are located (for now) in the [operators/](https://github.com/NERSC/interactEM/blob/main/operators) directory. After you add an `operator.json` to any subdirectory of `operators` and refresh your frontend, it will appear in the list of operators.

To build and deploy operators locally, run the following commands from the repository root:

```bash
# Initial setup (run once)
make setup

# Build all operators
make operators

# Or build a specific operator
make operator target=center-of-mass-partial
```

The `make` commands handle all the complexity:

- Setting up a local Docker registry
- Building the operator base image and distiller-streaming base
- Building your operator containers
- Pushing images to the local registry
- Pulling images into podman with correct tags

For faster iteration during development, you can omit the `--build-base` flag by using the lower-level `bake.sh` script directly:

```bash
./operators/bake.sh --push-local --pull-local --target center-of-mass-partial
```

See [bake.sh](./bake.sh) for additional build options.
