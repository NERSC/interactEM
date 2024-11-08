from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    INFO = "INFO"
    DEBUG = "DEBUG"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    LOG_LEVEL: LogLevel = LogLevel.INFO


cfg = Settings()
