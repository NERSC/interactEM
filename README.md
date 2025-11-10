# interactEM

`interactEM` is an interactive [flow-based programming](https://en.wikipedia.org/wiki/Flow-based_programming) platform for streaming experimental data to High-Performance Computing (HPC). Users can wire together containerized operators through a web frontend and deploy them on both HPC and edge resources.

## Demo video

<https://github.com/user-attachments/assets/85b669af-e4c6-4fe6-9ad3-b5cce26b1a08>

## Features

- **Interactive Web Frontend**: Create data pipelines with a React-based frontend.
- **Containerized Operators**: Uses container technology to ensure consistent execution environments.
- **Data Streaming**: Operators connect and data flows between them over network with point-to-point communication.

## Running locally

### Prerequisites

- **Docker Desktop** and **Podman Desktop** (recommended for easiest setup)

### Configuration

1. **Setup `.env` with secure secrets**

    ```bash
    make env-setup
    ```

    This automatically:
    - Copies `.env.example` to `.env`
    - Generates secure random values for all secrets
    - Updates your `.env` file

1. **Add GitHub credentials**

    Edit your `.env` file and add your GitHub information:

    ```bash
    GITHUB_USERNAME=your_github_username
    GITHUB_TOKEN=your_personal_token
    ```

    You can get a personal token from your [GitHub account settings](https://github.com/settings/tokens).

### Starting services

1. **Quick start**

    ```bash
    make setup # sets up environment variables, do not run as root
    make docker-up # may need to run this as root, depending on your setup
    ```

1. **Access the application**

    Open your browser to [http://localhost:5173](http://localhost:5173)

    Login credentials:
    - **Username**: `admin@example.com`
    - **Password**: Check your `.env` file for `FIRST_SUPERUSER_PASSWORD` (auto-generated), or output from `make docker-up`

### Stopping services

1. **To stop services:**

    ```bash
    make docker-down
    ```

1. **To stop and clean database:**

    ```bash
    make clean
    ```

### Launching an agent

For operators to launch, you need to startup an agent process. See [backend/agent/README.md](backend/agent/README.md) for instructions on how to do this.

## License

This project is licensed under the LBNL BSD-3 License - see the [LICENSE](LICENSE) file for details.
