import uuid
from importlib import resources
from pathlib import Path

import netifaces
from jinja2 import Template
from pydantic import AnyWebsocketUrl, Field, NatsDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from interactem.core.constants import LOGS_DIR_IN_CONTAINER
from interactem.core.logger import get_logger
from interactem.core.models.containers import (
    PodmanMount,
    PodmanMountType,
)
from interactem.core.nats.config import NatsMode, get_nats_config

logger = get_logger()
VECTOR_NATS_CREDS_TARGET = "/nats.creds"


def _load_vector_template() -> str:
    return resources.files(__package__).joinpath("templates/vector.yaml.j2").read_text(encoding="utf-8")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    ID: uuid.UUID = Field(default_factory=uuid.uuid4)
    USE_NORMAL_PODMAN: bool = False
    PODMAN_SERVICE_URI: str | None = None
    PODMAN_BINARY_PATH: Path | None = None
    NATS_SERVER_URL: AnyWebsocketUrl | NatsDsn = NatsDsn("nats://localhost:4222")
    NATS_SERVER_URL_IN_CONTAINER: AnyWebsocketUrl | NatsDsn = NatsDsn(
        "nats://nats1:4222"
    )
    AGENT_TAGS: list[str] = []
    AGENT_NETWORKS: set[str] = set()
    AGENT_NAME: str | None = None
    MOUNT_LOCAL_REPO: bool = False
    OPERATOR_CREDS_FILE: Path

    # ZMQ configuration
    ZMQ_BIND_HOSTNAME: str = ""
    ZMQ_BIND_INTERFACE: str

    # Always pull images
    ALWAYS_PULL_IMAGES: bool = False

    # Vector configuration
    VECTOR_ENABLED: bool = True
    LOG_DIR: Path = Path("~/.interactem/logs").expanduser().resolve()
    VECTOR_CONFIG_PATH: Path | None = None
    OPERATOR_EXTRA_ENV: dict[str, str] = Field(default_factory=dict, exclude=True)

    @model_validator(mode="after")
    def ensure_operator_creds_file(self) -> "Settings":
        self.OPERATOR_CREDS_FILE = self.OPERATOR_CREDS_FILE.expanduser().resolve()
        if not self.OPERATOR_CREDS_FILE.is_file():
            raise ValueError("OPERATOR_CREDS_FILE must be provided")
        return self

    @model_validator(mode="after")
    def get_bind_hostname(self) -> "Settings":
        # if set by hostname, return early
        if self.ZMQ_BIND_HOSTNAME:
            return self

        try:
            # Get the IP address of the specified interface
            addresses = netifaces.ifaddresses(self.ZMQ_BIND_INTERFACE)
            # Get the IPv4 addresses (netifaces.AF_INET is the constant for IPv4)
            if netifaces.AF_INET in addresses:
                # Return the first IPv4 address
                logger.info(
                    f"Using interface {self.ZMQ_BIND_INTERFACE} with address {addresses[netifaces.AF_INET][0]['addr']}"
                )
                self.ZMQ_BIND_HOSTNAME = addresses[netifaces.AF_INET][0]["addr"]
                return self
            else:
                raise ValueError(
                    f"No IPv4 address found for interface {self.ZMQ_BIND_INTERFACE}"
                )
        except (ValueError, KeyError) as e:
            # If interface doesn't exist or has no IPv4 address
            logger.exception(
                f"Interface {self.ZMQ_BIND_INTERFACE} not found or has no IPv4 address, falling back to localhost."
            )
            raise e

    @model_validator(mode="after")
    def make_log_cfg(self) -> "Settings":
        self.LOG_DIR = self.LOG_DIR / str(self.ID)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.VECTOR_CONFIG_PATH = self.generate_vector_config()
        return self

    @model_validator(mode="after")
    def check_podman_binary_full_path(self) -> "Settings":
        if not self.PODMAN_BINARY_PATH:
            return self

        if not self.PODMAN_BINARY_PATH.is_absolute():
            raise ValueError(
                "PODMAN_BINARY must be an absolute path, if it is supplied at all."
            )
        return self

    @property
    def vector_enabled(self) -> bool:
        return self.VECTOR_CONFIG_PATH is not None

    @property
    def log_mount(self) -> PodmanMount | None:
        if not self.vector_enabled:
            return None
        return PodmanMount(
            type=PodmanMountType.bind,
            source=str(self.LOG_DIR),
            target=LOGS_DIR_IN_CONTAINER,
        )

    @property
    def vector_mounts(self) -> list[PodmanMount]:
        if not self.vector_enabled:
            return []
        config_mount = PodmanMount(
            type=PodmanMountType.bind,
            source=str(self.VECTOR_CONFIG_PATH),
            target="/etc/vector/vector.yaml",
        )
        log_mount = self.log_mount
        mounts = [config_mount]
        if log_mount:
            mounts.append(log_mount)
        creds_mount = self.vector_creds_mount
        if creds_mount:
            mounts.append(creds_mount)
        return mounts

    @property
    def vector_creds_mount(self) -> PodmanMount | None:
        creds_path = self.nats_creds_file
        if not creds_path:
            return None
        return PodmanMount(
            type=PodmanMountType.bind,
            source=str(creds_path),
            target=VECTOR_NATS_CREDS_TARGET,
        )

    @property
    def nats_creds_file(self) -> Path | None:
        try:
            nats_cfg = get_nats_config()
        except ValueError:
            return None
        if nats_cfg.NATS_SECURITY_MODE != NatsMode.CREDS:
            return None
        return nats_cfg.NATS_CREDS_FILE

    def generate_vector_config(self) -> Path | None:
        """Generates a vector config file and returns path to it"""

        if not self.VECTOR_ENABLED:
            logger.warning("VECTOR_ENABLED is false, skipping log aggregation.")
            return None

        if not self.LOG_DIR.exists():
            raise RuntimeError(
                f"Log directory {self.LOG_DIR} does not exist. Should not happen."
            )
        templ: Template = Template(_load_vector_template())
        vector_yaml = templ.render(
            logs_dir=LOGS_DIR_IN_CONTAINER,
            agent_id=self.ID,
            nats_url=str(self.NATS_SERVER_URL_IN_CONTAINER),
            nats_creds_path=VECTOR_NATS_CREDS_TARGET,
        )
        output_path = self.LOG_DIR / "vector.yaml"
        with open(output_path, "w") as f:
            f.write(vector_yaml)

        logger.info(f"Generated vector config at {output_path}")
        return output_path


cfg = Settings()  # pyright: ignore[reportCallIssue]
