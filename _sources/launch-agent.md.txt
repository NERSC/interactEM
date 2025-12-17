# Launch an agent

The agent is the process that starts operator containers, coordinates their lifecycle, and talks to the platform over NATS. You need at least one running agent before operators can launch.

## Prerequisites

Have a Python environment manager available (e.g., [`poetry`](https://python-poetry.org/docs/) or [`uv`](https://github.com/astral-sh/uv)).

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

- If you want to target specific resources, set tags:

```bash
AGENT_TAGS='["ncem-4dcamera","gpu"]'
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
