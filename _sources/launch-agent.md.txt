# Launch an agent

The agent is the process that starts operator containers, coordinates their lifecycle, and talks to the rest of the platform over NATS. You need at least one running agent before operators can launch.

## Prerequisites

Have a Python environment manager available (e.g., [`uv`](https://github.com/astral-sh/uv)).

## Configure the environment

You should already have run `make setup` in the repository root to create a base `.env`. Then:

```bash
cd backend/agent
```

- Copy `.env.example` if you have not already, and update values as needed.
- Set the agent's display name in `AGENT_NAME`:

```bash
AGENT_NAME=SecretAgentMan  # change to how you want it to display in the frontend
```

- If you want to run operators with specific tags on this agent, set your tags:

```bash
AGENT_TAGS='["ncem-4dcamera"]'
```

## Install and run

Install dependencies with your preferred tool:

```bash
poetry install
```

or

```bash
uv sync
```

If an agent is running at NERSC, we will use `podman-hpc`. If using `uv`, it will attempt to use the python binary from the user account that ran this command first, which is normally stored in `~/.local/share/uv/python`. If you are sharing this agent between users, you can set the `UV_PYTHON_INSTALL_DIR` env var to a shared location.

```bash
uv sync --extra hpc
```

Then activate your virtual environment and start the agent from the directory containing your `.env`:

```bash
cd backend/agent
interactem-agent
```

or with `uv`:

```bash
cd backend/agent
uv run interactem-agent
```

## Connecting an agent to a different NATS cluster

To connect into a different NATS cluster, we have to set the `.env` variables:

```bash
NATS_SERVER_URL=nats://the.url.to.nats # could also be ws/wss (websocket/secure websocket)
NATS_SERVER_URL_IN_CONTAINER=nats://the.url.to.nats # same as above
NATS_CREDS_FILE=/path/to/backend.creds
OPERATOR_CREDS_FILE=/path/to/operator.creds
AGENT_NETWORKS='["your-network-name"]' # need to be changed 
ZMQ_BIND_INTERFACE="eth0" # interface you are planning to transmit data from on this agent. 
```

## Connecting agents and their resources

`AGENT_TAGS` and `AGENT_NETWORKS` matter for how the pipeline will be deployed.

Say you have Data Reader Operator and you want to always run it next to your microscope. You must do the following:

1. On your local agent, set `AGENT_TAGS='["a-unique-tag-name"]'.
1. On your operator that you want to always run on the agent's machine, set the tag in the operator spec:

    ```json
    "tags": [
        {
        "value": "a-unique-tag-name",
        "description": "Required to run on agents with the tag a-unique-tag-name."
        }
    ]
    ```

1. Then, let's say this pipeline involves a processing step that is very heavy and needs gpus. Tag that operator with `gpu`, and it will be sent to an agent that also has the tag `gpu`.
1. If the connection between these operators crosses a `AGENT_NETWORKS` boundary ONE TIME, it may not cross that boundary again. This is because we only allow OUTBOUND connections from Operator inputs, and thereby INBOUND connections to operator outputs. This is a bit of a quirk, and could be fixed by other means in the future.
