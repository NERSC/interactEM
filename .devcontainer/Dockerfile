FROM quay.io/podman/stable:latest

# Copied from here: https://github.com/containers/image_build/blob/main/podman/Containerfile
ARG INSTALL_RPMS="podman fuse-overlayfs openssh-clients ucpp git python3.12-pip"
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

RUN pip install --upgrade pip && pip install poetry

WORKDIR /app

COPY ./pyproject.toml ./poetry.lock* /app/

COPY ./thirdparty /app/thirdparty

COPY .git /app/.git

RUN if [ "$INSTALL_DEV" = "true" ] ; then \
  poetry config virtualenvs.create false && \
  poetry install --no-root --no-interaction --no-ansi --with dev ; \
  else \
  poetry config virtualenvs.create false && \
  poetry install --no-root --no-interaction --no-ansi ; \
  fi

RUN poetry install --no-interaction --no-ansi