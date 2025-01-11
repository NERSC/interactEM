import pathlib
from enum import Enum

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    INFO = "INFO"
    DEBUG = "DEBUG"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class NatsMode(str, Enum):
    NKEYS = "nkeys"
    CREDS = "creds"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    CORE_PACKAGE_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent
    OPERATORS_PACKAGE_DIR: pathlib.Path = (
        pathlib.Path(__file__).parent.parent.parent / "operators"
    )
    LOG_LEVEL: LogLevel = LogLevel.INFO

    # ------- NATS settings -------
    NATS_MODE: NatsMode = NatsMode.NKEYS
    # We need to supply either the NKEY seed string or file for all clients
    NKEYS_SEED_STR: str = ""
    NKEYS_SEED_FILE: pathlib.Path | None = None

    # If creds mode, we need to supply the creds file
    NATS_CREDS_FILE: pathlib.Path | None = None

    @model_validator(mode="after")
    def validate_nats(self) -> "Settings":
        mode_method_map = {
            NatsMode.NKEYS: self.validate_nkeys,
            NatsMode.CREDS: self.validate_creds,
        }
        return mode_method_map[self.NATS_MODE]()

    def validate_nkeys(self) -> "Settings":
        if not self.NKEYS_SEED_FILE and not self.NKEYS_SEED_STR:
            raise ValueError("Either NKEYS_SEED or NKEYS_SEED_STR must be provided")
        if self.NKEYS_SEED_FILE and self.NKEYS_SEED_STR:
            raise ValueError("Only one of NKEYS_SEED or NKEYS_SEED_STR must be provided")

        # We only use NKEYS_SEED_STR in the rest of code
        if self.NKEYS_SEED_FILE:
            if not self.NKEYS_SEED_FILE.is_file():
                raise ValueError(f"File not found: {self.NKEYS_SEED_FILE}")

            with open(self.NKEYS_SEED_FILE) as f:
                self.NKEYS_SEED_STR = f.readline().strip()

        if not self.NKEYS_SEED_STR:
            raise ValueError("NKEYS_SEED_STR must not be empty")

        return self

    def validate_creds(self) -> "Settings":
        if not self.NATS_CREDS_FILE:
            raise ValueError("NATS_CREDS_FILE must be provided")
        if not self.NATS_CREDS_FILE.exists() or not self.NATS_CREDS_FILE.is_file():
            raise ValueError(f"NATS creds file not found: {self.NATS_CREDS_FILE}")

        self.NATS_CREDS_FILE = self.NATS_CREDS_FILE.expanduser().resolve()
        return self


cfg = Settings()
