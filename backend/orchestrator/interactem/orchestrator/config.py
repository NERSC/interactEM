from pydantic import AnyWebsocketUrl, NatsDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ORCHESTRATOR_", extra="ignore")
    NATS_SERVER_URL: AnyWebsocketUrl | NatsDsn = NatsDsn("nats://localhost:4222")
    API_KEY: str = "changeme"


cfg = Settings()
