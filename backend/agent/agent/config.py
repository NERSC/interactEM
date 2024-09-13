from typing import Any

from pydantic import Field, NatsDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    LOCAL: bool = True
    DOCKER_COMPATIBILITY_MODE: bool = False
    PODMAN_SERVICE_URI: str | None = None
    MOUNTS: list[dict[str, Any]] = []
    NATS_SERVER_URL: NatsDsn = Field(default="nats://localhost:4222")
    NATS_SERVER_URL_IN_CONTAINER: NatsDsn = Field(default="nats://nats1:4222")
    AGENT_MACHINE_NAME: str = "perlmutter"


cfg = Settings()
