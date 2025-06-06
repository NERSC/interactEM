# interactEM

An interactive [flow-based programming](https://en.wikipedia.org/wiki/Flow-based_programming) platform for streaming experimental data to High-Performance Computing (HPC). Users can wire together containerized operators through a web frontend and deploy them on both HPC and edge resources.

https://github.com/user-attachments/assets/85b669af-e4c6-4fe6-9ad3-b5cce26b1a08

## Features

- **Interactive Web Frontend**: Create data pipelines with a React-based frontend.
- **Containerized Operators**: Uses container technology to ensure consistent execution environments.
- **Data Streaming**: Operators connect and data flows between them over network with point-to-point communication.

## Running locally

### Prerequisites
- **Docker Desktop** and **Podman Desktop** (recommended for easiest setup)
- **NATS Tools**: Command-line utilities for interacting with [NATS](https://github.com/nats-io/natscli?tab=readme-ov-file#installation)

### Configuration

1. **Set up Environment Variables**  
    Add Github and personal token information in `.env` file.

    ```makefile
    GITHUB_USERNAME=your_github_username
    GITHUB_TOKEN=your_personal_token
   ```

1. **Generate NATS Authentication Files**  
    Generate `auth.conf` for the NATS cluster and various `.creds` and `.nk` files for NATS authentication.

    ```bash
    cd nats-conf
    ./generate-auth-jwt.sh
    ```

### Building Docker Images and starting services

1. **Build the Required Images**  
    Use one of the following methods.

    ```bash
    docker/build.sh
    ```
    or
    ```bash
    docker/bake.sh
    ```

1. **Bring up Services**  
    Use docker compose:

    ```bash
    docker compose up --force-recreate --remove-orphans --build -d
    ```

## License

This project is licensed under the LBNL BSD-3 License - see the [LICENSE](LICENSE) file for details.
