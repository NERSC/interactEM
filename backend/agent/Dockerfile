FROM quay.io/podman/stable:latest

ARG INSTALL_RPMS="git"

WORKDIR /app/

RUN dnf -y makecache && \
  dnf -y update && \
  dnf -y install $INSTALL_RPMS --exclude container-selinux && \
  dnf clean all && \
  rm -rf /var/cache /var/log/dnf* /var/log/yum.*


RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3 && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

# Copy poetry.lock* in case it doesn't exist in the repo
COPY ./agent/pyproject.toml ./agent/poetry.lock* /app/

COPY ./core/ /core/

COPY ./agent/agent/ /app/agent/

COPY ./agent/thirdparty/ /app/thirdparty/

# Allow installing dev dependencies to run tests
ARG INSTALL_DEV=false
RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then poetry install --no-root ; else poetry install --no-root --only main ; fi"

ENV PYTHONPATH=/app