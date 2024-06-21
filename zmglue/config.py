from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env")

    AGENT_PORT: int
    ORCHESTRATOR_PORT: int
    CONTAINER_INTERFACE: str | None


cfg = Settings()  # type: ignore
