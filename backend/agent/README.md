# InteractEM - Agent

The agent is a core component in the InteractEM system for running operator containers, and coordinating their lifecycle and configuration via NATS messaging.

## Running Locally

### Prerequisites
[**Poetry**](https://python-poetry.org/docs/)

### Configuration
**Set up Environment Variables**  

- Find the Podman Service Endpoint Socket. Open Podman Desktop and go to Settings. Locate and copy the Service Endpoint or Socket Path (e.g., /var/run/podman/podman.sock).
- Alternative method (if not using Podman Desktop; requires jq to be in your `$PATH`): Run the following command from the agent directory:

```bash
./scripts/podman-socket-path.sh
```

- Update the `.env` file for the agent. Endpoint goes to `PODMAN_SERVICE_URI` and set default `AGENT_NAME`.

```makefile
PODMAN_SERVICE_URI=<your_socket_goes_here>
AGENT_NAME=default_agent_name
```

### Run Agents
**Use `poetry run` in agent directory where `.env` is present:**

```bash
poetry run interactem-agent
```
To run with custom agent's name and tags, set the following environment variables before running the agent (useful while running multiple agents):
```bash
AGENT_NAME="agent_name" AGENT_TAGS='["agent_tag"]' poetry run interactem-agent
```
