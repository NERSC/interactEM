from faststream.nats import NatsBroker

from .config import cfg
from .logger import get_logger

logger = get_logger()

def create_nats_broker(servers: list[str] | None = None) -> NatsBroker:
    """Create a configured NATS broker for FastStream."""

    if servers is None:
        servers = ["nats://localhost:4222"]

    # Determine auth options based on config
    if cfg.NATS_SECURITY_MODE.value == "nkeys":
        # For NKEYS authentication
        return NatsBroker(
            servers=servers,
            nkeys_seed_str=cfg.NKEYS_SEED_STR,
        )
    elif cfg.NATS_SECURITY_MODE.value == "creds":
        # For credentials file authentication
        return NatsBroker(
            servers=servers,
            user_credentials=str(cfg.NATS_CREDS_FILE),
        )
    else:
        # No authentication
        return NatsBroker(servers=servers)
