import asyncio

from core.nats import create_or_update_stream, nc
from core.nats.streams import AGENTS_STREAM_CONFIG
from nats.aio.client import Client as NATSClient
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DISTILLER_TOKEN: str


async def main():
    client = await nc(servers=["nats://localhost:4222"], name="test-nkeys")
    js = client.jetstream()
    await create_or_update_stream(AGENTS_STREAM_CONFIG, js)
    await client.close()
    cfg = Settings()  # type: ignore

    client = NATSClient()
    await client.connect(
        servers=["nats://localhost:4222"], name="test-token", token=cfg.DISTILLER_TOKEN
    )
    js = client.jetstream()
    await create_or_update_stream(AGENTS_STREAM_CONFIG, js)

    await asyncio.sleep(3)
    await create_or_update_stream(AGENTS_STREAM_CONFIG, js)


if __name__ == "__main__":
    asyncio.run(main())
