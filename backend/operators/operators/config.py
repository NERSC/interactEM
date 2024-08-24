from pydantic import Field, NatsDsn, WebsocketUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None)
    NATS_SERVER_URL: NatsDsn | WebsocketUrl = Field(default="nats://localhost:4222")

cfg = Settings()
