from pathlib import Path
from typing import Self

from pydantic import NatsDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    NATS_SERVER_URL: NatsDsn = NatsDsn("nats://localhost:4222")
    SFAPI_KEY_PATH: Path = Path("/secrets/sfapi.pem")
    CONDA_ENV: Path | str
    ENV_FILE_PATH: Path

    @model_validator(mode="after")
    def resolve_path(self) -> Self:
        self.SFAPI_KEY_PATH = self.SFAPI_KEY_PATH.expanduser().resolve()
        if not self.SFAPI_KEY_PATH.is_file():
            raise ValueError(f"File not found: {self.SFAPI_KEY_PATH}")
        return self


cfg = Settings()  # type: ignore
