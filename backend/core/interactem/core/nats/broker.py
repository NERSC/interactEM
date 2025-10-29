from collections.abc import Sequence

from faststream import BaseMiddleware
from faststream.nats import NatsBroker, NatsPublishCommand

from interactem.core.logger import get_logger

from .config import NatsMode, get_nats_config

logger = get_logger()

def get_nats_broker(
    servers: list[str],
    name: str,
    middlewares: Sequence[BaseMiddleware[NatsPublishCommand]] = (),
) -> NatsBroker:
    nats_cfg = get_nats_config()
    options_map = {
        NatsMode.NKEYS: {
            "nkeys_seed_str": nats_cfg.NKEYS_SEED_STR,
        },
        NatsMode.CREDS: {
            "user_credentials": str(nats_cfg.NATS_CREDS_FILE),
        },
    }
    options = options_map[nats_cfg.NATS_SECURITY_MODE]

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
        logger=logger,
        middlewares=middlewares,  # type: ignore
        **options,  # type: ignore[call-arg]
    )
