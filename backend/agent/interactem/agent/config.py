import uuid
from pathlib import Path

import netifaces
from pydantic import AnyWebsocketUrl, Field, NatsDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from interactem.core.logger import get_logger

logger = get_logger()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    ID: uuid.UUID = Field(default_factory=uuid.uuid4)
    LOCAL: bool = False
    DOCKER_COMPATIBILITY_MODE: bool = False
    PODMAN_SERVICE_URI: str | None = None
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


cfg = Settings()  # pyright: ignore[reportCallIssue]
