# interactEM

`interactEM` is an interactive [flow-based programming](https://en.wikipedia.org/wiki/Flow-based_programming) platform for streaming experimental data to High-Performance Computing (HPC). Users wire together containerized operators through a web frontend and deploy them on both HPC and edge resources.

## Demo video

Watch the demo: https://github.com/user-attachments/assets/85b669af-e4c6-4fe6-9ad3-b5cce26b1a08
<!-- docs-only:start -->
```{raw} html
<video width="100%" controls>
  <source src="https://github.com/user-attachments/assets/85b669af-e4c6-4fe6-9ad3-b5cce26b1a08" type="video/mp4">
  Your browser does not support the video tag.
</video>
```
<!-- docs-only:end -->

## Features

- **Interactive Web Frontend**: Create data pipelines with a React-based frontend.
- **Containerized Operators**: Uses container technology to ensure consistent execution environments.
- **Data Streaming**: Operators connect and data flows between them over network with point-to-point communication.

## Running locally

### Prerequisites

- **[Docker](https://docs.docker.com/engine/install/)**, **[Podman](https://podman.io/docs/installation)**, **[uv](https://docs.astral.sh/uv/getting-started/installation/)**

### Configuration

1. **Setup `.env` with secure secrets**

    ```bash
    make setup
    ```

    This automatically:
    - Copies `.env.example` to `.env`
    - Generates secure random values for all secrets
    - Searches for your podman socket
    - Updates your `.env` file

1. **Add GitHub credentials**

    Edit your `.env` file and add GitHub info:

    ```bash
    GITHUB_USERNAME=your_github_username
    GITHUB_TOKEN=your_personal_token
    ```

    You can get a personal token from your [GitHub account settings](https://github.com/settings/tokens). Use a classic token with `read:packages`.

### Starting services

1. **Quick start**

    ```bash
    make setup
    # then fix your GITHUB_USERNAME/TOKEN in .env
    make docker-up
    make operators
    ```

1. **Access the application**

    Open your browser to [http://localhost:5173](http://localhost:5173)

    - Username: `admin@example.com`
    - Password: Check your `.env` file for `FIRST_SUPERUSER_PASSWORD` (auto-generated), or output from `make docker-up`

### Stopping services

1. **To stop services:**

    ```bash
    make docker-down
    ```

1. **To stop and delete database (be careful):**

    ```bash
    make clean
    ```

### Launching an agent

For operators to launch, you need to startup an agent process. See [launching an agent](launch-agent.md) for instructions on how to do this.

## License

This project is licensed under the LBNL BSD-3 License - see the [LICENSE](/LICENSE) file for details.
