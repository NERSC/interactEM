# TODO: this is deprecated. We should use the core base image...
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10

WORKDIR /app/

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

# Copy poetry.lock* in case it doesn't exist in the repo
COPY ./app/pyproject.toml ./app/poetry.lock* /app/

# Allow installing dev dependencies to run tests
ARG INSTALL_DEV=false

COPY ./core/ /core/
COPY ./sfapi_models/ /sfapi_models/

RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then poetry install --no-root ; else poetry install --no-root --only main ; fi"

ENV PYTHONPATH=/app

ENV MODULE_NAME=interactem.app.main

COPY ./app/scripts/ /app/

COPY ./app/alembic.ini /app/

COPY ./app/prestart.sh /app/

COPY ./app/tests-start.sh /app/

COPY ./app/interactem /app/interactem
