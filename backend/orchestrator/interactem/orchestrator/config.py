from pydantic import AnyWebsocketUrl, NatsDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None)
    NATS_SERVER_URL: AnyWebsocketUrl | NatsDsn = NatsDsn("nats://localhost:4222")
    ORCHESTRATOR_API_KEY: str = "changeme"
    NUM_PARALLEL_OPERATORS: int = 4


cfg = Settings()
