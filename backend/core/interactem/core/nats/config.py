import pathlib
from enum import Enum

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class NatsMode(str, Enum):
    NKEYS = "nkeys"
    CREDS = "creds"


class NatsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    NATS_SECURITY_MODE: NatsMode = NatsMode.CREDS
    # We need to supply either the NKEY seed string or file for all clients
    NKEYS_SEED_STR: str = ""
    NKEYS_SEED_FILE: pathlib.Path | None = None

    # If creds mode, we need to supply the creds file
    NATS_CREDS_FILE: pathlib.Path | None = None

    @model_validator(mode="after")
    def validate_nats(self) -> "NatsSettings":
        mode_method_map = {
            NatsMode.NKEYS: self.validate_nkeys,
            NatsMode.CREDS: self.validate_creds,
        }
        return mode_method_map[self.NATS_SECURITY_MODE]()

    def validate_nkeys(self) -> "NatsSettings":
        if not self.NKEYS_SEED_FILE and not self.NKEYS_SEED_STR:
            raise ValueError(
                "Either NKEYS_SEED_FILE or NKEYS_SEED_STR must be provided"
            )
        if self.NKEYS_SEED_FILE and self.NKEYS_SEED_STR:
            raise ValueError(
                "Only one of NKEYS_SEED_FILE or NKEYS_SEED_STR must be provided"
            )

        # We only use NKEYS_SEED_STR in the rest of code
        if self.NKEYS_SEED_FILE:
            if not self.NKEYS_SEED_FILE.is_file():
                raise ValueError(f"File not found: {self.NKEYS_SEED_FILE}")

            with open(self.NKEYS_SEED_FILE) as f:
                self.NKEYS_SEED_STR = f.readline().strip()

        if not self.NKEYS_SEED_STR:
            raise ValueError("NKEYS_SEED_STR must not be empty")

        return self

    def validate_creds(self) -> "NatsSettings":
        if not self.NATS_CREDS_FILE:
            raise ValueError("NATS_CREDS_FILE must be provided")
        if not self.NATS_CREDS_FILE.exists() or not self.NATS_CREDS_FILE.is_file():
            raise ValueError(f"NATS creds file not found: {self.NATS_CREDS_FILE}")

        self.NATS_CREDS_FILE = self.NATS_CREDS_FILE.expanduser().resolve()
        return self


_nats_config_cache: NatsSettings | None = None


def get_nats_config() -> NatsSettings:
    """
    Lazily load NATS configuration. Prevents requiring NATS_CREDS_FILE
    unless explicitly connecting.
    """
    global _nats_config_cache
    if _nats_config_cache is None:
        _nats_config_cache = NatsSettings()
    return _nats_config_cache
