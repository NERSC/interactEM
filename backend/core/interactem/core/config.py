import pathlib
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
    CORE_PACKAGE_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent
    OPERATORS_PACKAGE_DIR: pathlib.Path = (
        pathlib.Path(__file__).parent.parent.parent.parent / "operators" / "interactem"
    )
    LOG_LEVEL: LogLevel = LogLevel.INFO


cfg = Settings()
