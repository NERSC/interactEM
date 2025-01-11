# interactEM

An interactive [flow-based programming](https://en.wikipedia.org/wiki/Flow-based_programming) platform for streaming experimental data to High-Performance Computing (HPC). Users can wire together containerized operators through a web frontend and deploy them on both HPC and edge resources.

https://github.com/user-attachments/assets/85b669af-e4c6-4fe6-9ad3-b5cce26b1a08

## Features

- **Interactive Web Frontend**: Create data pipelines with a React-based frontend.
- **Containerized Operators**: Uses container technology to ensure consistent execution environments.
- **Data Streaming**: Operators connect and data flows between them over network with point-to-point communication.

## Running locally

First generate `auth.conf` for the NATS cluster and various `.nk` files for NATS authentication:

```bash
cd nats-conf
./generate-auth-nkey.sh
```

Generate the images using

```bash
cd docker
./build.sh
```

Then, bring up services using docker compose (this will also build things):

```bash
docker compose up --force-recreate --remove-orphans --build -d
```

## License

This project is licensed under the LBNL BSD-3 License - see the [LICENSE](LICENSE) file for details.
