# Operators

## What is an Operator?

Operators are pieces of code that will perform some action on data coming from other operators. They are the bits of code that can be chained together to build a data pipeline.

## Running operators locally

Operators are currently located in the [`operators/`](/operators) directory.

To run an operator pipeline, we have to have its container image in `podman`'s container storage. There are several ways to get the container into the podman stroage, but we opt to build the operators using `docker bake`, pull them into a local docker registry, and pull them from this registry with podman:

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

See [bake.sh](/operators/bake.sh) for additional build options.

## Creating an operator

At the very least, three files are required to make an operator:

1. [run.py](#runpy)
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

### run.py

We need to define the code that will operate on incoming messages. The incoming messages will come in as [BytesMessages](/backend/core/interactem/core/models/messages.py), which contain data, metadata, and tracking information.

Here is an example of the [`run.py`](/operators/center-of-mass-partial/run.py) file for the partial center of mass operator. You can see that the parameters (defined in the [spec](#specification), see below).

### Containerfile

We need to use the operator [base image](/docker/Dockerfile.operator) the parent image for our [`Containerfile`](/operators/center-of-mass-partial/Containerfile). In this case, we are using the [`distiller-streaming`](/operators/distiller-streaming/Containerfile) image as the base, as it contains a lot of utilities for processing 4D Camera frames.

### Specification

Operators specifications need to be defined in a `json` file. The specification can be found in [spec.py](/backend/core/interactem/core/models/spec.py).

Here's an example of an [`operator.json`](/operators/center-of-mass-partial/operator.json) for the partial center of mass operator.
