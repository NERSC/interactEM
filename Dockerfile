FROM python:3.12.4-slim-bookworm as build

RUN apt-get update && apt-get install -y --no-install-recommends \
    podman \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install poetry

WORKDIR /app

COPY ./pyproject.toml ./poetry.lock* /app/

COPY ./thirdparty /app/thirdparty

RUN if [ "$INSTALL_DEV" = "true" ] ; then \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi --with dev ; \
    else \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi ; \
    fi

ENV PYTHONPATH=/app

COPY ./zmglue/ /app/zmglue

RUN poetry install --no-interaction --no-ansi