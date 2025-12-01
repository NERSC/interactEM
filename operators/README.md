# Operators

## What is an Operator?

Operators are pieces of code that will perform some action on data coming from other operators. They are the bits of code that can be chained together to build a data pipeline.

## Getting operators into podman storage

Premade operators are currently located in the [`operators/`](/operators) directory. To run an operator pipeline, `podman` has to know about it. Can be done using [bake](#docker-bake--podman-pull) or [podman build](#podman-build).

### docker bake + podman pull

We can use use `docker bake` and `podman pull` for operators in the [bake hcl file](/operators/docker-bake.hcl).

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

If you [make](#creating-an-operator) an operator, then you can add it to the `hcl` file and it will be a part of this build process. This doesn't happen automatically, you will have to manually edit that file - look at the format and use your judgment (or ask an agent).

### `podman build`

If you create an operator using the instructions below, you can also use a regular `podman build`.

For example, if we have an operator with the name `my-operator` in the `my-operator/` directory you can build it like this:

```bash
cd my-operator
# tag should match what is found in the "image" field in your operator.json
podman build -t ghcr.io/nersc/interactem/my-operator:latest .  
```

## Creating an operator

At the very least, three files are required to make an operator:

1. [run.py](#runpy)
1. [Containerfile](#containerfile)
1. [Specification](#specification)

As a part of our `cli` tool, we have some templates that can get you started. Using `uv`:

```bash
cd cli
uv sync
uv run interactem operator new
```

or `poetry`:

```bash
cd cli
poetry install
poetry run interactem operator new
```

Or if you are feeling dangerous:

```bash
cd cli
pip install . 
interactem operator new
```


```{note}
Operators will be updated **ONLY** in the operators panel during a refresh. Your existing pipelines will **NOT** be updated. One should manually replace the operators in existing pipelines with the refreshed operator.
```
This will generate the files you need under whatever directory you specify. If you put them in the [operators directory (interactEM/operators/)](/operators), and refresh the frontend, you will see it appear there.

You can build the operators as discussed [above](#running-operators-locally).

### run.py

We need to define the code that will operate on incoming messages. The incoming messages will come in as [BytesMessages](/backend/core/interactem/core/models/messages.py), which contain data, metadata, and tracking information.

Here is an example of the [`run.py`](/operators/center-of-mass-partial/run.py) file for the partial center of mass operator. You can see that the parameters (defined in the [spec](#specification), see below).

### Containerfile

We need to use the operator [base image](/docker/Dockerfile.operator) the parent image for our [`Containerfile`](/operators/center-of-mass-partial/Containerfile). In this case, we are using the [`distiller-streaming`](/operators/distiller-streaming/Containerfile) image as the base, as it contains a lot of utilities for processing 4D Camera frames.

### Specification

Operators specifications need to be defined in a `json` file. The specification can be found in [spec.py](/backend/core/interactem/core/models/spec.py).

Here's an example of an [`operator.json`](/operators/center-of-mass-partial/operator.json) for the partial center of mass operator.
