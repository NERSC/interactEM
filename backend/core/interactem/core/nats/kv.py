import asyncio
import uuid
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any, Generic, TypeVar

import anyio
import nats
import nats.errors
import nats.js
import nats.js.errors
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.kv import KeyValue
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from interactem.core.constants import (
    BUCKET_METRICS,
    BUCKET_STATUS,
)
from interactem.core.logger import get_logger
from interactem.core.nats import (
    get_metrics_bucket,
    get_status_bucket,
)
from interactem.core.util import BaseExceptionGroup

logger = get_logger()


class InteractemBucket(str, Enum):
    METRICS = BUCKET_METRICS
    STATUS = BUCKET_STATUS


bucket_map: dict[
    InteractemBucket, Callable[[JetStreamContext], Awaitable[KeyValue]]
] = {
    InteractemBucket.METRICS: get_metrics_bucket,
    InteractemBucket.STATUS: get_status_bucket,
}

ERRORS_THAT_REQUIRE_RECONNECT = (
    nats.errors.StaleConnectionError,
    nats.errors.ConnectionClosedError,
    nats.errors.TimeoutError,
    nats.js.errors.ServiceUnavailableError,
    nats.js.errors.ServerError,
    nats.errors.NoRespondersError,
    nats.js.errors.NoStreamResponseError,
)

ATTEMPTS_BEFORE_GIVING_UP = 10
DEFAULT_UPDATE_INTERVAL = 1.0  # seconds

V = TypeVar("V", bound=BaseModel)


