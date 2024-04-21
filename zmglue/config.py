from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env")

    AGENT_PORT: int
    ORCHESTRATOR_PORT: int
    CONTAINER_INTERFACE: Optional[str]


cfg = Settings()  # type: ignore
