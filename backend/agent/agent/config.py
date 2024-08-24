from typing import Any

from pydantic import Field, NatsDsn, WebsocketUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    LOCAL: bool = True
    DOCKER_COMPATIBILITY_MODE: bool = False
    MOUNTS: list[dict[str, Any]] = []
    NATS_SERVER_URL: NatsDsn | WebsocketUrl = Field(default="nats://localhost:4222")
    NATS_SERVER_URL_IN_CONTAINER: NatsDsn | WebsocketUrl = Field(
        default="nats://nats1:4222"
    )

cfg = Settings()  # type: ignore
