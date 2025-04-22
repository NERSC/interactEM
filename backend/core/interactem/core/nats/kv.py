import asyncio
import uuid
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any, Generic, TypeVar

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
    BUCKET_AGENTS,
    BUCKET_METRICS,
    BUCKET_OPERATORS,
    BUCKET_PIPELINES,
)
from interactem.core.logger import get_logger
from interactem.core.nats import (
    get_agents_bucket,
    get_metrics_bucket,
    get_operators_bucket,
    get_pipelines_bucket,
)
from interactem.core.util import create_task_with_ref

logger = get_logger()


class InteractemBucket(str, Enum):
    AGENTS = BUCKET_AGENTS
    OPERATORS = BUCKET_OPERATORS
    METRICS = BUCKET_METRICS
    PIPELINES = BUCKET_PIPELINES


bucket_map: dict[
    InteractemBucket, Callable[[JetStreamContext], Awaitable[KeyValue]]
] = {
    InteractemBucket.AGENTS: get_agents_bucket,
    InteractemBucket.OPERATORS: get_operators_bucket,
    InteractemBucket.METRICS: get_metrics_bucket,
    InteractemBucket.PIPELINES: get_pipelines_bucket,
}

ERRORS_THAT_REQUIRE_RECONNECT = (
    nats.errors.StaleConnectionError,
    nats.errors.UnexpectedEOF,
    nats.errors.ConnectionClosedError,
)

V = TypeVar("V", bound=BaseModel)


class KeyValueLoop(Generic[V]):
    def __init__(
        self,
        nc: NATSClient,
        js: JetStreamContext,
        shutdown_event: asyncio.Event,
        bucket: InteractemBucket,
        data_model: type[V],
        update_interval: float = 10.0,
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
        self._pending_tasks: set[asyncio.Task] = set()

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
                await self._wait_for_next_cycle()

            except Exception as e:
                logger.exception(f"Unexpected error in KeyValueLoop: {e}")
                raise

        logger.info(f"Exiting key-value update loop for {self._bucket_type.value}")

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

        # Create tasks for all value updates
        for key_str, getter in self._value_getters.items():
            value = getter()
            create_task_with_ref(
                self._pending_tasks, self._safe_put_value(key_str, value)
            )

    async def _safe_put_value(self, key_str: str, value: V) -> None:
        if not self._bucket:
            logger.error(f"Cannot put value for key {key_str}: bucket not initialized")
            return

        try:
            validated = self._data_model.model_validate(value)
            await self._bucket.put(key_str, validated.model_dump_json().encode())
        except ERRORS_THAT_REQUIRE_RECONNECT as e:
            logger.warning(f"NATS connection issue while updating key {key_str}: {e}")
            # handle reconnection immediately
            create_task_with_ref(self._pending_tasks, self._attempt_reconnect())
        except Exception as e:
            logger.exception(f"Error updating key {key_str}: {e}")
            raise

    async def _wait_for_next_cycle(self) -> None:
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(), timeout=self._update_interval
            )
        except asyncio.TimeoutError:
            # Normal timeout, continue the loop
            pass

    async def update_now(self) -> None:
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(Exception),
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
        delete_tasks: set[asyncio.Task] = set()
        for key in keys_str:
            create_task_with_ref(delete_tasks, self._safe_delete_key(key))

        await asyncio.gather(*delete_tasks, return_exceptions=True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type(ERRORS_THAT_REQUIRE_RECONNECT),
        reraise=True,
    )
    async def _safe_delete_key(self, key_str: str):
        try:
            await self._bucket.delete(key_str)
        except ERRORS_THAT_REQUIRE_RECONNECT as e:
            logger.warning(f"NATS connection issue while deleting key {key_str}: {e}")
            await self._attempt_reconnect()
            raise  # to let tenacity retry
        except Exception as e:
            logger.exception(f"Error deleting key {key_str}: {e}")
            raise

    async def stop(self) -> None:
        self._running = False

        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
            self._main_task = None

        if self._pending_tasks:
            pending_tasks = list(self._pending_tasks)
            logger.info(f"Waiting for {len(pending_tasks)} pending tasks to complete")
            _, pending = await asyncio.wait(pending_tasks, timeout=2.0)
            if pending:
                logger.info(f"Cancelling {len(pending)} remaining tasks")
                for task in pending:
                    task.cancel()
                await asyncio.wait(pending, timeout=1.0)

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