class KeyValueLoop(Generic[V]):
    def __init__(
        self,
        nc: NATSClient,
        js: JetStreamContext,
        shutdown_event: asyncio.Event,
        bucket: InteractemBucket,
        data_model: type[V],
        update_interval: float = DEFAULT_UPDATE_INTERVAL,
    ):
        self._nc = nc
        self._js = js
        self._shutdown_event = shutdown_event
        self._bucket_type = bucket
        self._update_interval = update_interval
        self._data_model = data_model

        # State management
        self._running = False
        self._bucket: KeyValue | None = None
        self._main_task: asyncio.Task | None = None

        # Callbacks
        self.before_update_callbacks: list[Callable[[], Awaitable[None] | None]] = []
        self.cleanup_callbacks: list[Callable[[], Awaitable[Any] | Any]] = []

        # Data storage
        self._value_getters: dict[str, Callable[[], V]] = {}

    async def _get_bucket(self) -> KeyValue:
        bucket_getter = bucket_map.get(self._bucket_type)
        if not bucket_getter:
            raise ValueError(
                f"No bucket getter found for bucket name: {self._bucket_type.value}"
            )
        return await bucket_getter(self._js)

    async def get_bucket(self) -> KeyValue:
        if self._bucket is None:
            self._bucket = await self._get_bucket()
        return self._bucket

    async def start(self) -> None:
        if self._running:
            return

        try:
            self._bucket = await self._get_bucket()
            self._running = True
            self._main_task = asyncio.create_task(self._loop())
        except Exception as e:
            logger.exception(f"Failed to start KeyValueLoop: {e}")
            raise

    async def _loop(self) -> None:
        logger.info(f"Starting key-value update loop for {self._bucket_type.value}")

        while self._running and not self._shutdown_event.is_set():
            try:
                # Run pre-update callbacks
                await self._run_callbacks()

                # Update all values
                await self._update_values()

                # Wait until next update interval or shutdown
                with anyio.move_on_after(self._update_interval):
                    await self._shutdown_event.wait()

            except Exception as e:
                logger.exception(f"Unexpected error in KeyValueLoop: {e}")
                raise

        # If we exited the loop because of shutdown event but we're still running,
        # we should delete keys and perform cleanup
        if self._shutdown_event.is_set() and self._running:
            logger.info(
                f"Shutdown event detected for {self._bucket_type.value}, cleaning up keys"
            )
            await self.delete_keys()

    async def _run_callbacks(self) -> None:
        for callback in self.before_update_callbacks:
            try:
                result = callback()
                # Handle async callbacks
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception(f"Error in before_update callback: {e}")
                raise

    async def _update_values(self) -> None:
        if not self._bucket:
            logger.error("Cannot update values: bucket not initialized")
            # handle this immediately
            await self._attempt_reconnect()
            return

        # Create child task group for all value updates
        async with anyio.create_task_group() as tg:
            for key_str, getter in self._value_getters.items():
                value = getter()
                tg.start_soon(self._safe_put_value, key_str, value)

    async def _safe_put_value(self, key_str: str, value: V) -> None:
        if not self._bucket:
            logger.error(f"Cannot put value for key {key_str}: bucket not initialized")
            return

        try:
            validated = self._data_model.model_validate(value)
            await self._bucket.put(key_str, validated.model_dump_json().encode())
        except ERRORS_THAT_REQUIRE_RECONNECT as e:
            logger.warning(f"NATS connection issue while updating key {key_str}: {e}")
            await self._attempt_reconnect()
        except Exception as e:
            logger.exception(f"Error updating key {key_str}: {e}")
            raise

    async def _update_now(self) -> None:
        """Immediate update of all of our values."""
        if not self._running:
            logger.warning("Cannot update now: KeyValueLoop is not running")
            return

        try:
            await self._run_callbacks()
            await self._update_values()
        except Exception as e:
            logger.exception(f"Error during immediate update: {e}")
            raise

    async def _run_with_timeout(
        self,
        action: str,
        op: Callable[[], Awaitable[None]],
        timeout: float | None,
    ) -> bool:
        if timeout is None:
            await op()
            return False

        with anyio.move_on_after(timeout) as scope:
            try:
                await op()
            except Exception as e:
                logger.warning("KV %s failed: %s", action, e)
        timed_out = scope.cancel_called
        if timed_out:
            logger.warning("KV %s timed out after %.1fs", action, timeout)
        return timed_out

    async def update_now(
        self,
        timeout: float | None = None,
        *,
        action: str = "update now",
    ) -> bool:
        return await self._run_with_timeout(action, self._update_now, timeout)

    async def stop(
        self,
        timeout: float | None = None,
        *,
        action: str = "stop",
    ) -> bool:
        return await self._run_with_timeout(action, self._stop, timeout)

    @retry(
        stop=stop_after_attempt(ATTEMPTS_BEFORE_GIVING_UP),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(ERRORS_THAT_REQUIRE_RECONNECT),
        reraise=True,
    )
    async def _attempt_reconnect(self) -> bool:
        if not self._running:
            return False

        self._bucket = await self._get_bucket()
        logger.info(f"Reconnected to bucket {self._bucket_type.value}")
        return True

    def add_or_update_value(
        self, key: str | uuid.UUID, value_or_getter: V | Callable[[], V]
    ) -> None:
        key_str = str(key)

        # we can have a callable to get a value, or a ref to one
        if callable(value_or_getter):
            getter = value_or_getter
        else:
            # Convert static values to getters for uniform handling
            value = value_or_getter

            def getter() -> V:
                return value

        self._value_getters[key_str] = getter

    async def delete_keys(self, keys: list[str | uuid.UUID] | None = None) -> None:
        if not self._bucket:
            logger.error("Cannot delete keys: bucket not initialized")
            return

        if keys is None:
            keys = list(self._value_getters.keys())

        keys_str: list[str] = [str(k) for k in keys]

        logger.info(f"Deleting keys: {keys_str}")

        try:
            async with anyio.create_task_group() as tg:
                for key in keys_str:
                    tg.start_soon(self._safe_delete_key, key)
        except BaseExceptionGroup as eg:
            logger.exception(f"Errors during key deletion: {eg}")

    @retry(
        stop=stop_after_attempt(ATTEMPTS_BEFORE_GIVING_UP),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(ERRORS_THAT_REQUIRE_RECONNECT),
        reraise=True,
    )
    async def _safe_delete_key(self, key_str: str):
        if not self._bucket:
            logger.error(f"Cannot delete key {key_str}: bucket not initialized")
            return

        try:
            await self._bucket.delete(key_str)
        except ERRORS_THAT_REQUIRE_RECONNECT as e:
            logger.warning(f"NATS connection issue while deleting key {key_str}: {e}")
            await self._attempt_reconnect()
            raise  # to let tenacity retry
        except Exception as e:
            logger.exception(f"Error deleting key {key_str}: {e}")
            raise

    async def _stop(self) -> None:
        self._running = False

        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
            self._main_task = None

        for callback in self.cleanup_callbacks:
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                # Don't need to raise here because we are shutting down...
                logger.exception(f"Error in cleanup callback: {e}")

        # Delete all keys added to the bucket by this instance
        if self._bucket:
            await self.delete_keys()

    async def refresh_connection(self, nc: NATSClient, js: JetStreamContext) -> None:
        """Refresh the NATS connection context without clearing existing keys."""
        logger.info("Refreshing KV connection for bucket %s", self._bucket_type.value)
        self._nc = nc
        self._js = js
        self._bucket = None
        if self._running:
            await self._attempt_reconnect()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(ERRORS_THAT_REQUIRE_RECONNECT),
        reraise=True,
    )
    async def get_val(self, key: str | uuid.UUID) -> V | None:
        key_str = str(key)
        if not self._bucket:
            raise RuntimeError(f"Cannot get key {key_str}: bucket not initialized")

        try:
            entry = await self._bucket.get(key_str)
            if not entry.value:
                logger.warning(f"Key {key_str} has no value in bucket")
                return None
            return self._data_model.model_validate_json(entry.value)
        except ERRORS_THAT_REQUIRE_RECONNECT:
            await self._attempt_reconnect()
            raise  # to let tenacity retry
        except nats.js.errors.KeyNotFoundError:
            logger.warning(f"Key {key_str} not found in bucket")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error getting key {key_str}: {e}")
            raise
