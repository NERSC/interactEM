"""NATS stream storage type configuration.

This is separated from the main NATS config to allow stream configs to be defined
without triggering full NATS credential validation.
"""

from nats.js.api import StorageType
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageConfig(BaseSettings):
    """Minimal config for just the stream storage type."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    NATS_STREAM_STORAGE_TYPE: StorageType = StorageType.MEMORY

cfg = StorageConfig()
