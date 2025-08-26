# Building operators

## Building locally

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

    This will pull local registry images into podman and tag them appropriately with [`pull_images_from_bake.py`](./pull_images_from_bake.py). This also runs at the end of [`bake.sh`](./bake.sh)

The [build_all.sh](./build_all.sh) script was used before, but it is cumbersome so I am not updating it.
