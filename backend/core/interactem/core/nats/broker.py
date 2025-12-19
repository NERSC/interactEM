import asyncio
import logging
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

from faststream import BaseMiddleware
from faststream.nats import NatsBroker, NatsPublishCommand

from interactem.core.logger import get_logger

from .config import NatsMode, get_nats_config

logger = get_logger()


def _log_callback_error(task: asyncio.Task, name: str) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("NATS %s callback failed", name)


def _schedule_callback(
    callback: Callable[[], Coroutine[Any, Any, None]] | None, name: str
) -> None:
    if not callback:
        return
    try:
        task = asyncio.create_task(callback())
    except Exception:
        logger.exception("Failed to schedule NATS %s callback", name)
        return
    task.add_done_callback(lambda task: _log_callback_error(task, name))


def get_nats_broker(
    servers: list[str],
    name: str,
    middlewares: Sequence[BaseMiddleware[NatsPublishCommand]] = (),
    on_disconnect: Callable[[], Coroutine[Any, Any, None]] | None = None,
    on_reconnect: Callable[[], Coroutine[Any, Any, None]] | None = None,
    on_closed: Callable[[], Coroutine[Any, Any, None]] | None = None,
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
        _schedule_callback(on_disconnect, "disconnect")

    async def reconnected_cb():
        logger.info("NATS reconnected.")
        _schedule_callback(on_reconnect, "reconnect")

    async def closed_cb():
        logger.info("NATS connection closed.")
        _schedule_callback(on_closed, "closed")

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
        log_level=logging.DEBUG,
        **options,  # type: ignore[call-arg]
    )
