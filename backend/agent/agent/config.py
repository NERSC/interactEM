from pydantic import Field, NatsDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    LOCAL: bool = True
    DOCKER_COMPATIBILITY_MODE: bool = False
    PODMAN_SERVICE_URI: str | None = None
    NATS_SERVER_URL: NatsDsn = Field(default="nats://localhost:4222")
    NATS_SERVER_URL_IN_CONTAINER: NatsDsn = Field(default="nats://nats1:4222")
    AGENT_MACHINE_NAME: str | None = None
    MOUNT_LOCAL_REPO: bool = False


cfg = Settings()
