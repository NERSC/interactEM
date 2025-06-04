# InteractEM - CLI

A command-line interface for executing InteractEM pipelines defined in a JSON File through NATS messaging.

## Installation
Prerequisites: [**Poetry**](https://python-poetry.org/docs/)

1. Activate a virtual environment:
    ```bash
    eval $(poetry env activate)
    ```
1. Install the cli package:
    ```bash
    poetry install
    ```

## Usage
Before using the CLI, ensure that your virtual environment (where the CLI package is installed) is activated. 

- To run a pipeline with a JSON file:
    ```bash
    interactem pipeline run -f <your_pipeline.json_path>
    ```
-  To list running pipelines:
    ```bash
    interactem pipeline ls
    ```
-  To stop a running pipeline:
    ```bash
    interactem pipeline stop <your_pipeline_id>
    ```