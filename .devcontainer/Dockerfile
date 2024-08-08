FROM quay.io/podman/stable:latest

# Copied from here: https://github.com/containers/image_build/blob/main/podman/Containerfile
ARG INSTALL_RPMS="podman fuse-overlayfs openssh-clients ucpp git python3.12-pip pipx"
ARG FLAVOR="stable"

RUN dnf -y makecache && \
  dnf -y update && \
  rpm --setcaps shadow-utils 2>/dev/null && \
  case "${FLAVOR}" in \
  stable) \
  dnf -y install $INSTALL_RPMS --exclude container-selinux \
  ;; \
  testing) \
  dnf -y install $INSTALL_RPMS --exclude container-selinux \
  --enablerepo updates-testing \
  ;; \
  upstream) \
  dnf -y install 'dnf-command(copr)' --enablerepo=updates-testing && \
  dnf -y copr enable rhcontainerbot/podman-next && \
  dnf -y install $INSTALL_RPMS \
  --exclude container-selinux \
  --enablerepo=updates-testing \
  ;; \
  *) \
  printf "\\nFLAVOR argument must be set and valid, currently: '${FLAVOR}'\\n\\n" 1>&2 && \
  exit 1 \
  ;; \
  esac && \
  dnf clean all && \
  rm -rf /var/cache /var/log/dnf* /var/log/yum.*

# https://stackoverflow.com/a/57886655
ENV PATH="/root/.local/bin:${PATH}"
RUN pipx install poetry && pipx inject poetry poetry-plugin-bundle

WORKDIR /app

COPY ./pyproject.toml /app/

COPY ./thirdparty /app/thirdparty

COPY .git /app/.git

RUN if [ "$INSTALL_DEV" = "true" ] ; then \
  poetry bundle venv --python=/usr/bin/python3 --with=dev /venv ; \
  else \
  poetry bundle venv --python=/usr/bin/python3 --without=dev /venv ; \
  fi


ENV PATH="/venv/bin:${PATH}"
ENV VIRTUAL_ENV="/venv"

# install nats server v2.10.14
RUN curl -sf https://binaries.nats.dev/nats-io/nats-server/v2@v2.10.14 | sh