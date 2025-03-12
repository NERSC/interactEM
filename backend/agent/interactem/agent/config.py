from pathlib import Path

from pydantic import AnyWebsocketUrl, Field, NatsDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    LOCAL: bool = False
    DOCKER_COMPATIBILITY_MODE: bool = False
    PODMAN_SERVICE_URI: str | None = None
    NATS_SERVER_URL: AnyWebsocketUrl | NatsDsn = Field(default="nats://localhost:4222")
    NATS_SERVER_URL_IN_CONTAINER: AnyWebsocketUrl | NatsDsn = Field(
        default="nats://nats1:4222"
    )
    AGENT_TAGS: list[str] = []
    MOUNT_LOCAL_REPO: bool = False
    OPERATOR_CREDS_FILE: Path

    @model_validator(mode="after")
    def ensure_operator_creds_file(self) -> "Settings":
        self.OPERATOR_CREDS_FILE = self.OPERATOR_CREDS_FILE.expanduser().resolve()
        if not self.OPERATOR_CREDS_FILE.is_file():
            raise ValueError("OPERATOR_CREDS_FILE must be provided")
        return self


cfg = Settings()
