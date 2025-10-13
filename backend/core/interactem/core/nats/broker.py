from faststream.nats import NatsBroker

from interactem.core.config import cfg
from interactem.core.logger import get_logger

logger = get_logger()

def get_nats_broker(servers: list[str], name: str) -> NatsBroker:
    options_map = {
        cfg.NATS_SECURITY_MODE.NKEYS: {
            "nkeys_seed_str": cfg.NKEYS_SEED_STR,
        },
        cfg.NATS_SECURITY_MODE.CREDS: {
            "user_credentials": str(cfg.NATS_CREDS_FILE),
        },
    }
    options = options_map[cfg.NATS_SECURITY_MODE]

    async def disconnected_cb():
        logger.info("NATS disconnected.")

    async def reconnected_cb():
        logger.info("NATS reconnected.")

    async def closed_cb():
        logger.info("NATS connection closed.")

    return NatsBroker(
        servers=servers,
        name=name,
        allow_reconnect=True,
        max_reconnect_attempts=-1,  # Retry indefinitely
        reconnected_cb=reconnected_cb,
        disconnected_cb=disconnected_cb,
        closed_cb=closed_cb,
        **options,  # type: ignore[call-arg]
    )
