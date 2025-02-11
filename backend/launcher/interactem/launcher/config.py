from pathlib import Path

from pydantic import NatsDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    NATS_SERVER_URL: NatsDsn = NatsDsn("nats://localhost:4222")
    SFAPI_KEY_PATH: Path = Path("/secrets/sfapi.pem")
    CONDA_ENV: Path | str
    ENV_FILE_PATH: Path
    SFAPI_ACCOUNT: str
    SFAPI_QOS: str

    @model_validator(mode="after")
    def resolve_path(self) -> "Settings":
        self.SFAPI_KEY_PATH = self.SFAPI_KEY_PATH.expanduser().resolve()
        if not self.SFAPI_KEY_PATH.is_file():
            raise ValueError(f"File not found: {self.SFAPI_KEY_PATH}")
        return self


cfg = Settings()  # type: ignore
