from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    LOCAL: bool = True
    DOCKER_COMPATIBILITY_MODE: bool = False
    MOUNTS: list[dict[str, Any]] = []


cfg = Settings()  # type: ignore
