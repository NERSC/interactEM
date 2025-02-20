FROM interactem/interactem:latest

COPY ./sfapi_models/ /interactem/sfapi_models/

WORKDIR /interactem/launcher/
COPY ./launcher/README.md ./launcher/pyproject.toml ./launcher/poetry.lock* ./
RUN poetry install --no-root

COPY ./launcher/interactem/ ./interactem/
RUN poetry install --only main
    
COPY ./launcher/run.py ./run.py

CMD ["python", "./run.py"]