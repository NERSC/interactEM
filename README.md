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
- **NATS Tools**: Command-line utilities for interacting with [NATS](https://github.com/nats-io/natscli?tab=readme-ov-file#installation)

### Configuration

1. **Create a `.env` and setup environment variables**

    Create a `.env`

    ```bash
    cd interactEM
    cp .env.example .env
    ```

    Add Github and personal token information in `.env` file. You will need to get this from your github account.

    ```makefile
    GITHUB_USERNAME=your_github_username
    GITHUB_TOKEN=your_personal_token
   ```

1. **Generate NATS Authentication Files**  
    Generate `auth.conf` for the NATS cluster and various `.creds` and `.nk` files for NATS authentication.

    ```bash
    cd conf/nats-conf
    ./generate-auth-jwt.sh
    ```

### Building Docker Images and starting backend services

1. **Build the Required Images**  

    ```bash
    docker/bake.sh
    ```

1. **Bring up Services**  
    Use docker compose:

    ```bash
    docker compose up --force-recreate --remove-orphans --build -d
    ```

### Starting frontend service

Follow instructions in [frontend/interactEM/README.md](frontend/interactEM/README.md) to install `npm` and install dependencies.

You will end up with a `frontend/interactEM/node_modules` directory if you did things correctly. Then you should be able to run

```bash
npm run dev
```

and you should get some output like:

```bash
> @interactem/interactem@0.0.4 dev
> vite


  VITE v6.3.5  ready in 318 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

The username/password for this login are in `.env.example`

```bash
FIRST_SUPERUSER_USERNAME=admin@example.com
FIRST_SUPERUSER_PASSWORD=changethis
```

### Launching an agent

For operators to launch, you need to startup an agent process. See [backend/agent/README.md](backend/agent/README.md) for instructions on how to do this.

## License

This project is licensed under the LBNL BSD-3 License - see the [LICENSE](LICENSE) file for details.
