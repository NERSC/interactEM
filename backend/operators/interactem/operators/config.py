from pydantic import AnyWebsocketUrl, NatsDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    NATS_SERVER_URL: AnyWebsocketUrl | NatsDsn = NatsDsn("nats://localhost:4222")
    ZMQ_BIND_HOSTNAME: str
    ZMQ_BIND_INTERFACE: str

cfg = Settings()
