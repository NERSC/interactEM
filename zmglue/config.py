from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env")

    AGENT_PORT: int
    ORCHESTRATOR_PORT: int


cfg = Settings()  # type: ignore
