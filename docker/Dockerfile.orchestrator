FROM interactem/interactem:latest

WORKDIR /interactem/orchestrator/
COPY ./orchestrator/README.md ./orchestrator/pyproject.toml ./orchestrator/poetry.lock* ./
RUN poetry install --no-root

COPY ./orchestrator/interactem/ ./interactem/
RUN poetry install --only main

COPY ./orchestrator/run.py ./

CMD ["python", "run.py"]