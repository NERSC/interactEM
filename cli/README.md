# InteractEM - CLI

## Installation

In your Python environment, from inside the cli folder (where pyproject.toml is located), install the CLI package:
```bash
pip install .
```

## Usage
Before using the CLI, ensure that your virtual environment (where the CLI package is installed) is activated. 
- To see the available commands:
    ```bash
    interactem pipeline --help
    ```
- To create a pipeline with a JSON file:
    ```bash
    interactem pipeline create -f <your_pipeline.json>
    ```
-  To list pipelines:
    ```bash
    interactem pipeline ls
    ```
- To run a pipeline:
    ```bash
    interactem pipeline run <pipeline_id> <revision_id>
    ```
-  To stop a running pipeline:
    ```bash
    interactem pipeline stop <your_pipeline_id> <revision_id>
    ```
- To delete a pipeline:
    ```bash
    interactem pipeline rm <pipeline_id>
    ```