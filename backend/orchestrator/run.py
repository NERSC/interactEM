import anyio
from anyio import TASK_STATUS_IGNORED
from anyio.abc import TaskStatus
from faststream.exceptions import IncorrectState
from nats.js import JetStreamContext

from interactem.core.logger import get_logger
from interactem.orchestrator.app import app, deployment_state
from interactem.orchestrator.orchestrator import continuous_update_kv

logger = get_logger()


async def wait_for_broker_connection(
    task_status: TaskStatus[JetStreamContext] = TASK_STATUS_IGNORED,
) -> None:
    """
    Wait for FastStream broker to connect and provide JetStream context
    for use in other tasks.
    """
    max_wait_attempts = 300
    wait_interval = 0.1
    for _ in range(max_wait_attempts):
        if app.broker is not None:
            try:
                js = app.broker.config.connection_state.stream
                task_status.started(js)
                return
            except IncorrectState:
                await anyio.sleep(wait_interval)
        else:
            await anyio.sleep(wait_interval)
    raise RuntimeError("FastStream broker failed to connect within allotted time")


async def main():
    logger.info("Starting orchestrator...")

    async with anyio.create_task_group() as tg:
        # we wrap this because FastStream catches exceptions
        # and we want to cancel other tasks when we shut down
        async def app_runner():
            try:
                await app.run()
            finally:
                tg.cancel_scope.cancel()

        tg.start_soon(app_runner)
        js = await tg.start(wait_for_broker_connection)
        tg.start_soon(continuous_update_kv, js, deployment_state)

        logger.info("Orchestrator started successfully")


if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user")
    logger.info("Orchestrator process exited")
