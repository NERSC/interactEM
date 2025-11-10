import uuid
from collections.abc import AsyncGenerator, Coroutine
from contextlib import asynccontextmanager
from typing import Any

import anyio
from anyio import AsyncContextManagerMixin
from anyio.abc import TaskGroup

from interactem.core.logger import get_logger

logger = get_logger()


class DeploymentContext(AsyncContextManagerMixin):
    """Manages async tasks for a pipeline deployment using anyio task groups.

    All spawned tasks are automatically tracked and cancelled on deployment exit.
    """

    def __init__(self, deployment_id: uuid.UUID):
        self.deployment_id = deployment_id
        self.task_group: TaskGroup | None = None
        logger.info(f"Created DeploymentContext for deployment {deployment_id}")

    @asynccontextmanager
    async def __asynccontextmanager__(self) -> AsyncGenerator["DeploymentContext"]:
        """Manage deployment lifecycle with anyio task group."""
        try:
            async with anyio.create_task_group() as tg:
                self.task_group = tg
                yield self
        except anyio.get_cancelled_exc_class():
            raise
        finally:
            self.task_group = None

    def cancel(self) -> None:
        """Cancel all tasks in this deployment."""
        if self.task_group is None:
            logger.warning(f"DeploymentContext {self.deployment_id} not initialized")
            return
        self.task_group.cancel_scope.cancel()

    def spawn_task(
        self, coro: Coroutine[Any, Any, Any], name: str | None = None
    ) -> None:
        """Spawn a task that runs concurrently and cancels with deployment.

        Args:
            coro: Coroutine to run
            name: Optional task name for debugging
        """
        if self.task_group is None:
            raise RuntimeError(
                f"DeploymentContext {self.deployment_id} not initialized. "
                "Must use as context manager."
            )

        async def task_wrapper() -> None:
            """Log exceptions and cancellation."""
            try:
                await coro
            except anyio.get_cancelled_exc_class():
                raise
            except Exception as e:
                logger.exception(
                    f"Error in task {name} for deployment {self.deployment_id}: {e}"
                )
                raise

        self.task_group.start_soon(task_wrapper, name=name)
