# Getting Started

Use this path if you just want to see interactEM running locally.

## 1. Bring up the core stack

Follow the [running locally](introduction.md#running-locally) steps to install prerequisites, generate your `.env`, and start Docker services.

## 2. Launch an agent

Once the web UI is up, start an agent so operators can be scheduled. Instructions live on the [launching an agent](launch-agent.md) page.

## 3. Build or pull operators

- Use `make operators` to build all bundled operators into Podman storage.
- Or build a specific operator target with `make operator target=<name>`.
- To create your own, follow [authoring operators](authoring-operators.md).
