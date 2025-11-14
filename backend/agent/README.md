# InteractEM - Agent

The agent is core component in the InteractEM system for running operator containers, and coordinating their lifecycle and  via NATS messaging.

## Prerequisites

Some python environment manager (e.g., [`poetry`](https://python-poetry.org/docs/) or [`uv`](https://github.com/astral-sh/uv)).

## Configuration

**Set up Environment Variables**  

You should have already run `make setup` in the root directory. Then go to agent directory:

```sh
cd backend/agent
```

- Update the `.env` file for the agent. You can for example set the agent's name by changing `AGENT_NAME`:

```sh
AGENT_NAME=SecretAgentMan # change to how you want it to display in the frontend
```

If you have specific tags to match an operator on, run the following:

```sh
AGENT_TAGS='["ncem-4dcamera","gpu"]'
```

## Install and run

```bash
poetry install
```

or

```bash
uv sync
```

## Run Agent

Activate your virtual environment, then the following inside the directory where the `.env` is:

```bash
cd backend/agent
interactem-agent
```

or with `uv`:

```bash
cd backend/agent
uv run interactem-agent
```
