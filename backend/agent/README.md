# InteractEM - Agent

The agent is core component in the InteractEM system for running operator containers, and coordinating their lifecycle and configuration via NATS messaging.

## Running Locally

### Prerequisites

Some python environment manager (e.g., [`poetry`](https://python-poetry.org/docs/) or [`uv`](https://github.com/astral-sh/uv)).

### Configuration

**Set up Environment Variables**  

- Find the Podman Service Endpoint Socket. Open Podman Desktop and go to Settings. Locate and copy the Service Endpoint or Socket Path (e.g., /var/run/podman/podman.sock).
- Alternative method (requires `jq` to be in `$PATH`): run the following script:

```bash
backend/agent/scripts/podman-socket-path.sh
```

- Create `.env`:

```bash
cp backend/agent/.env.example backend/agent/.env
```

- Update the `.env` file for the agent. Endpoint goes to `PODMAN_SERVICE_URI` and set default `AGENT_NAME`.

```bash
# note **3** slashes in unix:///var....
PODMAN_SERVICE_URI=<your_socket_goes_here>
AGENT_NAME=default_agent_name
```

### Install the interactem CLI tool

```bash
cd cli
poetry install
```

or

```bash
cd cli
uv venv .venv --python=3.12
uv pip install -e .
source .venv/bin/activate
```

### Run Agents

Run the following inside the [directory](backend/agent/) where `.env` is.

```bash
interactem agent
```

To run with custom agent's name and tags, set the following environment variables before running the agent (useful while running multiple agents):

```bash
AGENT_NAME="agent_name" AGENT_TAGS='["agent_tag"]' interactem agent
```
