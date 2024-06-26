from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env")

    AGENT_PORT: int
    AGENT_INTERFACE: str | None
    ORCHESTRATOR_PORT: int
    ORCHESTRATOR_INTERFACE: str | None
    CONTAINER_INTERFACE: str | None


cfg = Settings()  # type: ignore
