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

You still have to build these operators and make sure that your local `podman` can see them.

### MacOS

1. Get `docker desktop` and `podman desktop`.
1. Set up docker local docker registry by running:

    ```sh
    docker run -d -p 5001:5000 --restart always --name docker-registry registry:3
    ```

1. Use [bake.sh](./bake.sh) to build all containers with docker. This includes base image, operator, and distiller-streaming. You should do the following

    ```sh
    ./bake --push-local --build-base
    ```

    This will push everything to the local registry, instead of pushing up to GitHub packages. You can also omit `--build-base` to avoid building base images for faster iteration.

1. Set your `.env` file in the operator directory to have the correct podman socket (see [`.env.example`](./.env.example))
1. Use poetry environment from root directory [pyproject.toml](../pyproject.toml) and run the following:

    ```sh
    poetry run python pull_images_from_bake.py
    ```

    This will pull local registry images into podman and tag them appropriately with [`pull_images_from_bake.py`](./pull_images_from_bake.py). This also runs at the end of [`bake.sh`](./bake.sh) if `--pull-local` is given.

The [build_all.sh](./build_all.sh) script was used before, but it is cumbersome so I am not updating it.
